from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import RedirectResponse
from fastapi.responses import FileResponse
from app.core.database import Base, engine
from app.core.config import settings
from app.core.exceptions import NotAuthenticated

# =========================
# IMPORT MODELS
# =========================
from app.routes.seo import router as seo_router

from app.models.login_log import LoginLog
from app.models.user import User
from app.models.video import Video
from app.models.music import Music
from app.models.news import News
from app.models.comment import Comment
from app.models.analytics import Analytics
from app.models.subscriber import Subscriber
from app.models.stream_log import StreamLog
from app.routes import category
# =========================
# CREATE DATABASE TABLES
# =========================

Base.metadata.create_all(bind=engine)

# =========================
# CREATE FASTAPI APP
# =========================

app = FastAPI()

# =========================
# SECURITY HEADERS
# =========================

@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)

    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["X-XSS-Protection"] = "1; mode=block"

    return response

# =========================
# SESSION MIDDLEWARE (FIXED)
# =========================

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,
    session_cookie=settings.SESSION_COOKIE,
    max_age=10800,
    same_site="lax",
    https_only=False  # ⚠️ MUST be False for localhost/Termux
)

# =========================
# DASHBOARD PROTECTION
# =========================


@app.exception_handler(NotAuthenticated)
def auth_redirect_handler(request: Request, exc: NotAuthenticated):
    return RedirectResponse(url="/auth/login", status_code=302)
# =========================
# STATIC FILES
# =========================

app.mount(
    "/static",
    StaticFiles(directory="app/static"),
    name="static"
)
# =========================
# FAVICON
# =========================

@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return FileResponse(
        "app/static/favicon.ico"
    )


# =========================
# ROBOTS
# =========================

@app.get("/robots.txt", include_in_schema=False)
def robots():
    return FileResponse(
        "app/static/robots.txt",
        media_type="text/plain"
    )


# =========================
# SITEMAP
# =========================

@app.get("/sitemap.xml", include_in_schema=False)
def sitemap():
    return FileResponse(
        "app/static/sitemap.xml",
        media_type="application/xml"
    )
# =========================
# ROUTERS
# =========================

from app.routes.auth import router as auth_router
from app.routes.dashboard import router as dashboard_router
from app.routes.frontend import router as frontend_router
from app.routes.news import router as news_router
from app.routes.videos import router as videos_router
from app.routes.music import router as music_router
from app.routes.comments import router as comments_router
from app.routes.subscribers import router as subscribers_router
from app.routes.search import router as search_router
app.include_router(category.router)
app.include_router(seo_router)
app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(frontend_router)
app.include_router(news_router)
app.include_router(videos_router)
app.include_router(music_router)
app.include_router(comments_router)
app.include_router(subscribers_router)
app.include_router(search_router)
