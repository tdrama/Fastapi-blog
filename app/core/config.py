import os
from pydantic_settings import BaseSettings

import secrets


class Settings(BaseSettings):

    APP_NAME: str = "Blog Project"

    DEBUG: bool = True

    DATABASE_URL: str = "sqlite:///./blog.db"

    # =========================
    # SECURITY
    # =========================

    SECRET_KEY: str ="5c9038ed937f6392fb2d36de94043f48abdd015826bc4b2a27975694d2b16edf8178c143ee08ae400a654753359c84eb148a90237cc17b6eb63eb5549a1bf450"

    ALGORITHM: str = "HS256"

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    SESSION_COOKIE: str = "blog_session"

    SESSION_MAX_AGE: int = 60 * 60 * 24

    SECURE_COOKIES: bool = False

##verification email


    EMAIL_ADDRESS: str = "bamtboie@gmail.com"
    EMAIL_PASSWORD: str = "sflgcbalerbkrjka"

settings = Settings()
