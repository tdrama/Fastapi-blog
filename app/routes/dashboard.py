from fastapi import (
    APIRouter,
    Request,
    Depends
)
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from fastapi.templating import Jinja2Templates
from app.core.database import get_db
from app.core.permissions import require_admin
from app.models.login_log import LoginLog
from app.models.user import User
from app.models.video import Video
from app.models.music import Music
from app.models.news import News
from app.models.comment import Comment
from app.models.subscriber import Subscriber
from app.models.category import Category
from app.core.permissions import browser_admin_required

router = APIRouter()

templates = Jinja2Templates(
    directory="app/templates"
)



@router.get("/dashboard")
def dashboard(request: Request, db: Session = Depends(get_db)):

    current_user: User = Depends(browser_admin_required)

    if isinstance(current_user, RedirectResponse):
        return current_user

    return templates.TemplateResponse(
        "dashboard/index.html",
        {"request": request, "user": current_user}
    )
    stats = {
        "users": db.query(User).count(),
        "videos": db.query(Video).count(),
        "music": db.query(Music).count(),
        "news": db.query(News).count(),
        "comments": db.query(Comment).count(),
        "subscribers": db.query(Subscriber).count()
    }

    total_music_views = sum(
        m.views or 0
        for m in db.query(Music).all()
    )

    total_video_views = sum(
        v.views or 0
        for v in db.query(Video).all()
    )

    total_news_views = sum(
        n.views or 0
        for n in db.query(News).all()
    )

    return templates.TemplateResponse(
        "dashboard/index.html",
        {
            "request": request,
            "user": current_user,
            "stats": stats,
            "total_music_views": total_music_views,
            "total_video_views": total_video_views,
            "total_news_views": total_news_views
        }
    )

# =========================
# RECENT DATA ENDPOINT
# =========================

@router.get("/recent")
def dashboard_recent(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):

    return templates.TemplateResponse(
        "dashboard/index.html",
        {
            "request": request,
            "latest_news": db.query(News)
                .order_by(News.id.desc())
                .limit(5)
                .all(),

            "latest_videos": db.query(Video)
                .order_by(Video.id.desc())
                .limit(5)
                .all(),

            "latest_music": db.query(Music)
                .order_by(Music.id.desc())
                .limit(5)
                .all(),

            "latest_comments": db.query(Comment)
                .order_by(Comment.id.desc())
                .limit(5)
                .all()
        }
    )

# =========================
# COMMENTS PAGE
# =========================

@router.get("/dashboard/comments")
def comments_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):

    comments = (
    db.query(Comment)
    .order_by(Comment.id.desc())
    .all()
)

    return templates.TemplateResponse(
        "dashboard/comments/index.html",
        {
            "request": request,
            "comments": comments
        }
    )
@router.get("/dashboard/login-activity")
def login_activity(
    request: Request,
    page: int = 1,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    page = max(page, 1)
    per_page = 20

    total = db.query(LoginLog).count()

    logs = (
        db.query(LoginLog)
        .order_by(LoginLog.id.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    total_pages = (total + per_page - 1) // per_page

    return templates.TemplateResponse(
        "dashboard/login_activity.html",
        {
            "request": request,
            "logs": logs,
            "page": page,
            "total_pages": total_pages,
            "user": current_user
        }
    )
@router.get("/dashboard/comments/delete/{comment_id}")
def delete_comment(
    comment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
  ):
    comment = db.query(Comment).filter(
        Comment.id == comment_id
    ).first()

    if comment:
        db.delete(comment)
        db.commit()

    return RedirectResponse(
        "/dashboard/comments",
        status_code=303
    )
@router.get("/dashboard/categories")
def categories_page(
    request: Request,
    db: Session = Depends(get_db)
):
    categories = db.query(Category).all()

    return templates.TemplateResponse(
        "dashboard/categories/index.html",
        {
            "request": request,
            "categories": categories
        }
    )
