from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Setup placeholder defaults. Pydantic will overwrite these 
    # automatically with the matching values inside your local .env file!
    SECRET_KEY: str = "fallback_weak_development_key"
    LOGIN_GATEWAY_URL: str = "login"
    REGISTER_GATEWAY_URL: str = "register"
    ADMIN_GATEWAY_TOKEN: str = "default_token"
    SESSION_COOKIE: str = "session_tracker"
    ENV: str = "development"

    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
