import os
import hashlib
import re
from fastapi import (
    APIRouter,
    Request,
    Depends,
    Query,
    HTTPException,
    Form)
from starlette.datastructures import UploadFile
from app.core.dependencies import get_current_user
from app.utils.file import safe_file_path
from app.core.limiter import limiter
from sqlalchemy import func, text, union_all, select, desc,literal
from fastapi.responses import(RedirectResponse,HTMLResponse,JSONResponse,FileResponse)
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload  # 🔒 FIXED: joinedload must be explicitly declared here!
from app.models.stream_log import StreamLog
from app.core.database import get_db
from datetime import datetime
 #  ✅ FIXED: Import added here
import httpx
from fastapi_csrf_protect import CsrfProtect
import os.path
from app.models.news import News
from app.models.video import Video
from app.models.music import Music
from app.models.comment import Comment
from app.models.user import User

router = APIRouter(tags=["Public Activity Feed"])

templates = Jinja2Templates( directory="app/templates" )
BASE_UPLOAD_DIR = os.path.abspath("app/static/uploads")


@router.get("/")
@limiter.limit("60/minute")
async def home(
    request: Request,
    page: int = Query(default=1, ge=1),
    db: Session = Depends(get_db)
):
    per_page = 6
    feed_per_page = 9

    skip = (page - 1) * per_page
    feed_offset = (page - 1) * feed_per_page

    # =========================================
    # 1. FEATURED NEWS
    # =========================================

    news = (
        db.query(News)
        .order_by(desc(News.created_at))
        .offset(skip)
        .limit(per_page)
        .all()
    )
    videos = (
        db.query(Video)
        .order_by(desc(Video.created_at))
        .limit(6)
        .all()
    )
    # =========================================
    # 2. FEATURED MUSIC
    # =========================================

    musics = (
        db.query(Music)
        .order_by(desc(Music.created_at))
        .limit(6)
        .all()
    )

    # =========================================
    # 3. TRENDING NEWS
    # =========================================

    trending_news = (
        db.query(News)
        .order_by(
            desc(News.views),
            desc(News.created_at)
        )
        .limit(5)
        .all()
    )
    # =========================================
    # 4. TRENDING MUSIC
    # =========================================

    trending_musics = (
        db.query(Music)
        .order_by(
            desc(Music.views),
            desc(Music.created_at)
        )
        .limit(5)
        .all()
    )

    # =========================================
    # 5. CHECK MUSIC FILES
    # =========================================

    for m in musics:

        if m.music_file:

            file_path = os.path.join(
                BASE_UPLOAD_DIR,
                m.music_file.lstrip("/")
            )

            m.file_exists = os.path.exists(file_path)

        else:

            m.file_exists = False

    # =========================================
    # 6. HOMEPAGE ACTIVITY FEED
    #    VIDEOS EXCLUDED COMPLETELY
    # =========================================

    stmt = text("""
        SELECT
            id,
            title,
            slug,
            content,
            media,
            views,
            created_at,
            type,
            video_file,
            music_file
        FROM feed
        WHERE type IN ('news', 'music')
        ORDER BY created_at DESC, id DESC
        LIMIT :limit OFFSET :offset
    """)

    try:

        raw_rows = (
            db.execute(
                stmt,
                {
                    "limit": feed_per_page,
                    "offset": feed_offset
                }
            )
            .mappings()
            .all()
        )

    except Exception as e:

        print("Homepage Feed Query View Error:", e)

        raw_rows = []

    # =========================================
    # 7. CONVERT FEED ROWS
    # =========================================

    initial_feed = []

    class StreamItem:

        def __init__(self, data_map):

            self.id = data_map["id"]

            self.type = data_map["type"]

            self.title = data_map["title"]

            self.slug = data_map["slug"]

            self.content = data_map["content"]

            self.image = data_map["media"]

            self.views = data_map["views"]

            self.created_at = data_map["created_at"]

            # Convert SQLite timestamp
            if isinstance(self.created_at, str):

                try:

                    self.created_at = datetime.strptime(
                        self.created_at,
                        "%Y-%m-%d %H:%M:%S"
                    )

                except ValueError:

                    pass

            # Kept only for compatibility.
            # They will not be rendered because
            # the SQL query excludes videos.
            self.video_file = None

            self.music_file = data_map["music_file"]

            self.embed_url = data_map.get("embed_url")

    # =========================================
    # 8. BUILD FEED
    # =========================================

    for row in raw_rows:

        # Extra protection:
        # NEVER allow a video row into the frontend.
        if row["type"] not in ("news", "music"):
            continue

        initial_feed.append(
            StreamItem(row)
        )

    # =========================================
    # 9. HOMEPAGE PAGINATION
    # =========================================

    total_news = (
        db.query(func.count(News.id))
        .scalar()
    )

    total_pages = (
        total_news + per_page - 1
    ) // per_page

    # =========================================
    # 10. RENDER HOMEPAGE
    # =========================================

    render_with_csrf = request.app.state.render_with_csrf

    return render_with_csrf(
        templates_instance=templates,
        request=request,
        template_name="frontend/index.html",
        context={
            "news": news,
            "musics": musics,

            "trending_news": trending_news,
            "trending_musics": trending_musics,
            "videos": videos,
            "feed": initial_feed,

            "page": page,
            "total_pages": total_pages,
            # Open Graph fallback for homepage
            "meta_title": "BAM-Tech — Premium News, Music & Videos",
            "meta_description": "Your ultimate destination for the latest news, premium music, and viral videos.",
            "meta_image": "https://therealbam.com/static/og-image.png"
        }
    )
