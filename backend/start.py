import asyncio
import os

from backend.config import get_settings
from backend.db.migrate_startup import run_startup_migrations


def main() -> None:
    settings = get_settings()
    settings.validate_runtime()

    if settings.AUTO_APPLY_MIGRATIONS:
        asyncio.run(run_startup_migrations())

    os.execvp(
        "uvicorn",
        ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"],
    )


if __name__ == "__main__":
    main()
