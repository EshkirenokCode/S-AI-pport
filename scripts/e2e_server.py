"""Disposable real-service stack for browser tests."""

import os
import secrets
import signal
import subprocess
import sys
import time
from pathlib import Path

import psycopg
from psycopg import sql

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.settings import settings

root = Path(__file__).resolve().parents[1]
cfg = settings()
product = cfg.database_url.rsplit("/", 1)[0] + "/saipport_browser"
sandbox = cfg.sandbox_database_url.rsplit("/", 1)[0] + "/saipport_lab_browser"
for url in (product, sandbox):
    with psycopg.connect(url.rsplit("/", 1)[0] + "/postgres", autocommit=True) as c:
        name = url.rsplit("/", 1)[1]
        if not c.execute(
            "SELECT 1 FROM pg_database WHERE datname=%s", (name,)
        ).fetchone():
            c.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
env = {
    **os.environ,
    "DATABASE_URL": product,
    "SANDBOX_DATABASE_URL": sandbox,
    "APP_URL": "http://127.0.0.1:18002",
    "SANDBOX_URL": "http://127.0.0.1:18003",
    "ALLOWED_ORIGINS": "http://127.0.0.1:18002",
    "MODEL_PROVIDER": "deterministic",
    "OPENROUTER_API_KEY": "",
    "TOOL_TRANSPORT": "mcp",
    "SESSION_LIMIT_PER_HOUR": "1000",
    "APP_SECRET": secrets.token_hex(32),
    "SANDBOX_TOKEN": secrets.token_hex(32),
}
subprocess.run(
    [sys.executable, "-m", "app.migrate"], cwd=root / "backend", env=env, check=True
)
processes = []


def shutdown(*_):
    for process in reversed(processes):
        process.terminate()
    for process in processes:
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
    raise SystemExit(0)


signal.signal(signal.SIGTERM, shutdown)
signal.signal(signal.SIGINT, shutdown)
for args in [
    (
        "-m",
        "uvicorn",
        "app.sandbox:app",
        "--host",
        "127.0.0.1",
        "--port",
        "18003",
        "--log-level",
        "warning",
    ),
    (
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        "18002",
        "--log-level",
        "warning",
    ),
    ("-m", "app.worker"),
]:
    processes.append(
        subprocess.Popen([sys.executable, *args], cwd=root / "backend", env=env)
    )
try:
    while all(p.poll() is None for p in processes):
        time.sleep(0.2)
finally:
    shutdown()
