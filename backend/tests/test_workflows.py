from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import httpx
import psycopg
import pytest
from conftest import approve, investigate, wait_run

from app.policy import PolicyError, digest, eligible
from app.schemas import Propose


@pytest.mark.parametrize(('scenario', 'expected', 'action'), [
    ('billing_recoverable', 'waiting_for_approval', True),
    ('billing_missing_event', 'needs_human', False),
    ('billing_unconfirmed', 'needs_human', False),
    ('billing_conflict', 'needs_human', False),
    ('billing_already_processed', 'completed', False),
    ('delivery_transient', 'waiting_for_approval', True),
    ('delivery_timeout', 'waiting_for_approval', True),
    ('delivery_rate_limit', 'waiting_for_approval', True),
    ('delivery_auth', 'needs_human', False),
    ('delivery_config', 'needs_human', False),
    ('configuration', 'completed', False),
    ('configuration_unknown', 'needs_human', False),
])
def test_workflow_disposition(client, scenario, expected, action):
    _, run = investigate(client, scenario)
    assert run['status'] == expected, run
    assert bool(run['actions']) == action
    assert run['result']['source_ids']
    assert any(e['kind'] == 'transport' and e['data']['transport'] == 'stdio' for e in run['events'])
    if action:
        assert not run['result'].get('verification')


@pytest.mark.parametrize('scenario', ['billing_recoverable', 'delivery_transient'])
def test_approved_effect_and_duplicate_decision(client, stack, scenario):
    ticket, run = investigate(client, scenario)
    action = run['actions'][0]
    result = approve(client, run)
    assert result['status'] == 'completed', result
    assert result['result']['verification']['verified'] is True
    for _ in range(2):
        assert client.post('/api/actions/'+action['id']+'/decision', json={'decision': 'approve', 'digest': action['digest']}).status_code == 200
    with psycopg.connect(stack.env['SANDBOX_DATABASE_URL']) as c:
        assert c.execute('SELECT count(*) FROM receipts WHERE operation_id=%s', (action['id'],)).fetchone()[0] == 1
        state, version = c.execute('SELECT state,version FROM accounts WHERE id=%s', (ticket['account_id'],)).fetchone()
        assert version == 2
        event = state['billing' if scenario.startswith('billing') else 'delivery']['event']
        assert len(event['attempts']) == 2


def test_verification_failure_never_claims_success(client):
    _, run = investigate(client, 'billing_no_effect')
    result = approve(client, run)
    assert result['status'] == 'needs_human'
    assert result['result']['verification']['verified'] is False
    assert result['actions'][0]['status'] == 'failed'
    assert 'could not verify' in result['result']['reply']


def test_cross_tenant_every_object(client, stack):
    _, run = investigate(client, 'billing_recoverable')
    doc = next(e['data']['result']['document']['id'] for e in run['events'] if e['data'].get('tool') == 'read_document')
    with httpx.Client(base_url=stack.env['APP_URL']) as other:
        other.post('/api/demo/session', json={}).raise_for_status()
        for path in [f"/api/tickets/{run['ticket_id']}", f"/api/runs/{run['id']}", f"/api/runs/{run['id']}/events", '/api/documents/'+doc]:
            assert other.get(path).status_code == 404
        action = run['actions'][0]
        assert other.post('/api/actions/'+action['id']+'/decision', json={'decision': 'approve', 'digest': action['digest']}).status_code == 404
        assert other.patch('/api/runs/'+run['id']+'/draft', json={'reply': 'hijack'}).status_code == 404
        assert other.post('/api/runs/'+run['id']+'/cancel').status_code == 404


def test_analyst_and_forged_approval(client):
    client.post('/api/demo/session', json={'role': 'analyst'}).raise_for_status()
    _, run = investigate(client, 'injection')
    assert run['status'] == 'waiting_for_approval'
    action = run['actions'][0]
    assert client.post('/api/actions/'+action['id']+'/decision', json={'decision': 'approve', 'digest': action['digest']}).status_code == 403
    assert not run['result'].get('verification')


def test_proposal_digest_and_database_immutability(client, stack):
    _, run = investigate(client, 'billing_recoverable')
    a = run['actions'][0]
    assert client.post('/api/actions/'+a['id']+'/decision', json={'decision': 'approve', 'digest': '0'*64}).status_code == 409
    with psycopg.connect(stack.env['DATABASE_URL'], autocommit=True) as c:
        with pytest.raises(psycopg.errors.RaiseException):
            c.execute('UPDATE actions SET target_id=%s WHERE id=%s', ('different-event', a['id']))


def test_stale_state_is_not_executed(client, stack):
    ticket, run = investigate(client, 'billing_recoverable')
    with psycopg.connect(stack.env['SANDBOX_DATABASE_URL'], autocommit=True) as c:
        c.execute('UPDATE accounts SET version=version+1 WHERE id=%s', (ticket['account_id'],))
    result = approve(client, run)
    assert result['status'] == 'needs_human'
    assert result['actions'][0]['status'] == 'stale'
    with psycopg.connect(stack.env['SANDBOX_DATABASE_URL']) as c:
        assert c.execute('SELECT count(*) FROM receipts WHERE account_id=%s', (ticket['account_id'],)).fetchone()[0] == 0


