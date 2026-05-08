from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
    )

    strava_client_id: int | None = None
    strava_client_secret: str | None = None
    strava_db_path: str = "./data/strava.db"
    log_level: str = "INFO"
    log_path: str = "./logs/strava-mcp.log"


settings = Settings()
