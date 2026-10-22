"""Run an isolated local stack; stop owned application processes on exit."""

import os
import shutil
import signal
import subprocess
import time
from pathlib import Path
from urllib.parse import urlparse

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
env = {
    **os.environ,
    **{k: v for k, v in dotenv_values(ROOT / ".env").items() if v is not None},
}
python = ROOT / ".venv/bin/python"
processes = []
stop = False


def shutdown(*_):
    global stop
    stop = True


def main():
    if not (ROOT / ".env").exists():
        raise SystemExit("Run make setup first.")
    dburl = env.get("DATABASE_URL", "")
    parsed = urlparse(dburl)
    if parsed.hostname in ("localhost", "127.0.0.1") and parsed.port == 55432:
        bindir = Path("/opt/homebrew/opt/postgresql@17/bin")
        if not bindir.exists():
            pg_config = shutil.which("pg_config")
            if not pg_config:
                raise SystemExit(
                    "Install PostgreSQL 17 or use Docker Compose. pg_config was not found."
                )
            bindir = Path(
                subprocess.check_output([pg_config, "--bindir"], text=True).strip()
            )
        pg = ROOT / ".local/pg"
        pg.parent.mkdir(exist_ok=True)
        if not (pg / "PG_VERSION").exists():
            subprocess.run(
                [
                    str(bindir / "initdb"),
                    "-D",
                    str(pg),
                    "-A",
                    "trust",
                    "--no-locale",
                    "-E",
                    "UTF8",
                ],
                check=True,
            )
        status = subprocess.run(
            [str(bindir / "pg_ctl"), "-D", str(pg), "status"],
            stdout=subprocess.DEVNULL,
            check=False,
        )
        if status.returncode:
            subprocess.run(
                [
                    str(bindir / "pg_ctl"),
                    "-D",
                    str(pg),
                    "-l",
                    str(ROOT / ".local/postgres.log"),
                    "-o",
                    "-p 55432 -h 127.0.0.1 -k /tmp -c timezone=UTC",
                    "start",
                ],
                check=True,
            )
        import psycopg
        from psycopg import sql

        with psycopg.connect(
            dburl.rsplit("/", 1)[0] + "/postgres", autocommit=True
        ) as c:
            for name in ("saipport", "saipport_lab"):
                if not c.execute(
                    "SELECT 1 FROM pg_database WHERE datname=%s", (name,)
                ).fetchone():
                    c.execute(
                        sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name))
                    )
    subprocess.run(
        [str(python), "-m", "app.migrate"], cwd=ROOT / "backend", env=env, check=True
    )
    commands = [
        (
            [
                str(python),
                "-m",
                "uvicorn",
                "app.sandbox:app",
                "--host",
                "127.0.0.1",
                "--port",
                "8001",
            ],
            ROOT / "backend",
        ),
        (
            [
                str(python),
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                "8000",
            ],
            ROOT / "backend",
        ),
        ([str(python), "-m", "app.worker"], ROOT / "backend"),
        (["npm", "run", "dev"], ROOT / "frontend"),
    ]
    try:
        for cmd, cwd in commands:
            processes.append(subprocess.Popen(cmd, cwd=cwd, env=env))
        print(
            "Workspace: http://127.0.0.1:5173 · API: http://127.0.0.1:8000", flush=True
        )
        while not stop:
            if any(p.poll() is not None for p in processes):
                raise SystemExit("A service exited. Check the output above.")
            time.sleep(0.4)
    finally:
        for p in reversed(processes):
            if p.poll() is None:
                p.terminate()
        for p in processes:
            try:
                p.wait(timeout=10)
            except subprocess.TimeoutExpired:
                p.kill()
        print(
            "Application services stopped. The isolated local PostgreSQL cluster is retained."
        )


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    main()