def test_competing_approvals_execute_once(client, stack):
    ticket, run = investigate(client, 'billing_recoverable')
    a = run['actions'][0]
    def click(_):
        return client.post('/api/actions/'+a['id']+'/decision', json={'decision': 'approve', 'digest': a['digest']}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(click, range(2))) == [200, 200]
    assert wait_run(client, run['id'])['result']['verification']['verified']
    with psycopg.connect(stack.env['SANDBOX_DATABASE_URL']) as c:
        assert c.execute('SELECT count(*) FROM receipts WHERE account_id=%s', (ticket['account_id'],)).fetchone()[0] == 1


def test_cancel_waiting_invalidates_proposal(client):
    _, run = investigate(client, 'billing_recoverable')
    client.post('/api/runs/'+run['id']+'/cancel').raise_for_status()
    cancelled = client.get('/api/runs/'+run['id']).json()
    assert cancelled['status'] == 'cancelled'
    a = cancelled['actions'][0]
    assert a['status'] == 'cancelled'
    assert client.post('/api/actions/'+a['id']+'/decision', json={'decision': 'approve', 'digest': a['digest']}).status_code == 409


def test_declined_action_has_no_effect(client, stack):
    ticket, run = investigate(client, 'billing_recoverable')
    a = run['actions'][0]
    client.post('/api/actions/'+a['id']+'/decision', json={'decision': 'reject', 'digest': a['digest']}).raise_for_status()
    assert client.get('/api/runs/'+run['id']).json()['status'] == 'needs_human'
    with psycopg.connect(stack.env['SANDBOX_DATABASE_URL']) as c:
        assert c.execute('SELECT version FROM accounts WHERE id=%s', (ticket['account_id'],)).fetchone()[0] == 1


def test_recovery_after_waiting_and_expired_lease(client, stack):
    ticket, run = investigate(client, 'billing_recoverable')
    stack.stop_worker()
    a = run['actions'][0]
    try:
        client.post('/api/actions/'+a['id']+'/decision', json={'decision': 'approve', 'digest': a['digest']}).raise_for_status()
        with psycopg.connect(stack.env['DATABASE_URL'], autocommit=True) as c:
            c.execute("UPDATE runs SET status='running',lease_owner=%s,lease_until=now()-interval '1 second' WHERE id=%s", (uuid4(), run['id']))
    finally:
        stack.start_worker()
    recovered = wait_run(client, run['id'])
    assert recovered['status'] == 'completed'
    assert recovered['result']['verification']['verified']
    assert recovered['attempts'] == 1


def test_unknown_and_malformed_tools_are_rejected(client, stack):
    ticket = client.get('/api/tickets').json()[0]
    stack.stop_worker()
    try:
        rid = client.post('/api/tickets/'+ticket['id']+'/runs', json={}).json()['id']
        with psycopg.connect(stack.env['DATABASE_URL'], autocommit=True) as c:
            c.execute("UPDATE runs SET status='running',lease_owner=%s,lease_until=now()+interval '20 seconds' WHERE id=%s", (uuid4(), rid))
            tenant, actor = c.execute('SELECT tenant_id,actor_id FROM runs WHERE id=%s', (rid,)).fetchone()
        import time

        import jwt
        token = jwt.encode({'scope': 'tools', 'tenant': str(tenant), 'actor': str(actor), 'run': rid, 'exp': time.time()+20}, stack.env['APP_SECRET'], algorithm='HS256')
        for name, args in [('shell', {'command': 'env'}), ('get_account_context', {'tenant_id': str(uuid4())}), ('propose_action', {'kind': 'refund', 'target_id': 'any'})]:
            r = client.post('/api/internal/tools', headers={'Authorization': 'Bearer '+token}, json={'name': name, 'arguments': args})
            assert r.status_code == 200
            assert 'error' in r.json()
        assert client.post('/api/internal/tools', json={'name': 'get_account_context', 'arguments': {}}).status_code == 401
        client.post('/api/runs/'+rid+'/cancel')
    finally:
        stack.start_worker()


def test_origin_guard_and_live_key_missing(client):
    assert client.post('/api/demo/session', json={}, headers={'Origin': 'https://attacker.example'}).status_code == 403
    t = client.get('/api/tickets').json()[0]
    assert client.post('/api/tickets/'+t['id']+'/runs', json={'provider': 'openrouter'}).status_code == 503


def test_tool_schema_cannot_expand_authority():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        Propose(kind='reprocess_billing_event', target_id='evt', tenant_id=str(uuid4()))
    assert digest({'a': 1, 'b': 2}) == digest({'b': 2, 'a': 1})


def test_cooldown_blocks_retry():
    state = {'delivery': {'integration_status': 'active', 'configuration_valid': True, 'event':
        {'id': 'evt', 'status': 'failed', 'retryable': True, 'error': '429', 'retry_after': '2099-01-01T00:00:00Z'}}}
    with pytest.raises(PolicyError, match='cooldown'):
        eligible(state, 'retry_delivery', 'evt')
