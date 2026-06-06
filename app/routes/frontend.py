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
    Form
)
from sqlalchemy import func
from fastapi.responses import(RedirectResponse,JSONResponse,FileResponse)
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.database import get_db

from app.models.news import News
from app.models.video import Video
from app.models.music import Music
from app.models.comment import Comment

router = APIRouter()

templates = Jinja2Templates(
    directory="app/templates"
)

# =========================================
# HOME PAGE
# =========================================
@router.get("/")

def home(
    request: Request,
    page: int = Query(1),
    db: Session = Depends(get_db)
):
    per_page = 6
    skip = (page - 1) * per_page

    total_news = db.query(News).count()

    total_pages = (
        total_news + per_page - 1
    ) // per_page

    news = db.query(News)\
        .order_by(News.id.desc())\
        .offset(skip)\
        .limit(per_page)\
        .all()

    videos = db.query(Video)\
        .order_by(Video.id.desc())\
        .limit(6)\
        .all()

    musics = db.query(Music)\
        .order_by(Music.id.desc())\
        .limit(6)\
        .all()

    trending_news = db.query(News)\
        .order_by(News.views.desc())\
        .limit(5)\
        .all()

    trending_videos = db.query(Video)\
        .order_by(Video.views.desc())\
        .limit(5)\
        .all()

    trending_musics = db.query(Music)\
        .order_by(Music.views.desc())\
        .limit(5)\
        .all()
 # =====================================
    # MIXED FEED FOR INFINITE SCROLL
    # =====================================

    all_news = db.query(News).all()
    all_videos = db.query(Video).all()
    all_musics = db.query(Music).all()

    items = []

    for n in all_news:
        items.append({
            "type": "news",
            "id": n.id,
            "title": n.title,
            "created_at": n.created_at,
            "obj": n
        })

    for v in all_videos:
        items.append({
            "type": "video",
            "id": v.id,
            "title": v.title,
            "created_at": v.created_at,
            "obj": v
        })

    for m in all_musics:
        items.append({
           "type": "music",
           "id": m.id,
           "title": m.title,
           "created_at": m.created_at,
           "obj": m
        })
    # Sort newest first
    items.sort(
        key=lambda x: x["created_at"],
        reverse=True
    )

    # First 9 items shown initially
    items = items[:9]

    return templates.TemplateResponse(
        "frontend/index.html",
        {
            "request": request,
            "news": news,
            "videos": videos,
            "musics": musics,
            "trending_news": trending_news,
            "trending_videos": trending_videos,
            "trending_musics": trending_musics,
            # Infinite Scroll Feed
            "items": items,
            "page": page,
            "total_pages": total_pages
        }
    )
 # =====================================
    # load more
    # ============================
