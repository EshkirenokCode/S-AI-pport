import os
import secrets
import subprocess
import sys
import time
from pathlib import Path

import httpx
import psycopg
import pytest
from psycopg import sql

from app.settings import settings


class TestStack:
    def __init__(self, env):
        self.env = env
        self.processes = []
        self.worker = None

    def spawn(self, *args):
        process = subprocess.Popen([sys.executable, *args], env=self.env, cwd=Path(__file__).parents[1],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.processes.append(process)
        return process

    def start_worker(self):
        self.worker = self.spawn('-m', 'app.worker')

    def stop_worker(self):
        if self.worker and self.worker.poll() is None:
            self.worker.terminate()
            self.worker.wait(timeout=10)


@pytest.fixture(scope='session')
def stack():
    cfg = settings()
    product = os.getenv('TEST_DATABASE_URL', cfg.database_url.rsplit('/', 1)[0]+'/saipport_test')
    sandbox = os.getenv('TEST_SANDBOX_DATABASE_URL', cfg.sandbox_database_url.rsplit('/', 1)[0]+'/saipport_lab_test')
    for url in (product, sandbox):
        with psycopg.connect(url.rsplit('/', 1)[0]+'/postgres', autocommit=True) as c:
            name = url.rsplit('/', 1)[1]
            if not c.execute('SELECT 1 FROM pg_database WHERE datname=%s', (name,)).fetchone():
                c.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
    env = {**os.environ, 'DATABASE_URL': product, 'SANDBOX_DATABASE_URL': sandbox,
        'APP_URL': 'http://127.0.0.1:18000', 'SANDBOX_URL': 'http://127.0.0.1:18001',
        'APP_SECRET': secrets.token_hex(32), 'SANDBOX_TOKEN': secrets.token_hex(32),
        'OPENROUTER_API_KEY': '', 'MODEL_PROVIDER': 'deterministic', 'TOOL_TRANSPORT': 'mcp',
        'SESSION_LIMIT_PER_HOUR': '1000', 'RUN_TIMEOUT_SECONDS': '90', 'LEASE_SECONDS': '6'}
    subprocess.run([sys.executable, '-m', 'app.migrate'], env=env, cwd=Path(__file__).parents[1], check=True)
    stack = TestStack(env)
    stack.spawn('-m', 'uvicorn', 'app.sandbox:app', '--host', '127.0.0.1', '--port', '18001', '--log-level', 'warning')
    stack.spawn('-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '18000', '--log-level', 'warning')
    stack.start_worker()
    for _ in range(100):
        try:
            if httpx.get(env['APP_URL']+'/ready', timeout=1).status_code == 200:
                break
        except httpx.HTTPError:
            pass
        time.sleep(0.1)
    else:
        raise RuntimeError('Test services did not start')
    yield stack
    for process in reversed(stack.processes):
        if process.poll() is None:
            process.terminate()
    for process in stack.processes:
        process.wait(timeout=10)


@pytest.fixture
def client(stack):
    with httpx.Client(base_url=stack.env['APP_URL'], timeout=20) as c:
        c.post('/api/demo/session', json={}).raise_for_status()
        yield c


def investigate(client, scenario):
    ticket = next(t for t in client.get('/api/tickets').json() if t['scenario'] == scenario)
    response = client.post(f"/api/tickets/{ticket['id']}/runs", json={})
    response.raise_for_status()
    return ticket, wait_run(client, response.json()['id'])


def wait_run(client, run_id, states=('waiting_for_approval', 'completed', 'needs_human', 'failed', 'cancelled')):
    for _ in range(200):
        r = client.get('/api/runs/'+str(run_id))
        r.raise_for_status()
        run = r.json()
        if run['status'] in states:
            return run
        time.sleep(0.1)
    raise AssertionError(f'Run {run_id} did not finish: {run}')


def approve(client, run):
    action = run['actions'][0]
    r = client.post('/api/actions/'+action['id']+'/decision', json={'decision': 'approve', 'digest': action['digest']})
    r.raise_for_status()
    return wait_run(client, run['id'])
