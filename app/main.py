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

import secrets

from app.core.database import Base, engine
from app.core.config import settings
from app.core.exceptions import NotAuthenticated
from slowapi import _rate_limit_exceeded_handler
from pydantic import BaseModel

from app.models import user, video, music, news, comment, analytics, subscriber, stream_log, login_log, category
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
from slowapi import Limiter

# =========================
# CREATE DATABASE TABLES
# =========================
Base.metadata.create_all(bind=engine)

# =========================
# RATE LIMITER
# =========================
limiter = Limiter(key_func=get_remote_address)

# =========================
# CREATE FASTAPI APP
# =========================
app = FastAPI()

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
    # ✅ BYPASS CHECK: Allow the AJAX subscription endpoint to pass through safely without token checks
    if request.url.path == "/api/v1/subscribe-ajax":
        return await call_next(request)

    if request.method in ["POST", "PUT", "DELETE", "PATCH"]:
        cookie_token = request.cookies.get("csrf_token_cookie")
        form_token = request.headers.get("X-CSRF-Token")

        content_type = request.headers.get("content-type", "").lower()
        is_form_submission = (
            "application/x-www-form-urlencoded" in content_type
            or "multipart/form-data" in content_type
        )
                # ✅ FIXED: Caches the form data stream FIRST, then checks for tokens
 #       if is_form_submission:
#            try:
  #              form_data = await request.form()
   #             request._form = form_data
    #            
                # Only use form data fallback if the header token didn't exist
     #           if not form_token:
      #              form_token = form_data.get("csrf_token")
       #     except Exception:
        #        pass

        #token_to_validate = header_token or form_token

        if not form_token and is_form_submission:
            try:
                form_data = await request.form()
                form_token = form_data.get("csrf_token")

                request._form = form_data
            except Exception:
                form_token = None

        if not cookie_token:
            return JSONResponse(
                status_code=403,
                content={"detail": "CSRF validation failed: Missing token"}
            )
        if not form_token:
            return JSONResponse(
                status_code=403,
                content={"detail": "Missing csrf_token"}
            )
        if not secrets.compare_digest(cookie_token, form_token):
            return JSONResponse(
                status_code=403,
               # content={"detail": "CSRF validation failed: Token mismatch"}
                content={"detail": "Token mismatch","cookie": cookie_token, "form": form_token,}
            )

        try:
            csrf_signer.unsign(form_token)
        except BadSignature:
            return JSONResponse(
                status_code=403,
                content={"detail": "CSRF validation failed: Invalid signature"}
            )

    response = await call_next(request)

    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    # FIXED VARIANT: Grants explicit execution paths to TinyMCE assets while keeping scripts secure
    response.headers["Content-Security-Policy"] = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' 'unsafe-eval' "
    "https://code.jquery.com "
    "https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' "
    "https://cdn.jsdelivr.net; "
    "img-src 'self' data: blob: https:; "
    "font-src 'self' data: https://cdn.jsdelivr.net; "
    "connect-src 'self' http://127.0.0.1:8000 http://localhost:8000; "  
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
    return RedirectResponse(url="/auth/login", status_code=302)

# =========================
# STATIC FILES
# =========================

@app.on_event("startup")
def create_upload_dirs():
    Path("app/static/uploads/music/covers").mkdir(parents=True, exist_ok=True)
    Path("app/static/uploads/music/audio").mkdir(parents=True, exist_ok=True)
    Path("app/static/uploads/videos").mkdir(parents=True, exist_ok=True)
    Path("app/static/uploads/news").mkdir(parents=True, exist_ok=True)
#)
#

@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return FileResponse("app/static/favicon.ico")


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

