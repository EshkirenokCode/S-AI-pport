"""Create private local configuration without printing credentials."""

import getpass
import secrets
from pathlib import Path

root = Path(__file__).resolve().parents[1]
path = root / ".env"
if path.exists():
    print("Existing .env preserved.")
else:
    user = getpass.getuser()
    path.write_text(
        "\n".join(
            [
                "APP_SECRET=" + secrets.token_hex(32),
                "SANDBOX_TOKEN=" + secrets.token_hex(32),
                "POSTGRES_PASSWORD=" + secrets.token_hex(20),
                "APP_DB_PASSWORD=" + secrets.token_hex(20),
                "LAB_DB_PASSWORD=" + secrets.token_hex(20),
                f"DATABASE_URL=postgresql://{user}@127.0.0.1:55432/saipport",
                f"SANDBOX_DATABASE_URL=postgresql://{user}@127.0.0.1:55432/saipport_lab",
                "APP_URL=http://127.0.0.1:8000",
                "SANDBOX_URL=http://127.0.0.1:8001",
                "MODEL_PROVIDER=deterministic",
                "TOOL_TRANSPORT=mcp",
                "OPENROUTER_API_KEY=",
                "OPENROUTER_MODEL=openrouter/free",
            ]
        )
        + "\n"
    )
    path.chmod(0o600)
    print("Created private .env. Add an OpenRouter key only for explicit live runs.")
