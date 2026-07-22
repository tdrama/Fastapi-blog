from fastapi import (
    APIRouter,
    Request,
    Depends,
    HTTPException
)
from sqlalchemy.orm import selectinload  # Fixes the NameError crash
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi.templating import Jinja2Templates
from app.core.database import get_db
from app.models.login_log import LoginLog
from app.models.user import User
from app.models.video import Video
from app.models.music import Music
from app.models.news import News
from app.models.comment import Comment
from app.models.subscriber import Subscriber
from app.models.category import Category
from app.core.permissions import browser_admin_required
from fastapi_csrf_protect import CsrfProtect

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.get("/dashboard")
def dashboard(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(browser_admin_required)
):
    stats = {
        "users": db.query(User).count(),
        "videos": db.query(Video).count(),
        "music": db.query(Music).count(),
        "news": db.query(News).count(),
        "comments": db.query(Comment).count(),
        "subscribers": db.query(Subscriber).count()
    }

    total_music_views = db.query(func.sum(Music.views)).scalar() or 0
    total_video_views = db.query(func.sum(Video.views)).scalar() or 0
    total_news_views = db.query(func.sum(News.views)).scalar() or 0

         # FIXED JINJA2 RENDERING PATTERN (Bypasses Starlette Cache Key String Crash)
    return request.app.state.render_with_csrf(
        templates_instance=templates,
        request=request,
        template_name="dashboard/index.html",
        context={
            "user": current_user,
            "stats": stats,
            "total_music_views": total_music_views,
            "total_video_views": total_video_views,
            "total_news_views": total_news_views
        }
    )

@router.get("/dashboard/recent")
def dashboard_recent(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(browser_admin_required)
):
    return templates.TemplateResponse(
        request=request,
        name="dashboard/recent.html",
        context={
            "latest_news": db.query(News).order_by(News.id.desc()).limit(5).all(),
            "latest_videos": db.query(Video).order_by(Video.id.desc()).limit(5).all(),
            "latest_music": db.query(Music).order_by(Music.id.desc()).limit(5).all(),
            "latest_comments": db.query(Comment).order_by(Comment.id.desc()).limit(5).all()
        }
    )
@router.get("/dashboard/comments")
async def comments_page(
    request: Request, 
    status: str = "all", 
    page: int = 1,
    db: Session = Depends(get_db), 
    current_user: User = Depends(browser_admin_required)
):
    # 1. Safely parse and clamp the page parameter from incoming URL queries
    try:
        page = int(request.query_params.get("page", 1))
        if page < 1:
            page = 1
    except (ValueError, TypeError):
        # Fall back to function default if query parameter string parsing breaks
        if not isinstance(page, int) or page < 1:
            page = 1

    per_page = 20  # Keep matching your 20 rows limit
    offset = (page - 1) * per_page

    # 2. Establish relationship loader queries
    query = db.query(Comment).options(
        selectinload(Comment.video),
        selectinload(Comment.music),
        selectinload(Comment.news)
    )

    if status != "all":
        query = query.filter(Comment.status == status)

    # 3. Calculate pagination boundaries and total entries
    total = query.count()
    comments = query.order_by(Comment.created_at.desc()).offset(offset).limit(per_page).all()

    total_pages = (total + per_page - 1) // per_page
    if total_pages < 1:
        total_pages = 1

    has_prev = page > 1
    has_next = page < total_pages

    # ✅ FIXED JINJA2 KEYWORDS: Explicitly named parameters pass structural token pipelines
    return request.app.state.render_with_csrf(
        templates_instance=templates,
        request=request,
        template_name="dashboard/comments/index.html",
        context={
            "comments": comments,
            "page": page,
            "total_pages": total_pages,
            "status": status,
            "user": current_user,
            "has_prev": has_prev,
            "has_next": has_next,
            "prev_page": page - 1,
            "next_page": page + 1
        }
    )

@router.get("/dashboard/login-activity")
def login_activity(
    request: Request,
    page: int = 1,
    db: Session = Depends(get_db),
    current_user: User = Depends(browser_admin_required)
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
       request=request,
       name="dashboard/login_activity.html",
       context= {
            "logs": logs,
            "page": page,
            "total_pages": total_pages,
            "user": current_user
        }
    )

@router.post("/dashboard/comments/delete/{comment_id}")
async def delete_comment(
    comment_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(browser_admin_required)
):

    comment = db.query(Comment).filter(Comment.id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    db.delete(comment)
    db.commit()
    return RedirectResponse("/dashboard/comments", status_code=303)

@router.get("/dashboard/categories")
def categories_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(browser_admin_required)
):
    categories = db.query(Category).all()

    return request.app.state.render_with_csrf(
        templates_instance=templates,
        request=request,
        template_name="dashboard/categories/index.html",
        context={
            "categories": categories,
            "user": current_user
        }
    )