@router.get(
    "/feed/stream",
    response_class=HTMLResponse,
    name="get_infinite_feed_stream"
)
async def get_infinite_feed_stream(
    request: Request,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=6, ge=1, le=24),
    db: Session = Depends(get_db)
):
    offset = (page - 1) * limit

    # =========================================
    # 1. FETCH ONLY NEWS AND MUSIC
    # =========================================

    stmt = text("""
        SELECT
            id,
            title,
            slug,
            content,
            media,
            views,
            created_at,
            type,
            video_file,
            music_file
        FROM feed
        WHERE type IN ('news', 'music')
        ORDER BY created_at DESC, id DESC
        LIMIT :limit OFFSET :offset
    """)

    try:

        rows = (
            db.execute(
                stmt,
                {
                    "limit": limit,
                    "offset": offset
                }
            )
            .mappings()
            .all()
        )

    except Exception as e:

        print("Feed Stream Error:", e)

        raise HTTPException(
            status_code=500,
            detail="Unable to load feed."
        )

    # =========================================
    # 2. NO MORE RESULTS
    # =========================================

    if not rows:
        return HTMLResponse("")

    # =========================================
    # 3. TEMPLATE OBJECT
    # =========================================

    feed = []

    class StreamItem:

        def __init__(
            self,
            data_map,
            parsed_date
        ):

            self.id = data_map["id"]

            self.type = data_map["type"]

            self.title = data_map["title"]

            self.slug = data_map["slug"]

            self.content = data_map["content"]

            self.image = data_map["media"]

            self.views = data_map["views"]

            self.created_at = parsed_date

            # Videos are deliberately disabled.
            self.video_file = None

            self.music_file = data_map["music_file"]

            self.embed_url = data_map.get("embed_url")

    # =========================================
    # 4. CONVERT DATABASE ROWS
    # =========================================

    for row in rows:

        # Final protection.
        # Only news and music are allowed.
        if row["type"] not in ("news", "music"):
            continue

        created_at = row["created_at"]

        if isinstance(created_at, str):

            try:

                created_at = datetime.strptime(
                    created_at,
                    "%Y-%m-%d %H:%M:%S"
                )

            except ValueError:

                pass

        feed.append(
            StreamItem(
                row,
                created_at
            )
        )

    # =========================================
    # 5. RENDER LOAD MORE
    # =========================================

    render_with_csrf = request.app.state.render_with_csrf

    return render_with_csrf(
        templates_instance=templates,
        request=request,
        template_name="frontend/load_more.html",
        context={
            "feed": feed
        }
    )

# =========================================
# NEWS PAGE
# =========================================

@router.get("/news")
def news_page(
    request: Request,
    db: Session = Depends(get_db)
):
    news = (
        db.query(News)
        .order_by(News.id.desc())
        .all()
    )

    return request.app.state.render_with_csrf(
        templates_instance=templates,
        request=request,
        template_name="frontend/news.html",
        context={
            "news_list": news
        }
    )


