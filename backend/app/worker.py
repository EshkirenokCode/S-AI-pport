import asyncio
import json
import logging
import signal
import sys
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import uuid4

import httpx
from fastapi import HTTPException
from mcp import Client, StdioServerParameters

from app.db import Database, clean, js
from app.policy import PolicyError, digest, eligible
from app.providers import SYSTEM_PROMPT, live_next, offline_next
from app.services import LabClient, delegate
from app.settings import settings
from app.tools import ToolRegistry

log = logging.getLogger('saipport.worker')
TERMINAL = ('completed', 'needs_human', 'failed', 'cancelled')


class InterruptedRun(Exception):
    pass


class Worker:
    def __init__(self):
        self.cfg = settings()
        self.db = Database(self.cfg.database_url)
        self.lab = LabClient()
        self.owner = uuid4()
        self.stopping = asyncio.Event()

    async def open(self):
        await self.db.open()

    async def close(self):
        await self.lab.close()
        await self.db.close()

    async def claim(self):
        async with self.db.pool.connection() as c, c.transaction():
            run = await (await c.execute('''SELECT * FROM runs WHERE status='queued'
                OR (status='running' AND lease_until<now()) ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1''')).fetchone()
            if not run:
                return None
            return await (await c.execute('''UPDATE runs SET status='running',lease_owner=%s,
                lease_until=now()+%s*interval '1 second',attempts=attempts+1,
                started_at=coalesce(started_at,now()) WHERE id=%s RETURNING *''',
                (self.owner, self.cfg.lease_seconds, run['id']))).fetchone()

    async def check(self, run):
        fresh = await self.db.one('SELECT * FROM runs WHERE id=%s AND tenant_id=%s', (run['id'], run['tenant_id']))
        if fresh['lease_owner'] != self.owner or fresh['status'] != 'running':
            raise InterruptedRun('Worker lease is no longer active')
        if fresh['cancel_requested']:
            raise InterruptedRun('Investigation was cancelled')
        if datetime.now(UTC) > fresh['deadline']:
            raise PolicyError('Run time budget exhausted')
        if fresh['attempts'] > 3:
            raise PolicyError('Recovery attempt budget exhausted')

    async def heartbeat(self, run):
        while True:
            await asyncio.sleep(max(1, self.cfg.lease_seconds//3))
            await self.db.execute("UPDATE runs SET lease_until=now()+%s*interval '1 second' WHERE id=%s AND lease_owner=%s AND status='running'",
                (self.cfg.lease_seconds, run['id'], self.owner))

    async def finish(self, run, status, error=None):
        await self.db.execute('''UPDATE runs SET status=%s,error=%s,lease_owner=NULL,lease_until=NULL,
            finished_at=CASE WHEN %s THEN now() ELSE NULL END WHERE id=%s AND lease_owner=%s''',
            (status, error, status in TERMINAL, run['id'], self.owner))
        await self.db.event(run, 'state', 'Investigation ' + status.replace('_', ' '), {'status': status})

    @asynccontextmanager
    async def transport(self, run):
        if self.cfg.tool_transport == 'direct':
            registry = ToolRegistry(self.db, self.lab)
            yield lambda name, args: registry.call(run, name, args)
            return
        params = StdioServerParameters(command=sys.executable, args=['-m', 'app.mcp_server'],
            env={'SUPPORT_API_URL': self.cfg.app_url, 'SUPPORT_CONTEXT': delegate(run)})
        async with Client(params, read_timeout_seconds=25) as client:
            tools = await client.list_tools()
            if len(tools.tools) != 7:
                raise PolicyError('MCP tool contract mismatch')
            await self.db.event(run, 'transport', 'Scoped MCP session connected',
                                {'transport': 'stdio', 'tools': len(tools.tools), 'protocol': client.protocol_version})

            async def call(name, args):
                result = await client.call_tool(name, args)
                if result.is_error:
                    return {'error': 'MCP tool validation failed'}
                if result.structured_content is not None:
                    return result.structured_content
                return json.loads(next(c.text for c in result.content if c.type == 'text'))
            yield call

    async def investigate(self, run):
        ticket = await self.db.one('SELECT family,subject,body FROM tickets WHERE id=%s AND tenant_id=%s', (run['ticket_id'], run['tenant_id']))
        checkpoint = run['checkpoint']
        messages = checkpoint.get('messages') or [{'role': 'system', 'content': SYSTEM_PROMPT},
            {'role': 'user', 'content': json.dumps(ticket)}]
        turns = checkpoint.get('turns', 0)
        async with self.transport(run) as call:
            while turns < self.cfg.max_model_calls:
                await self.check(run)
                await self.db.event(run, 'check', 'Checking evidence' if run['provider'] == 'deterministic' else 'Model is reviewing evidence',
                                    {'provider': run['provider'], 'turn': turns+1})
                calls = offline_next(ticket, messages) if run['provider'] == 'deterministic' else await live_next(self.db, run, messages)
                turns += 1
                if not calls:
                    messages.append({'role': 'user', 'content': 'Use the available tools and finish_investigation; plain text is not a final result.'})
                    continue
                # Validate IDs/shape before retaining only the public function call protocol.
                safe_calls = []
                for c in calls[:5]:
                    safe_calls.append({'id': str(c['id'])[:150], 'type': 'function', 'function':
                        {'name': c['function']['name'], 'arguments': c['function']['arguments']}})
                messages.append({'role': 'assistant', 'content': None, 'tool_calls': safe_calls})
                done = False
                for c in safe_calls:
                    await self.check(run)
                    try:
                        args = json.loads(c['function']['arguments'])
                        if not isinstance(args, dict):
                            raise ValueError('Tool arguments must be an object')
                        result = await call(c['function']['name'], args)
                    except (ValueError, KeyError):
                        result = {'error': 'Invalid JSON tool arguments'}
                    messages.append({'role': 'tool', 'tool_call_id': c['id'], 'content': json.dumps(clean(result))})
                    if c['function']['name'] == 'finish_investigation' and result.get('accepted'):
                        done = True
                await self.db.execute('UPDATE runs SET checkpoint=%s WHERE id=%s AND lease_owner=%s',
                                      (js({'messages': messages, 'turns': turns}), run['id'], self.owner))
                if done:
                    current = await self.db.one('SELECT result FROM runs WHERE id=%s', (run['id'],))
                    action = await self.db.one('SELECT id FROM actions WHERE run_id=%s', (run['id'],))
                    outcome = current['result'].get('disposition')
                    await self.finish(run, 'waiting_for_approval' if action else 'completed' if outcome == 'resolved' else 'needs_human')
                    return
        raise PolicyError('Model call budget exhausted before a valid conclusion')

    async def execute(self, run):
        action = await self.db.one('SELECT * FROM actions WHERE run_id=%s AND tenant_id=%s', (run['id'], run['tenant_id']))
        if not action or action['status'] not in ('approved', 'executing', 'succeeded'):
            raise PolicyError('No approved repair is available')
        receipt = await self.lab.receipt(run['tenant_id'], action['id'])
        if not receipt:
            await self.check(run)
            approver = await self.db.one("SELECT id FROM actors WHERE id=%s AND tenant_id=%s AND role='operator'", (action['approved_by'], run['tenant_id']))
            if not approver or digest(action['payload']) != action['digest']:
                raise PolicyError('Approver permission or proposal integrity check failed')
            state = await self.lab.state(run['tenant_id'], action['payload']['account_id'])
            if state['version'] != action['payload']['expected_version']:
                await self.db.execute("UPDATE actions SET status='stale' WHERE id=%s", (action['id'],))
                raise PolicyError('Account changed after proposal. Investigate again before another action.')
            eligible(state, action['kind'], action['target_id'])
            await self.db.execute("UPDATE actions SET status='executing' WHERE id=%s AND status IN ('approved','executing')", (action['id'],))
            await self.db.event(run, 'execution', 'Executing the approved repair', {'action_id': str(action['id']), 'target_id': action['target_id']})
            await self.check(run)
            body = {k: action['payload'][k] for k in ('kind', 'target_id', 'account_id', 'expected_version')}
            body.update(operation_id=str(action['id']), tenant_id=str(run['tenant_id']))
            try:
                response = await self.lab.client.post('/operations', json=body)
                response.raise_for_status()
                receipt = response.json()
            except (httpx.TransportError, httpx.HTTPStatusError):
                receipt = await self.lab.receipt(run['tenant_id'], action['id'])
                if not receipt:
                    await self.db.execute("UPDATE actions SET status='unknown' WHERE id=%s", (action['id'],))
                    raise PolicyError('External result is uncertain. No blind retry was performed.') from None
        await self.db.event(run, 'verification', 'Reading the account again to verify the effect', {'receipt': receipt})
        state = await self.lab.state(run['tenant_id'], action['payload']['account_id'])
        verified = ((state['plan'] == 'Pro' and state['billing']['event']['status'] == 'processed')
                    if action['kind'] == 'reprocess_billing_event' else
                    (state['delivery']['event']['status'] == 'delivered' and state['delivery']['event'].get('acknowledged') is True))
        await self.db.execute('UPDATE actions SET status=%s,receipt=%s WHERE id=%s',
                              ('succeeded' if verified else 'failed', js(receipt), action['id']))
        row = await self.db.one('SELECT result,cancel_requested FROM runs WHERE id=%s', (run['id'],))
        result = row['result']
        result['verification'] = {'verified': verified, 'account_version': state['version'], 'plan': state['plan'],
                                  'operation_id': str(action['id']), 'cancel_requested': row['cancel_requested']}
        if verified:
            result['summary'] = ('The paid Pro access is restored. The account was read again and the billing event is processed.'
                if action['kind'] == 'reprocess_billing_event' else 'The event was delivered. A fresh read confirms the destination acknowledgement.')
            result['reply'] = ('Your Pro access has been restored. I reprocessed the failed access-update event and checked that your account is now on Pro. No additional charge was made.'
                if action['kind'] == 'reprocess_billing_event' else 'The event has now been delivered. I retried the failed delivery and verified the destination acknowledgement.')
        else:
            result['summary'] = 'The operation returned a receipt, but the expected change was not verified. Human review is required.'
            result['reply'] = 'The recovery operation completed, but I could not verify that it restored the expected state. I have escalated this for further investigation.'
        await self.db.execute('UPDATE runs SET result=%s WHERE id=%s AND lease_owner=%s', (js(result), run['id'], self.owner))
        await self.db.event(run, 'verified' if verified else 'verification_failed',
                            'Repair verified' if verified else 'Expected effect was not verified', result['verification'])
        await self.db.audit(run['tenant_id'], action['approved_by'], 'action.verified' if verified else 'action.verification_failed', action['id'], run['id'])
        await self.db.execute('UPDATE tickets SET status=%s WHERE id=%s AND tenant_id=%s',
                              ('resolved' if verified else 'needs_human', run['ticket_id'], run['tenant_id']))
        await self.finish(run, 'completed' if verified else 'needs_human')

    async def process(self, run):
        heartbeat = asyncio.create_task(self.heartbeat(run))
        try:
            await self.check(run)
            await self.db.event(run, 'state', 'Investigation started' if run['attempts'] == 1 else 'Worker recovered the investigation',
                                {'attempt': run['attempts'], 'phase': run['phase']})
            async with asyncio.timeout(self.cfg.run_timeout_seconds):
                await (self.investigate(run) if run['phase'] == 'investigate' else self.execute(run))
        except InterruptedRun:
            fresh = await self.db.one('SELECT status FROM runs WHERE id=%s', (run['id'],))
            if fresh['status'] == 'running':
                await self.finish(run, 'cancelled')
        except (PolicyError, HTTPException) as e:
            message = str(e.detail) if isinstance(e, HTTPException) else str(e)
            await self.finish(run, 'needs_human', message)
        except httpx.HTTPStatusError as e:
            await self.finish(run, 'failed', f'Upstream HTTP {e.response.status_code}. No successful outcome was assumed.')
        except (httpx.TransportError, TimeoutError):
            await self.finish(run, 'needs_human', 'An upstream request timed out or was unreachable. The outcome is unverified.')
        except asyncio.CancelledError:
            await self.db.execute('UPDATE runs SET lease_until=now() WHERE id=%s AND lease_owner=%s', (run['id'], self.owner))
            raise
        except Exception as e:
            log.error('run=%s error_type=%s', run['id'], type(e).__name__)
            await self.finish(run, 'failed', f'Investigation stopped: {type(e).__name__}. See the observable steps.')
        finally:
            heartbeat.cancel()
            await asyncio.gather(heartbeat, return_exceptions=True)

    async def serve(self):
        await self.open()
        try:
            while not self.stopping.is_set():
                run = await self.claim()
                if run:
                    task = asyncio.create_task(self.process(run))
                    stop = asyncio.create_task(self.stopping.wait())
                    await asyncio.wait([task, stop], return_when=asyncio.FIRST_COMPLETED)
                    if not task.done():
                        task.cancel()
                    stop.cancel()
                    await asyncio.gather(task, stop, return_exceptions=True)
                else:
                    try:
                        await asyncio.wait_for(self.stopping.wait(), timeout=0.4)
                    except TimeoutError:
                        pass
        finally:
            await self.close()


async def main():
    worker = Worker()
    for sig in (signal.SIGINT, signal.SIGTERM):
        asyncio.get_running_loop().add_signal_handler(sig, worker.stopping.set)
    await worker.serve()


if __name__ == '__main__':
    logging.basicConfig(level=logging.WARNING)
    asyncio.run(main())
