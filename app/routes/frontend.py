# =========================================
# FRONTEND ROUTES
# FILE: app/routes/frontend.py
# =========================================

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
from sqlalchemy.orm import Session
import os
from app.core.database import get_db
from datetime import datetime  # ✅ FIXED: Import added here

import os.path
from app.models.news import News
from app.models.video import Video
from app.models.music import Music
from app.models.comment import Comment
from app.models.user import User
router = APIRouter(tags=["Public Activity Feed"])

templates = Jinja2Templates(
    directory="app/templates"
)
BASE_UPLOAD_DIR = os.path.abspath("app/static/uploads")

# =========================================
# HOME PAGE
# ============
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

    # 1. Fetch data for featured sections
    news = db.query(News).order_by(desc(News.created_at)).offset(skip).limit(per_page).all()
    videos = db.query(Video).order_by(desc(Video.created_at)).limit(6).all()
    musics = db.query(Music).order_by(desc(Music.created_at)).limit(6).all()

    trending_news = db.query(News).order_by(desc(News.views), desc(News.created_at)).limit(5).all()
    trending_videos = db.query(Video).order_by(desc(Video.views), desc(Video.created_at)).limit(5).all()
    trending_musics = db.query(Music).order_by(desc(Music.views), desc(Music.created_at)).limit(5).all()

    # 2. Check if files exist before passing to template (Audio)
    for m in musics:
        if m.music_file:
            file_path = os.path.join(BASE_UPLOAD_DIR, m.music_file.lstrip("/"))
            m.file_exists = os.path.exists(file_path)
        else:
            m.file_exists = False

    # Check if files exist before passing to template (Video)
    for v in videos:
        if v.video_file:
            file_path = os.path.join(BASE_UPLOAD_DIR, v.video_file.lstrip("/"))
            v.file_exists = os.path.exists(file_path)
        else:
            v.file_exists = False

    # 3. ✅ SEAMLESS VIEW EXTRACTION: Pull initial Page 1 cards from your optimized feed VIEW
    stmt = text("""
        SELECT id, title, slug, content, media, views, created_at, type, video_file, music_file
        FROM feed
        ORDER BY created_at DESC, id DESC
        LIMIT :limit OFFSET :offset
    """)

    try:
        raw_rows = db.execute(stmt, {"limit": feed_per_page, "offset": feed_offset}).mappings().all()
    except Exception as e:
        print("Homepage Feed Query View Error:", e)
        raw_rows = []

    # 4. ✅ DATA DICTIONARY WRAPPER: Wrap raw view dictionary rows into dot-notation accessible objects
    # This matches the frontend expectation layout (item.title, item.image, item.type)
    initial_feed = []
    
    class StreamItem:
        def __init__(self, data_map):
            self.id = data_map["id"]
            self.type = data_map["type"]
            self.title = data_map["title"]
            self.slug = data_map["slug"]
            self.content = data_map["content"]
            self.image = data_map["media"]         # Maps database view 'media' string to frontend '.image'
            self.views = data_map["views"]
            self.created_at = data_map["created_at"]
            
            # Safe parsing for SQLite raw timestamp string columns
            if isinstance(self.created_at, str):
                try:
                    self.created_at = datetime.strptime(self.created_at, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    pass
            self.video_file = data_map["video_file"]
            self.music_file = data_map["music_file"]

    for row in raw_rows:
        initial_feed.append(StreamItem(row))

    total_news = db.query(func.count(News.id)).scalar()
    total_pages = (total_news + per_page - 1) // per_page

    # 5.  SYNCHRONIZED RETURN CONTEXT: Passes the initialized list to "feed" context key
    render_with_csrf = request.app.state.render_with_csrf

    return render_with_csrf(
        templates_instance=templates,
        request=request,
        template_name="frontend/index.html", 
        context={
            "news": news,
            "videos": videos,
            "musics": musics,
            "trending_news": trending_news,
            "trending_videos": trending_videos,
            "trending_musics": trending_musics,
            "feed": initial_feed,            # 🔥 FIXED: Populates your homepage updates loop with clean objects!
            "page": page,
            "total_pages": total_pages
        }
    )

# Added explicit name for route tracking stability
@router.get("/feed/stream", response_class=HTMLResponse, name="get_infinite_feed_stream")
async def get_infinite_feed_stream(
    request: Request,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=6, ge=1, le=24),
    db: Session = Depends(get_db)
):
    offset = (page - 1) * limit

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
        ORDER BY created_at DESC, id DESC
        LIMIT :limit OFFSET :offset
    """)

    try:
        rows = db.execute(
            stmt,
            {
                "limit": limit,
                "offset": offset
            }
        ).mappings().all()

    except Exception as e:
        print("Feed Stream Error:", e)
        raise HTTPException(
            status_code=500,
            detail="Unable to load feed."
        )

    if not rows:
        return HTMLResponse("")

    feed = []

    #  FIXED DATA MAPPING CLASS wrapper: Converts dict arrays to standard dot-notation object references
    # This prevents your templates from encountering property retrieval crashes inside Jinja
    class StreamItem:
        def __init__(self, data_map, parsed_date):
            self.id = data_map["id"]
            self.type = data_map["type"]
            self.title = data_map["title"]
            self.slug = data_map["slug"]
            self.content = data_map["content"]
            self.image = data_map["media"]         # Safely bridges database 'media' to frontend '.image'
            self.views = data_map["views"]
            self.created_at = parsed_date
            self.video_file = data_map["video_file"]
            self.music_file = data_map["music_file"]

    for row in rows:
        created_at = row["created_at"]

        if isinstance(created_at, str):
            try:
                created_at = datetime.strptime(
                    created_at,
                    "%Y-%m-%d %H:%M:%S"
                )
            except ValueError:
                pass

        # Instantiate our secure wrapper object and append it cleanly to the rendering feed array
        feed.append(StreamItem(row, created_at))

    # Safely passes the tracking cookies down through your native app helper middleware logic
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

    news = db.query(News)\
        .order_by(News.id.desc())\
        .all()
    return request.app.state.render_with_csrf(
        templates_instance=templates,
        request=request,
        template_name="frontend/news.html",
        context={
            "news_list": news  # Keep your original context dictionary key intact
        }
    )

# =========================================
# NEWS DETAIL
# =========================================

@router.get("/news/{identifier}")
def news_detail(
    identifier: str,
    request: Request,
    db: Session = Depends(get_db),
):
    if identifier.isdigit():
        # Look up article by numeric database row ID
        news = db.query(News).filter(News.id == int(identifier)).first()
        
        # 🚀 SEO Optimization: If the article has a slug string, enforce a permanent 301 redirect to the slug URL
        if news and getattr(news, "slug", None):
            return RedirectResponse(url=f"/news/{news.slug}", status_code=301)
    else:
        # Look up article directly by alphanumeric text slug column field
        news = db.query(News).filter(News.slug == identifier).first()

    if not news:
        raise HTTPException(
            status_code=404,
            detail="News not found"
        )
    try:
         news.views = (news.views or 0) + 1
         db.commit()
    except Exception:
         db.rollback()

    comments = db.query(Comment)\
        .filter(Comment.news_id == news.id)\
        .order_by(Comment.id.desc())\
        .all()
    
    related_news = db.query(News)\
        .filter(News.id != news.id)\
        .order_by(News.id.desc())\
        .limit(5)\
        .all()
    return request.app.state.render_with_csrf(
        templates_instance=templates,
        request=request,
        template_name="frontend/news_detail.html",
        context={
            "news": news,
            "comments": comments,
            "related_news": related_news,
            "meta_title": news.title,
            "meta_description": news.content[:160] if news.content else "",
            "meta_image": news.image
        }
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
    videos = db.query(Video)\
        .order_by(Video.id.desc())\
        .all()
    return request.app.state.render_with_csrf(
        templates_instance=templates,
        request=request,
        template_name="frontend/videos.html",
        context={
            "videos": videos  # Keep your original context dictionary key intact
        }
    )

# =========================================
# VIDEO DETAIL
# =========================================

@router.get("/video/download/{video_id}")
async def download_video(
    request: Request,
    video_id: int,
    db: Session = Depends(get_db)
):
    video = db.query(Video).filter(Video.id == video_id).first()

    if not video:
        raise HTTPException(status_code=404)

    relative_path = video.video_file.replace("/static/", "")
    file_path = safe_file_path(relative_path)

    video.downloads = (video.downloads or 0) + 1
    db.commit()

    return FileResponse(
        path=file_path,
        filename=os.path.basename(file_path),
        media_type="video/mp4"
    )
#=====================================================================
# 🎥 PUBLIC VIDEO DETAILED PLAYER PAGE ROUTE WITH 10-COMMENT PAGINATION
# =====================================================================
@router.get("/videos/{video_id}", response_class=HTMLResponse)
@limiter.limit("40/minute")
async def view_video_detail(
    video_id: int,
    request: Request,
    page: int = Query(default=1, ge=1), # ✅ Handles pagination query parameter safely
    db: Session = Depends(get_db)
):
    # 1. Fetch the target video parent row profile out of SQLite
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="The requested video cannot be found.")

    # 2. Configure 10-comment pagination slices explicitly
    comments_per_page = 10
    offset = (page - 1) * comments_per_page

    # Query child comment rows chronological sorting matching parent video context
    comments_query = db.query(Comment).filter(Comment.video_id == video_id).order_by(desc(Comment.id))
    total_comments_count = comments_query.count()
    paginated_comments = comments_query.offset(offset).limit(comments_per_page).all()
    total_pages = (total_comments_count + comments_per_page - 1) // comments_per_page

    # 3. Pull view counter matrix cleanly and commit to DB safely
    try:
        video.views = getattr(video, "views", 0) + 1
        db.commit()
    except Exception:
        db.rollback()

    # Pull the cookie/context assignment injection utility from app main state
    render_with_csrf = request.app.state.render_with_csrf

    # ✅ Safe token assignment across cookies and template layers
    return render_with_csrf(
        templates_instance=templates,
        request=request,
        template_name="frontend/video_detail.html",
        context={
            "video": video,
            "comments": paginated_comments,   # Page-sliced array list maps directly onto cards loop
            "current_page": page,             # Required for navigation buttons highlights
            "total_pages": max(total_pages, 1) # Prevents division by zero errors
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
    # 1. Verify the parent video resource row profile exists in your database
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Target video record not found.")

    # 2. Extract client submission data parameters cleanly
    content_clean = content.strip()
    if not content_clean:
        raise HTTPException(status_code=400, detail="Comment content cannot be empty.")

    # 3. Commit the new comment record row securely inside an exception block
    try:
        new_comment = Comment(
            video_id=video_id,
            name="Anonymous",  # Fallback property string if user auth profile parameters are omitted
            content=content_clean
        )
        db.add(new_comment)
        db.commit()
    except Exception as e:
        db.rollback()
        print("Video Comment Database Error:", e)
        raise HTTPException(status_code=500, detail="Database write action failure during comment saving.")

    # 4. HYBRID PROTOCOL RESPONSE DETECTOR:
    # If an older device bypasses JavaScript, perform a clean browser redirect fallback
    if "application/x-www-form-urlencoded" in request.headers.get("content-type", "").lower():
        return RedirectResponse(url=f"/videos/{video_id}", status_code=303)

    # For your optimized frontend AJAX fetch listener, return a clean validation status confirmation code
    return JSONResponse(
        status_code=201, 
        content={"success": True, "detail": "Public user comment registered successfully."}
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
    musics = db.query(Music)\
        .order_by(Music.id.desc())\
        .all()
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

@router.get("/music/{music_id}")
async def music_detail(
    music_id: int,
    request: Request,
    db: Session = Depends(get_db)):

    music = db.query(Music)\
        .filter(Music.id == music_id)\
        .first()

    if not music:
        raise HTTPException(
            status_code=404,
            detail="Music not found"
        )

    music.views = (music.views or 0) + 1
    db.commit()
    db.refresh(music)

    comments = db.query(Comment)\
        .filter(Comment.music_id == music_id)\
        .order_by(Comment.id.desc())\
        .all()

    related_music = db.query(Music)\
        .filter(Music.id != music_id)\
        .order_by(Music.id.desc())\
        .limit(5)\
        .all()
    return request.app.state.render_with_csrf(
            templates_instance=templates,
            request=request,
            template_name="frontend/music_detail.html",
            context={
                "music": music,
                "comments": comments,
                "related_music": related_music,
                "meta_title": music.title,
                "meta_description": music.description[:160] if music.description else "",
              #  "meta_image": music.thumbnail
                "meta_image": getattr(music, "image", getattr(music, "cover_image", "/static/images/default_audio.png"))
            }
        )
# =========================================
# MUSIC DOWNLOAD ROUTE
# =========================================
@router.get("/music/download/{music_id}")
@limiter.limit("5/minute")
async def download_music(request: Request, music_id: int, db: Session = Depends(get_db)):
    music = db.query(Music).filter(Music.id == music_id).first()
    if not music:
        raise HTTPException(404)

    relative_path = music.music_file.replace("/static/", "")
    file_path = safe_file_path(relative_path)

    music.downloads = (music.downloads or 0) + 1
    db.commit()

    return FileResponse(path=file_path, filename=file_path.name)
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
    # Re-fetch page data context exactly matching your layout rules
    comments = db.query(Comment)\
        .filter(Comment.music_id == music_id)\
        .order_by(Comment.id.desc())\
        .all()
    related_music = db.query(Music)\
        .filter(Music.id != music_id)\
        .order_by(Music.id.desc())\
        .limit(5)\
        .all()
    music = db.query(Music)\
        .filter(Music.id == music_id)\
        .first()

    if not music:
        raise HTTPException(
            status_code=404,
            detail="Music not found"
        )

    new_comment = Comment(
        name=name,
        content=content,
        music_id=music_id
    )

    db.add(new_comment)
    db.commit()
    return request.app.state.render_with_csrf(
         templates_instance=templates,
         request=request,
         template_name="frontend/music_detail.html",
         context={
             "music": music,
             "comments": comments,
             "related_music": related_music,
             "meta_title": music.title,
             "meta_description": music.description[:160] if music.description else "",
             "meta_image": music.cover_image
         }
     )
# =========================================
# ADMIN DOWNLOAD STATS
# =========================================

@router.get("/admin/stats/downloads")
async def download_stats(db: Session = Depends(get_db)):

    music_total = db.query(func.sum(Music.downloads)).scalar()
    video_total = db.query(func.sum(Video.downloads)).scalar()

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
    current_user: User = Depends(get_current_user),
):
    csrf_protect.validate_csrf(request) 
    comment = db.query(Comment).filter(Comment.id == comment_id).first()
    if not comment:
        raise HTTPException(404)
    if comment.user_id!= current_user.id and not current_user.is_admin:
        raise HTTPException(403)
    db.delete(comment)
    db.commit()
    return RedirectResponse(request.headers.get("referer", "/"), 303)
##about

@router.get("/about")
async def about_page(request: Request):
    return request.app.state.render_with_csrf(
         templates_instance=templates,
         request=request,
         template_name="frontend/about.html",
         context={}
     )
@router.get("/contact")
async def contact_page(request:Request):
   return request.app.state.render_with_csrf(
        templates_instance=templates,
        request=request,
        template_name="frontend/contact.html",
        context={}
    )
@router.get("/feed/stream")
async def get_infinite_feed_stream(
    request: Request,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=6, ge=1, le=24),
    db: Session = Depends(get_db)
):
    offset = (page - 1) * limit
    unified_feed = []

    # 1. Fetch data aggregates cleanly from distinct entities
    news_records = db.query(News).order_by(News.created_at.desc()).offset(offset).limit(limit).all()
    video_records = db.query(Video).order_by(Video.created_at.desc()).offset(offset).limit(limit).all()
    music_records = db.query(Music).order_by(Music.created_at.desc()).offset(offset).limit(limit).all()

    # 2. Standardize news structures
    for item in news_records:
        unified_feed.append({
            "id": item.id,
            "type": "news",
            "title": item.title,
            "content": item.content,
            "image": item.image,
            "views": item.views,
            "created_at": item.created_at,
            "slug": getattr(item, "slug", None)
        })

    # 3. Standardize video structures
    for item in video_records:
        unified_feed.append({
            "id": item.id,
            "type": "video",
            "title": item.title,
            "content": item.description,  # Maps description parameter to uniform text key
            "image": item.thumbnail if item.thumbnail else None,
            "video_file": item.video_file,
            "views": item.views,
            "created_at": item.created_at,
            "slug": None
        })

    # 4. Standardize music structures
    for item in music_records:
        unified_feed.append({
            "id": item.id,
            "type": "music",
            "title": item.title,
            "content": item.description,
            "image": item.cover_image,
            "music_file": item.music_file,
            "views": item.views,
            "created_at": item.created_at,
            "slug": None
        })

    # 5. Global chronological sorting sorting structure
    unified_feed.sort(key=lambda x: x["created_at"] if x["created_at"] else datetime.min, reverse=True)
    
    # Crop the collection cleanly down to the requested chunk threshold size bounds
    paginated_slice = unified_feed[:limit]

    # ✅ HYBRID SNIPPET DELIVERY DETECTOR:
    # If the call is generated via the custom frontend Fetch API request, return the raw snippet block HTML
    if "xmlhttprequest" in request.headers.get("x-requested-with", "").lower() or "application/json" in request.headers.get("accept", "").lower():
        return templates.TemplateResponse(
            request=request,
            name="frontend/load_more.html",
            context={"feed": paginated_slice}
        )

    # Standard browser baseline fallback fallback block injection map
    return templates.TemplateResponse(
        request=request,
        name="frontend/home.html",
        context={"feed": paginated_slice}
    )