# =========================================
# NEWS DETAIL
# =========================================
# ====================================================
# 👑 HIGH-PERFORMANCE DYNAMIC NEWS DETAIL ROUTER WITH DEDUPLICATED VIEWS
# ====================================================
@router.get("/news/{identifier}")
async def news_detail(
    identifier: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    📰 SECURE NEWS DETAIL CONTROLLER

    Features:
    - Numeric ID -> permanent redirect to slug
    - Slug-based lookup
    - Eager-load comments relationship
    - 404 handling
    - Privacy-preserving IP hashing
    - Deduplicated view tracking
    - Defensive transaction handling
    - Secure Open Graph image URL construction
    - Safe metadata generation
    """

    # ============================================================
    # PHASE 0: INPUT VALIDATION
    # ============================================================

    identifier = identifier.strip()

    if not identifier:
        raise HTTPException(
            status_code=404,
            detail="News not found",
        )

    # Prevent unnecessarily large route parameters
    if len(identifier) > 200:
        raise HTTPException(
            status_code=404,
            detail="News not found",
        )

    # ============================================================
    # PHASE 1: NEWS LOOKUP
    # ============================================================

    news = None

    if identifier.isdigit():

        # Avoid absurdly large integer conversion
        try:
            news_id = int(identifier)
        except ValueError:
            raise HTTPException(
                status_code=404,
                detail="News not found",
            )

        # Database IDs should be positive
        if news_id <= 0:
            raise HTTPException(
                status_code=404,
                detail="News not found",
            )

        news = (
            db.query(News)
            .options(joinedload(News.comments))
            .filter(News.id == news_id)
            .first()
        )

        # Permanent redirect numeric URL -> canonical slug URL
        if news and getattr(news, "slug", None):

            slug = str(news.slug).strip()

            if slug:
                return RedirectResponse(
                    url=f"/news/{slug}",
                    status_code=301,
                )

    else:

        # Slug lookup
        news = (
            db.query(News)
            .options(joinedload(News.comments))
            .filter(News.slug == identifier)
            .first()
        )

    # ============================================================
    # PHASE 2: ENTITY BOUNDARY
    # ============================================================

    if not news:
        raise HTTPException(
            status_code=404,
            detail="News not found",
        )

    # ============================================================
    # PHASE 3: COMMENTS
    # ============================================================

    comments = (
        db.query(Comment)
        .filter(Comment.news_id == news.id)
        .order_by(Comment.id.desc())
        .limit(100)
        .all()
    )

    # ============================================================
    # PHASE 4: RELATED NEWS
    # ============================================================

    related_news = (
        db.query(News)
        .filter(News.id != news.id)
        .order_by(News.id.desc())
        .limit(5)
        .all()
    )

    # ============================================================
    # PHASE 5: SECURE CLIENT IP RESOLUTION
    # ============================================================
    #
    # IMPORTANT:
    # Do not blindly trust X-Forwarded-For from arbitrary clients.
    #
    # Cloudflare normally supplies CF-Connecting-IP when traffic
    # reaches your origin through Cloudflare.
    # ============================================================

    client_ip = None

    cf_ip = request.headers.get("CF-Connecting-IP")

    if cf_ip:
        client_ip = cf_ip.strip()

    else:
        real_ip = request.headers.get("X-Real-IP")

        if real_ip:
            client_ip = real_ip.strip()

        elif request.client:
            client_ip = request.client.host

    if not client_ip:
        client_ip = "unknown"

    # Only use the first value if a proxy supplies a comma-separated
    # address list.
    client_ip = client_ip.split(",")[0].strip()

    # Defensive maximum length
    client_ip = client_ip[:128]

    # ============================================================
    # PHASE 6: PRIVACY-PRESERVING IP HASH
    # ============================================================

    hashed_ip = hashlib.sha256(
        client_ip.encode("utf-8")
    ).hexdigest()

    # ============================================================
    # PHASE 7: SESSION USER
    # ============================================================

    session_user_id = request.session.get("user_id")

    # Defensive normalization
    if session_user_id is not None:
        try:
            session_user_id = int(session_user_id)
        except (TypeError, ValueError):
            session_user_id = None

    # ============================================================
    # PHASE 8: VIEW DEDUPLICATION
    # ============================================================

    view_query = (
        db.query(StreamLog)
        .filter(
            StreamLog.content_type == "news_view",
            StreamLog.content_id == news.id,
        )
    )

    if session_user_id:

        already_viewed = (
            view_query
            .filter(
                (StreamLog.ip_address == hashed_ip)
                | (StreamLog.user_id == session_user_id)
            )
            .first()
        )

    else:

        already_viewed = (
            view_query
            .filter(StreamLog.ip_address == hashed_ip)
            .first()
        )

    # ============================================================
    # PHASE 9: ATOMIC-STYLE VIEW UPDATE
    # ============================================================

    if not already_viewed:

        try:

            # Increment view counter
            news.views = (news.views or 0) + 1

            log = StreamLog(
                user_id=session_user_id,
                content_type="news_view",
                content_id=news.id,
                ip_address=hashed_ip,
            )

            db.add(log)
            db.commit()

            # Refresh database state after successful commit
            db.refresh(news)

        except Exception as exc:

            db.rollback()

            # Do not break the public news page because analytics failed.
            print(
                f"[Analytics] Failed to log news view "
                f"for ID #{news.id}: {exc}"
            )

    # ============================================================
    # PHASE 10: SECURE DYNAMIC OPEN GRAPH IMAGE
    # ============================================================

    fallback_image = (
        "https://therealbam.com/static/og-image.png"
    )

    meta_image = fallback_image

    if news.image:

        image_path = str(news.image).strip()

        if image_path:

            # ----------------------------------------------------
            # Absolute URL
            # ----------------------------------------------------

            if image_path.startswith(
                ("http://", "https://")
            ):
                meta_image = image_path

            # ----------------------------------------------------
            # /static/...
            # ----------------------------------------------------

            elif image_path.startswith("/static/"):

                meta_image = (
                    f"https://therealbam.com"
                    f"{image_path}"
                )

            # ----------------------------------------------------
            # static/...
            # ----------------------------------------------------

            elif image_path.startswith("static/"):

                meta_image = (
                    f"https://therealbam.com/"
                    f"{image_path}"
                )

            # ----------------------------------------------------
            # Uploaded image path
            # ----------------------------------------------------

            else:

                clean_image_path = image_path.lstrip("/")

                meta_image = (
                    "https://therealbam.com/"
                    "static/uploads/"
                    f"{clean_image_path}"
                )

    # ============================================================
    # PHASE 11: DEFENSIVE METADATA
    # ============================================================

    meta_title = (
        str(news.title).strip()
        if news.title
        else "BAM-Tech"
    )

    if news.content:

        # Prevent enormous metadata values
        meta_description = str(
            news.content
        ).strip()[:160]

    else:

        meta_description = (
            "Read the latest news and technology "
            "updates live on BAM-Tech."
        )

    # ============================================================
    # PHASE 12: SECURE TEMPLATE RESPONSE
    # ============================================================

    return request.app.state.render_with_csrf(
        templates_instance=templates,
        request=request,
        template_name="frontend/news_detail.html",
        context={
            "news": news,
            "comments": comments,
            "related_news": related_news,
            "meta_title": meta_title,
            "meta_description": meta_description,
            "meta_image": meta_image,
        },
    )
# =========================================
# VIDEOS PAGE
# =========================================

@router.get("/videos")
async def videos_page(
    request: Request,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=12, ge=1, le=100),
    db: Session = Depends(get_db)
):
    offset = (page - 1) * limit

    videos = (
        db.query(Video)
        .order_by(Video.id.desc())
        .all()
    )

    return request.app.state.render_with_csrf(
        templates_instance=templates,
        request=request,
        template_name="frontend/videos.html",
        context={
            "videos": videos
        }
    )
# =========================================
# VIDEO DOWNLOAD
# =========================================
@router.get("/video/download/{slug}")
@limiter.limit("5/minute")
async def download_video(
    request: Request,
    slug: str,
    db: Session = Depends(get_db)
):
    video = (
        db.query(Video)
        .filter(Video.slug == slug.strip())
        .first()
    )

    if not video:
        raise HTTPException(
            status_code=404,
            detail="Video not found"
        )

    if not video.video_file:
        raise HTTPException(
            status_code=404,
            detail="Video file not found"
        )

    relative_path = video.video_file.replace("/static/", "")
    file_path = safe_file_path(relative_path)

    if not file_path.is_file():
        raise HTTPException(
            status_code=404,
            detail="Video file does not exist"
        )

    def safe_download_filename(value: str) -> str:
        value = re.sub(r'[\\/:*?"<>|]+', '', value)
        value = re.sub(r'\s+', ' ', value)
        return value.strip()

    title = safe_download_filename(
        video.title or "Untitled Video"
    )

    download_filename = f"{title}.mp4"

    video.downloads = (video.downloads or 0) + 1
    db.commit()

    return FileResponse(
        path=file_path,
        filename=download_filename,
        media_type="video/mp4"
    )
# =====================================================================
# 🔒 2. SECURE HIDDEN FILE STREAM DELIVERY ENDPOINT
# =====================================================================
@router.get("/secure/direct/fetch/stream/{folder}/{filename}")
async def serve_raw_file_binary(folder: str, filename: str):
    # Security block: Only allow downloads originating from within your valid asset trees
    if folder not in ["videos", "music", "audio"]:
        raise HTTPException(status_code=403, detail="Access denied.")
    
    # Resolve physical absolute disk storage maps cleanly
    if folder == "audio":
        physical_disk_path = os.path.join("/var/www/Fastapi-blog/app/static/uploads/music/audio", filename)
    else:
        physical_disk_path = os.path.join("/var/www/Fastapi-blog/app/static/uploads", folder, filename)
        
    if not os.path.exists(physical_disk_path):
        raise HTTPException(status_code=404, detail="The selected media file could not be located on disk.")
        
    # Deliver the pure file stream binary asset straight to the smartphone clients
    return FileResponse(
        path=physical_disk_path,
        filename=filename,
        media_type="application/octet-stream"
    )


# =========================================
# 🎬 VIDEO DETAIL PAGE — SLUG ONLY
# =========================================
# ====================================================
# 🎥 HARDENED VIDEO DETAIL ROUTER WITH FRAUD-PROOF UNIQUE VIEW LOCK
# ====================================================
@router.get("/videos/{slug}", response_class=HTMLResponse, name="video_detail")
@limiter.limit("40/minute")
async def video_detail(
    slug: str,
    request: Request,
    page: int = Query(default=1, ge=1),
    db: Session = Depends(get_db)
):
    """
    🎞️ CINEMATIC VIDEO CONTROLLER:
    Enforces user-isolated view checking via IP-hashing, maintains
    comment pagination, and binds metadata tags for link previews.
    """

    slug = slug.strip()

    video = (
        db.query(Video)
        .filter(Video.slug == slug)
        .first()
    )

    if not video:
        raise HTTPException(
            status_code=404,
            detail="The requested video cannot be found."
        )

    # ============================================================
    # PAGINATE VIDEO COMMENTS
    # ============================================================

    comments_per_page = 10
    offset = (page - 1) * comments_per_page

    comments_query = (
        db.query(Comment)
        .filter(Comment.video_id == video.id)
        .order_by(desc(Comment.id))
    )

    total_comments_count = comments_query.count()

    paginated_comments = (
        comments_query
        .offset(offset)
        .limit(comments_per_page)
        .all()
    )

    total_pages = (
        (total_comments_count + comments_per_page - 1)
        // comments_per_page
    )

    # ============================================================
    # 🔒 PHASE 1: HARDENED IP RESOLUTION & HASHING
    # ============================================================

    ip_raw = (
        request.headers.get("CF-Connecting-IP")
        or request.headers.get("X-Real-IP")
        or (request.client.host if request.client else "unknown")
    )

    ip_str = str(ip_raw).split(",")[0].strip()[:128]

    hashed_ip = hashlib.sha256(
        ip_str.encode("utf-8")
    ).hexdigest()

    # ============================================================
    # 🔒 PHASE 2: DEFENSIVE VIEW LEDGER QUERY
    # ============================================================

    session_user_id = request.session.get("user_id")

    if session_user_id is not None:
        try:
            session_user_id = int(session_user_id)
        except (TypeError, ValueError):
            session_user_id = None

    view_query = (
        db.query(StreamLog)
        .filter(
            StreamLog.content_type == "video_view",
            StreamLog.content_id == video.id
        )
    )

    if session_user_id:
        already_viewed = (
            view_query
            .filter(
                (StreamLog.ip_address == hashed_ip)
                | (StreamLog.user_id == session_user_id)
            )
            .first()
        )
    else:
        already_viewed = (
            view_query
            .filter(
                StreamLog.ip_address == hashed_ip
            )
            .first()
        )

    # ============================================================
    # 🔒 PHASE 3: UNIQUE VIEW INCREMENTATION
    # ============================================================

    if not already_viewed:

        try:
            video.views = (video.views or 0) + 1

            log = StreamLog(
                user_id=session_user_id,
                content_type="video_view",
                content_id=video.id,
                ip_address=hashed_ip
            )

            db.add(log)
            db.commit()

            db.refresh(video)

            print(
                f"[Analytics] Successfully logged unique "
                f"video view for ID: #{video.id}"
            )

        except Exception as exc:

            db.rollback()

            # Analytics failure should not break the video page.
            print(
                f"[Analytics] Failed to log video view "
                f"for ID #{video.id}: {exc}"
            )

    # ============================================================
    # 🔒 PHASE 4: SECURE DYNAMIC OPEN GRAPH IMAGE
    # ============================================================

    fallback_image = (
        "https://therealbam.com/static/og-image.png"
    )

    meta_image = fallback_image

    if video.thumbnail:

        thumbnail_path = str(
            video.thumbnail
        ).strip()

        if thumbnail_path.startswith(
            ("http://", "https://")
        ):

            meta_image = thumbnail_path

        elif thumbnail_path.startswith(
            "/static/"
        ):

            meta_image = (
                f"https://therealbam.com"
                f"{thumbnail_path}"
            )

        elif thumbnail_path.startswith(
            "static/"
        ):

            meta_image = (
                f"https://therealbam.com/"
                f"{thumbnail_path}"
            )

        else:

            meta_image = (
                "https://therealbam.com/"
                "static/uploads/"
                f"{thumbnail_path.lstrip('/')}"
            )

    # ============================================================
    # 🔒 PHASE 5: SAFE SEO METADATA
    # ============================================================

    meta_title = (
        str(video.title).strip()
        if video.title
        else "BAM-Tech"
    )

    meta_description = (
        str(video.description).strip()[:160]
        if video.description
        else (
            "Watch the latest premium video releases "
            "and viral media tracks live on BAM-Tech."
        )
    )

    # ============================================================
    # PHASE 6: RENDER
    # ============================================================

    render_with_csrf = (
        request.app.state.render_with_csrf
    )

    return render_with_csrf(
        templates_instance=templates,
        request=request,
        template_name="frontend/video_detail.html",
        context={
            "video": video,
            "comments": paginated_comments,
            "current_page": page,
            "total_pages": max(total_pages, 1),
            "meta_title": meta_title,
            "meta_description": meta_description,
            "meta_image": meta_image,
        }
    )

# =========================================
# ADD VIDEO COMMENT
# =========================================

@router.post("/video/comment/{video_id}")
async def add_video_comment(
    video_id: int,
    request: Request,
    content: str = Form(...),
    db: Session = Depends(get_db)
):
    # =========================================
    # 1. VERIFY VIDEO EXISTS
    # =========================================

    video = (
        db.query(Video)
        .filter(Video.id == video_id)
        .first()
    )

    if not video:
        raise HTTPException(
            status_code=404,
            detail="Target video record not found."
        )

    # =========================================
    # 2. CLEAN COMMENT
    # =========================================

    content_clean = content.strip()

    if not content_clean:
        raise HTTPException(
            status_code=400,
            detail="Comment content cannot be empty."
        )

    # =========================================
    # 3. SAVE COMMENT
    # =========================================

    try:
        new_comment = Comment(
            video_id=video_id,
            name="Anonymous",
            content=content_clean
        )

        db.add(new_comment)
        db.commit()

    except Exception as e:
        db.rollback()

        print(
            "Video Comment Database Error:",
            e
        )

        raise HTTPException(
            status_code=500,
            detail="Database write action failure during comment saving."
        )

    # =========================================
    # 4. BROWSER FALLBACK
    # =========================================

    if (
        "application/x-www-form-urlencoded"
        in request.headers.get(
            "content-type",
            ""
        ).lower()
    ):
        return RedirectResponse(
            url=f"/videos/{video.slug}",
            status_code=303
        )

    # =========================================
    # 5. AJAX RESPONSE
    # =========================================

    return JSONResponse(
        status_code=201,
        content={
            "success": True,
            "detail": "Public user comment registered successfully."
        }
    )

# =========================================
# MUSIC PAGE
# =========================================

@router.get("/music")
async def music_page(
    request: Request,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=12, ge=1, le=100),
    db: Session = Depends(get_db)
):
    offset = (page - 1) * limit

    musics = (
        db.query(Music)
        .order_by(Music.id.desc())
        .all()
    )

    return request.app.state.render_with_csrf(
        templates_instance=templates,
        request=request,
        template_name="frontend/music.html",
        context={
            "musics": musics,
            "current_page": page,
            "limit": limit
        }
    )


# =========================================
# MUSIC DETAIL
# =========================================

# ====================================================
# 🎵 HARDENED MUSIC DETAIL ROUTER WITH FRAUD-PROOF UNIQUE VIEW LOCK
# ====================================================
@router.get("/music/{slug}")
async def music_detail(
    slug: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    🎵 AUDIO DETAIL CONTROLLER:
    Enforces user-isolated unique view logging, fetches comments and 
    related tracks, and attaches metadata layers for clear sharing previews.
    """
    music = db.query(Music).filter(Music.slug == slug).first()

    if not music:
        raise HTTPException(
            status_code=404,
            detail="Music not found"
        )

    comments = db.query(Comment).filter(Comment.music_id == music.id).order_by(Comment.id.desc()).all()
    related_music = db.query(Music).filter(Music.id != music.id).order_by(Music.id.desc()).limit(5).all()

    # 🔒 PHASE 1: HARDENED DEDUPLICATED IP RESOLUTION & HASHING
    ip_raw = request.headers.get("CF-Connecting-IP") or request.headers.get("X-Real-IP") or request.client.host
    ip_str = str(ip_raw).split(",")[0].strip()
    hashed_ip = hashlib.sha256(ip_str.encode("utf-8")).hexdigest()

    # 🔒 PHASE 2: DEFENSIVE LEDGER QUERY BOUNDARIES
    session_user_id = request.session.get("user_id")
    view_query = db.query(StreamLog).filter(
        StreamLog.content_type == "music_view",
        StreamLog.content_id == music.id
    )
    
    if session_user_id:
        already_viewed = view_query.filter(
            (StreamLog.ip_address == hashed_ip) | (StreamLog.user_id == session_user_id)
        ).first()
    else:
        already_viewed = view_query.filter(StreamLog.ip_address == hashed_ip).first()

    # 🔒 PHASE 3: IMMUTABLE VIEW INCREMENTATION LOCK
    if not already_viewed:
        music.views = (music.views or 0) + 1
        log = StreamLog(
            user_id=session_user_id,
            content_type="music_view",
            content_id=music.id,
            ip_address=hashed_ip
        )
        db.add(log)
        try:
            db.commit()
            print(f"[Analytics] Successfully logged unique music view for ID: #{music.id}")
        except Exception:
            db.rollback()
    else:
        db.refresh(music)

    # 🔒 PHASE 4: SECURE DYNAMIC LINK PREVIEW ROUTING METRICS
    if music.cover_image:
        meta_image = f"https://therealbam.com/static/uploads/{str(music.cover_image).lstrip('/')}"

    else:
        # 🔒 FIXED: Points directly to your real image file on disk instead of a raw domain URL
        meta_image = "https://therealbam.com/static/og-image.png"

    return request.app.state.render_with_csrf(
        templates_instance=templates,
        request=request,
        template_name="frontend/music_detail.html",
        context={
            "music": music,
            "comments": comments,
            "related_music": related_music,
            "meta_title": music.title,
            "meta_description": (
                music.description[:160]
                if music.description
                else "Listen to the latest premium audio tracks live on BAM-Tech."
            ),
            "meta_image": meta_image
        }
    )

# =========================================
# MUSIC DOWNLOAD ROUTE
# =========================================
@router.get("/music/download/{slug}")
@limiter.limit("5/minute")
async def download_music(
    request: Request,
    slug: str,
    db: Session = Depends(get_db)
):
    music = (
        db.query(Music)
        .filter(Music.slug == slug.strip())
        .first()
    )

    if not music:
        raise HTTPException(
            status_code=404,
            detail="Music not found"
        )

    if not music.music_file:
        raise HTTPException(
            status_code=404,
            detail="Music file not found"
        )

    relative_path = music.music_file.replace("/static/", "")
    file_path = safe_file_path(relative_path)

    if not file_path.is_file():
        raise HTTPException(
            status_code=404,
            detail="Audio file does not exist"
        )

    def safe_download_filename(value: str) -> str:
        value = re.sub(r'[\\/:*?"<>|]+', '', value)
        value = re.sub(r'\s+', ' ', value)
        return value.strip()

    artist = safe_download_filename(
        music.artist or "Unknown Artist"
    )

    title = safe_download_filename(
        music.title or "Untitled"
    )

    download_filename = f"{artist} - {title}.mp3"

    music.downloads = (music.downloads or 0) + 1
    db.commit()

    return FileResponse(
        path=file_path,
        filename=download_filename,
        media_type="audio/mpeg"
    )

# =========================================
# ADD MUSIC COMMENT
# =========================================

@router.post("/music/{music_id}/comment")
@limiter.limit("5/minute")
async def add_music_comment(
    request: Request,
    music_id: int,
    name: str = Form(...),
    content: str = Form(...),
    db: Session = Depends(get_db)
):
    music = (
        db.query(Music)
        .filter(Music.id == music_id)
        .first()
    )

    if not music:
        raise HTTPException(
            status_code=404,
            detail="Music not found"
        )

    comments = (
        db.query(Comment)
        .filter(Comment.music_id == music_id)
        .order_by(Comment.id.desc())
        .all()
    )

    related_music = (
        db.query(Music)
        .filter(Music.id != music_id)
        .order_by(Music.id.desc())
        .limit(5)
        .all()
    )

    new_comment = Comment(
        name=name,
        content=content,
        music_id=music_id
    )

    db.add(new_comment)
    db.commit()

    # Include the newly added comment in the returned page
    comments = (
        db.query(Comment)
        .filter(Comment.music_id == music_id)
        .order_by(Comment.id.desc())
        .all()
    )

    return request.app.state.render_with_csrf(
        templates_instance=templates,
        request=request,
        template_name="frontend/music_detail.html",
        context={
            "music": music,
            "comments": comments,
            "related_music": related_music,
            "meta_title": music.title,
            "meta_description": (
                music.description[:160]
                if music.description
                else ""
            ),
            "meta_image": getattr(
                music,
                "image",
                getattr(
                    music,
                    "cover_image",
                    "/static/images/default_audio.png"
                )
            )
        }
    )


# =========================================
# ADMIN DOWNLOAD STATS
# =========================================

@router.get("/admin/stats/downloads")
async def download_stats(
    db: Session = Depends(get_db)
):
    music_total = (
        db.query(func.sum(Music.downloads))
        .scalar()
    )

    video_total = (
        db.query(func.sum(Video.downloads))
        .scalar()
    )

    return {
        "music_downloads": music_total or 0,
        "video_downloads": video_total or 0
    }


# =========================================
# DELETE COMMENT (ADMIN ONLY)
# =========================================

@router.post("/comments/delete/{comment_id}")
async def delete_comment(
    comment_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    csrf_protect.validate_csrf(request)

    comment = (
        db.query(Comment)
        .filter(Comment.id == comment_id)
        .first()
    )

    if not comment:
        raise HTTPException(
            status_code=404,
            detail="Comment not found"
        )

    if (
        comment.user_id != current_user.id
        and not current_user.is_admin
    ):
        raise HTTPException(
            status_code=403,
            detail="Not authorized"
        )

    db.delete(comment)
    db.commit()

    return RedirectResponse(
        request.headers.get("referer", "/"),
        status_code=303
    )


# =========================================
# ABOUT PAGE
# =========================================

@router.get("/about")
async def about_page(
    request: Request
):
    return request.app.state.render_with_csrf(
        templates_instance=templates,
        request=request,
        template_name="frontend/about.html",
        context={}
    )


# =========================================
# CONTACT PAGE
# =========================================

@router.get("/contact")
async def contact_page(
    request: Request
):
    return request.app.state.render_with_csrf(
        templates_instance=templates,
        request=request,
        template_name="frontend/contact.html",
        context={}
    )
