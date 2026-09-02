from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
from pathlib import Path
from fastapi_csrf_protect.exceptions import CsrfProtectError

from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from itsdangerous import Signer, BadSignature
from contextlib import asynccontextmanager
import secrets

from app.core.database import Base, engine
from app.core.config import settings
from app.core.exceptions import NotAuthenticated
from slowapi import _rate_limit_exceeded_handler
from pydantic import BaseModel
# =========================
# EXPLICIT MODEL REGISTRATION
# =========================
from app.models.user import User
from app.models.news import News
from app.models.video import Video
from app.models.music import Music
from app.models.comment import Comment
from app.models.subscriber import Subscriber
from app.models.category import Category
import os
#from app.models import user, video, music, news, comment, analytics, subscriber, stream_log, login_log, category, feed
# Routers
from app.routes import category as category_router
from app.routes.seo import router as seo_router
from app.routes.auth import router as auth_router
from app.routes.dashboard import router as dashboard_router
from app.routes.frontend import router as frontend_router
from app.routes.news import router as news_router
from app.routes.videos import router as videos_router
from app.routes.music import router as music_router
from app.routes.comments import router as comments_router
from app.routes.subscribers import router as subscribers_router
from app.routes.search import router as search_router
from app.routes.file import router as file_router
from app.routes.contact import router as contact_router
from slowapi import Limiter

# =========================
# CREATE DATABASE TABLES
# =========================

# =========================
# RATE LIMITER
# =========================
limiter = Limiter(key_func=get_remote_address)

# =========================
# CREATE FASTAPI APP
# ===================
@asynccontextmanager
async def lifespan(app: FastAPI):
    # This code executes ONCE when the master process fires up
    # 🛡️ SYSTEM SAFEGUARD: Check if this is the primary worker before rebuilding
    # Gunicorn/Uvicorn sets an internal worker context ID string variable
    worker_id = os.environ.get("FORK_ID") or os.environ.get("WORKER_ID") or "0"
    
    # Only allow the master process or first active worker to initialize schemas
    if worker_id in ("0", "1"):
        try:
            print("🚀 Master Worker initializing core production relational tables...")
            Base.metadata.create_all(bind=engine)
            
            # Place your exact "Feed table rebuild" function wrapper execution call right here:
            # rebuild_feed_table_indices(db) 
            print("✅ Relational tables and views successfully validated.")
        except Exception as e:
            print("ℹ️ Table initialization skipped or handled by parallel thread:", e)
            
    yield
    # Code here executes when the application fully shuts down
    print("Shutting down worker thread instance...")

# 2. Assign the lifespan
app = FastAPI(
title="TheRealBam Production Platform Engine",
    lifespan=lifespan 
)

app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)

# ==========================================
# NATIVE CSRF & SECURITY HEADERS MIDDLEWARE
# ==========================================
# ===================================
# NATIVE CSRF & SECURITY HEADERS MIDDLEWARE
# ==========================================
# Inside app/main.py

# =======================================
# NATIVE CSRF & SECURITY HEADERS MIDDLEWARE
# ==========================================
#csrf_signer = Signer(settings.SECRET_KEY)
csrf_signer = Signer(settings.SECRET_KEY)

@app.middleware("http")
async def secure_csrf_and_headers_middleware(request: Request, call_next):
    if request.method in ["POST", "PUT", "DELETE", "PATCH"]:
        cookie_token = request.cookies.get("csrf_token_cookie")
        header_token = request.headers.get("X-CSRF-Token")
        if header_token:
            if not cookie_token or not secrets.compare_digest(cookie_token, header_token):
                return JSONResponse(
                    status_code=403,
                    content={"detail": "CSRF validation failed: Token mismatch"}
                )
            try:
                csrf_signer.unsign(header_token)
            except BadSignature:
                return JSONResponse(
                    status_code=403,
                    content={"detail": "CSRF validation failed: Invalid signature"}
                )
    response = await call_next(request)

    # Apply Production Security Headers
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' "
        "https://code.jquery.com "
        "https://cdn.jsdelivr.net "
        "https://pagead2.googlesyndication.com "
        "https://googleads.g.doubleclick.net "
        "https://tpc.googlesyndication.com "
        "https://al5sm.com; "
        "style-src 'self' 'unsafe-inline' "
        "https://cdn.jsdelivr.net; "
        "img-src 'self' data: blob: https:; "
        "font-src 'self' data: https://cdn.jsdelivr.net; "
        "connect-src 'self' "
        "https://cdn.jsdelivr.net "
        "https://pagead2.googlesyndication.com "
        "https://googleads.g.doubleclick.net "
        "https://tpc.googlesyndication.com "
        "https://al5sm.com; "
        "media-src 'self' blob: https:; "
        "frame-src 'self' "
        "https://googleads.g.doubleclick.net "
        "https://tpc.googlesyndication.com "
        "https://al5sm.com; "
    )
    return response

# ==========================================
# GLOBAL APP STATE JINJA2 CSRF HELPER
# ==========================================
def render_with_csrf(templates_instance, request: Request, template_name: str, context: dict = None):
    """
    Global app helper that signs tokens and sets cookies safely.
    Works for any router file across the whole app.
    """
    if context is None:
        context = {}

    # Generate and sign the CSRF token using the global signer
    raw_token = secrets.token_hex(32)
    signed_token = csrf_signer.sign(raw_token.encode()).decode()

    # Bundle requirements into context
    context["request"] = request
    context["csrf_token"] = signed_token

    response = templates_instance.TemplateResponse(
        request=request,
        name=template_name, 
        context=context
    )
    response.set_cookie(
        "csrf_token_cookie",
        signed_token,
        httponly=True,
        samesite="lax",
        secure=settings.ENV == "production" # Enforces HTTPS automatically in production
    )
    return response

# Save the helper to app state so routers can pull it without importing main.py
app.state.render_with_csrf = render_with_csrf



# =========================
# MIDDLEWARE
# =========================
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,
    session_cookie=settings.SESSION_COOKIE,
    max_age=10800,
    same_site="lax",
    https_only=settings.ENV == "production"
)

# =========================
# RATE LIMIT HANDLER
# =========================
async def custom_rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Too many requests. Slow down."}
    )

app.add_exception_handler(RateLimitExceeded, custom_rate_limit_handler)

# =========================
# AUTH REDIRECT
# =========================
app.exception_handler(NotAuthenticated)
def auth_redirect_handler(request: Request, exc: NotAuthenticated):
    target_url = f"/{settings.LOGIN_GATEWAY_URL}?access_token={settings.ADMIN_GATEWAY_TOKEN}"

 #   return RedirectResponse(url="target_url", status_code=302)
    return RedirectResponse(
    url=f"/{settings.LOGIN_GATEWAY_URL}?access_token={settings.ADMIN_GATEWAY_TOKEN}",
    status_code=302
)
# =========================
# STATIC FILES
# =========================

@app.on_event("startup")
def create_upload_dirs():
    Path("app/static/uploads/music/covers").mkdir(parents=True, exist_ok=True)
    Path("app/static/uploads/music/audio").mkdir(parents=True, exist_ok=True)
    Path("app/static/uploads/videos").mkdir(parents=True, exist_ok=True)
    Path("app/static/uploads/news").mkdir(parents=True, exist_ok=True)

@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return FileResponse("app/static/favicon.ico")

@app.get("/ads.txt")
async def get_ads_txt():
    return FileResponse("app/static/ads.txt")

app.mount("/static", StaticFiles(directory="app/static"), name="static")
# =========================
# ROUTERS
# =========================
app.include_router(category_router.router)
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
app.include_router(file_router)
app.include_router(contact_router)
