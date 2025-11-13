from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "drexapi"
    MONGODB_URI: str = "mongodb://mongo:27017/drex"
    MONGO_DB: str = "drex"
    DEBUG: bool = True

    # Pydantic v2 settings config
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8-sig",  # handle BOM if present
        case_sensitive=False,             # accept lower/upper case env keys
        extra="ignore",                  # ignore unknown keys in .env
    )


settings = Settings()