@router.get("/api/load-more")
def load_more(
    request: Request,
    page: int = 1,
    db: Session = Depends(get_db)
):

    per_page = 9

    news = db.query(News).all()
    videos = db.query(Video).all()
    music = db.query(Music).all()

    items = []

    for n in news:
        items.append({
            "type": "news",
            "id": n.id,
            "title": n.title,
            "created_at": n.created_at,
            "obj": n
        })

    for v in videos:
        items.append({
            "type": "video",
            "id": v.id,
            "title": v.title,
            "created_at": v.created_at,
            "obj": v
        })

    for m in music:
        items.append({
            "type": "music",
            "id": m.id,
            "title": m.title,
            "created_at": m.created_at,
            "obj": m
        })

    items.sort(
        key=lambda x: x["created_at"],
        reverse=True
    )

    start = (page - 1) * per_page
    end = start + per_page

    page_items = items[start:end]

    return templates.TemplateResponse(
        "frontend/load_more.html",
        {
            "request": request,
            "items": page_items
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

    return templates.TemplateResponse(
        "frontend/news.html",
        {
            "request": request,
            "news_list": news
        }
    )

# =========================================
# NEWS DETAIL
# =========================================

@router.get("/news/{news_id}")
def news_detail(
    news_id: int,
    request: Request,
    db: Session = Depends(get_db)
):

    news = db.query(News)\
        .filter(News.id == news_id)\
        .first()

    if not news:
        raise HTTPException(
            status_code=404,
            detail="News not found"
        )

    news.views = (news.views or 0) + 1
    db.commit()

    comments = db.query(Comment)\
        .filter(Comment.news_id == news_id)\
        .order_by(Comment.id.desc())\
        .all()

    related_news = db.query(News)\
        .filter(News.id != news_id)\
        .order_by(News.id.desc())\
        .limit(5)\
        .all()

    return templates.TemplateResponse(
        "frontend/news_detail.html",
        {
            "request": request,
            "news": news,
            "comments": comments,
            "related_news": related_news,

            "meta_title": news.title,
            "meta_description": news.content[:160] if news.content else "",
            "meta_image": news.image
        }
    )
# =========================================
# ADD NEWS COMMENT
# =========================================
# =========================================
# VIDEOS PAGE
# =========================================

@router.get("/videos")
def videos_page(
    request: Request,
    db: Session = Depends(get_db)
):

    videos = db.query(Video)\
        .order_by(Video.id.desc())\
        .all()

    return templates.TemplateResponse(
        "frontend/videos.html",
        {
            "request": request,
            "videos": videos
        }
    )

# =========================================
# VIDEO DETAIL
# =========================================

# =========================================
# VIDEO DOWNLOAD ROUTE
# =========================================

@router.get("/video/download/{video_id}")
def download_video(
    video_id: int,
    db: Session = Depends(get_db)
):

    video = db.query(Video).filter(Video.id == video_id).first()

    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
# increase downloads
    video.downloads = (video.downloads or 0) + 1
    db.commit()

    return FileResponse(
        path=video.video.file,  # or video.video_file_path (use your real column)
        filename=f"{video.title}.mp4",
        media_type="video/mp4"
    )
# =========================================
# ADD VIDEO COMMENT
# =========================================
# =========================================
# MUSIC PAGE
# =========================================

@router.get("/music")
def music_page(
    request: Request,
    db: Session = Depends(get_db)
):

    musics = db.query(Music)\
        .order_by(Music.id.desc())\
        .all()

    return templates.TemplateResponse(
        "frontend/music.html",
        {
            "request": request,
            "musics": musics
        }
    )

# =========================================
# MUSIC DETAIL
# =========================================

@router.get("/music/{music_id}")
def music_detail(
    music_id: int,
    request: Request,
    db: Session = Depends(get_db)
):

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

    comments = db.query(Comment)\
        .filter(Comment.music_id == music_id)\
        .order_by(Comment.id.desc())\
        .all()

    related_music = db.query(Music)\
        .filter(Music.id != music_id)\
        .order_by(Music.id.desc())\
        .limit(5)\
        .all()

    return templates.TemplateResponse(
        "frontend/music_detail.html",
        {
            "request": request,
            "music": music,
            "comments": comments,
            "related_music": related_music
        }
    )
# =========================================
# MUSIC DOWNLOAD ROUTE
# =========================================
@router.get("/music/download/{music_id}")
def download_music(
    music_id: int,
    db: Session = Depends(get_db)
):

    music = db.query(Music).filter(Music.id == music_id).first()
    if not music:
        raise HTTPException(status_code=404, detail="Music not found")
    #increase downloads
    music.downloads = (music.downloads or 0) + 1
    file_path = music.music_file.replace(
        "/static/",
        "app/static/"
    )

    print(file_path)  # debug

    return FileResponse(
        path=file_path,
        filename=os.path.basename(file_path),
        media_type="audio/mpeg"
    )
# =========================================
# ADD MUSIC COMMENT
# =========================================

@router.post("/music/{music_id}/comment")
def add_music_comment(
    music_id: int,
    name: str = Form(...),
    content: str = Form(...),
    db: Session = Depends(get_db)
):

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

    return RedirectResponse(
        f"/music/{music_id}",
        status_code=303
    )
# =========================================
# ADMIN DOWNLOAD STATS
# =========================================

@router.get("/admin/stats/downloads")
def download_stats(db: Session = Depends(get_db)):

    music_total = db.query(func.sum(Music.downloads)).scalar()
    video_total = db.query(func.sum(Video.downloads)).scalar()

    return {
        "music_downloads": music_total or 0,
        "video_downloads": video_total or 0
    }
# =========================================
# DELETE COMMENT (ADMIN ONLY)
# =========================================

@router.get("/comments/delete/{comment_id}")
def delete_comment(
    comment_id: int,
    db: Session = Depends(get_db)
):

    comment = db.query(Comment)\
        .filter(Comment.id == comment_id)\
        .first()

    if not comment:
        raise HTTPException(
            status_code=404,
            detail="Comment not found"
        )

    redirect_url = "/"

    if comment.news_id:
        redirect_url = f"/news/{comment.news_id}"

    elif comment.video_id:
        redirect_url = f"/videos/{comment.video_id}"

    elif comment.music_id:
        redirect_url = f"/music/{comment.music_id}"

    db.delete(comment)
    db.commit()

    return RedirectResponse(
        redirect_url,
        status_code=303
    )
##about

@router.get("/about")
def about_page(request: Request):
    return templates.TemplateResponse(
        "frontend/about.html",
        {"request": request}
    )
@router.get("/contact")
def contact_page(request:Request):
   return templates.TemplateResponse(
      "frontend/contact.html",
        {"request": request}
)
