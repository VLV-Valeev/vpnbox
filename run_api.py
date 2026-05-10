import uvicorn

from app.config import settings
from app.logging_config import setup_logging


def main() -> None:
    setup_logging()
    settings.require("bot_token")
    settings.require("database_url")
    settings.require("jwt_secret")

    uvicorn.run(
        "app.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
