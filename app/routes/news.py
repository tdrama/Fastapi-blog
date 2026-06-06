from fastapi import (
    APIRouter,
    Request,
    Depends,
    Form,
    BackgroundTasks, 
    UploadFile,
    File,
    HTTPException
)

from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from sqlalchemy.orm import Session, joinedload

from slugify import slugify

import os
import shutil
import hashlib
from uuid import uuid4
from app.models.subscriber import Subscriber
from app.services.email_service import send_email
from app.core.database import get_db
from app.models.news import News
from app.models.comment import Comment
from app.utils.sanitizer import sanitize_html
from app.models.category import Category

# ====================================================
# ROUTER
# ====================================================
router = APIRouter()

templates = Jinja2Templates(directory="app/templates")


# ====================================================
# UPLOAD CONFIG
# ====================================================
UPLOAD_DIR = "app/static/uploads/news"
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_IMAGES = [".jpg", ".jpeg", ".png", ".webp", ".avif"]

CATEGORIES = [
    "Politics",
    "Sports",
    "Technology",
    "Business",
    "Entertainment",
    "Health",
    "Education"
]


# ====================================================
# HASH FUNCTION
# ====================================================
def generate_file_hash(file):
    hasher = hashlib.md5()

    pos = file.tell()
    file.seek(0)

    for chunk in iter(lambda: file.read(4096), b""):
        hasher.update(chunk)

    file.seek(pos)

    return hasher.hexdigest()


# ====================================================
# DASHBOARD NEWS LIST
# ====================================================
@router.get("/dashboard/news")
def news_page(
    request: Request,
    page: int = 1,
    db: Session = Depends(get_db)
):

    per_page = 10

    total = db.query(News).count()

    news = (
        db.query(News)
        .order_by(News.id.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    total_pages = (total + per_page - 1) // per_page

    categories = db.query(Category).all()

    return templates.TemplateResponse(
        "dashboard/news/index.html",
        {
            "request": request,
            "news": news,
            "categories": categories,
            "page": page,
            "total_pages": total_pages
        }
    )
# ====================================================
# CREATE PAGE
# ====================================================
@router.get("/dashboard/news/create")
def create_page(request: Request,db: Session = Depends(get_db)
 ):

    categories = db.query(Category).all()

    return templates.TemplateResponse(
        "dashboard/news/create.html",
        {
            "request": request,
            "categories": categories
        }
    )


# ====================================================
# CREATE NEWS
# ====================================================
@router.post("/dashboard/news/create")
def create_news(
    request: Request,
    background_tasks: BackgroundTasks,
    title: str = Form(...),
    content: str = Form(...),
    category_id: str = Form(...),
    tags: str = Form(None),
    image: UploadFile = File(None),
    db: Session = Depends(get_db)
):

    slug = slugify(title)

    existing_slug = db.query(News).filter(News.slug == slug).first()

    if existing_slug:
        slug = f"{slug}-{uuid4().hex[:6]}"
    clean_content = sanitize_html(content or "")

    image_path = None
    image_hash = None
    image_size = 0

    # ---------------- IMAGE UPLOAD ----------------
    if image and image.filename:

        ext = os.path.splitext(image.filename)[1].lower()

        if ext not in ALLOWED_IMAGES:
            raise HTTPException(status_code=400, detail="Invalid image format")

        image_hash = generate_file_hash(image.file)

        existing_image = db.query(News)\
            .filter(News.image_hash == image_hash)\
            .first()

        if existing_image:
            raise HTTPException(status_code=400, detail="Image already exists")

        image.file.seek(0)

        filename = f"{uuid4()}_{image.filename}"
        file_path = f"{UPLOAD_DIR}/{filename}"

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(image.file, buffer)

        image_path = f"/static/uploads/news/{filename}"
        image_size = os.path.getsize(file_path)

    # ---------------- SESSION USER ----------------
    user_id = request.session.get("user_id")

    if not user_id:
        raise HTTPException(status_code=401, detail="Login required")

    clean_content = sanitize_html(content)

    news = News(
        title=title,
        slug=slug,
        content=clean_content,
        category_id=category_id,
        tags=tags,
        image=image_path,
        image_hash=image_hash,
        image_size=image_size,
        author_id=user_id
    )

    # SAVE NEWS
    db.add(news)

    db.commit()

    db.refresh(news)

     # SEND EMAIL TO SUBSCRIBERS
    # =========================
    # SEND EMAILS (ASYNC)
    # =========================
    subscribers = db.query(Subscriber).all()

    for sub in subscribers:
        background_tasks.add_task(
            send_email,
            sub.email,
            f"Breaking News: {news.title}",
            news.content or ""
        )

    return RedirectResponse(
        "/dashboard/news",
        status_code=302
    )

# ====================================================
# EDIT PAGE
# ====================================================
@router.get("/dashboard/news/edit/{news_id}")
def edit_news_page(news_id: int, request: Request, db: Session = Depends(get_db)):

    news = db.query(News).filter(News.id == news_id).first()

    if not news:
        raise HTTPException(status_code=404, detail="News not found")
 
    categories = db.query(Category).all()
    return templates.TemplateResponse(
        "dashboard/news/edit.html",
        {
            "request": request,
            "news": news,
            "categories": categories
        }
    )


# ====================================================
# UPDATE NEWS
# ====================================================
@router.post("/dashboard/news/update/{news_id}")
def update_news(
    news_id: int,
    title: str = Form(...),
    content: str = Form(...),
    category_id: int = Form(...),
    tags: str = Form(None),
    image: UploadFile = File(None),
    db: Session = Depends(get_db)
):

    news = db.query(News).filter(News.id == news_id).first()

    if not news:
        raise HTTPException(status_code=404, detail="News not found")

    news.title = title
    news.slug = slugify(title)
    news.content = content
    news.category_id = category_id
    news.tags = tags

    if image and image.filename:

        ext = os.path.splitext(image.filename)[1].lower()

        if ext not in ALLOWED_IMAGES:
            raise HTTPException(status_code=400, detail="Invalid image format")

        if news.image:
            old_file = f"app{news.image}"
            if os.path.exists(old_file):
                os.remove(old_file)

        image.file.seek(0)

        filename = f"{uuid4()}_{image.filename}"
        file_path = f"{UPLOAD_DIR}/{filename}"

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(image.file, buffer)

        news.image = f"/static/uploads/news/{filename}"
        news.image_size = os.path.getsize(file_path)

    db.commit()

    return RedirectResponse("/dashboard/news", status_code=302)


# ====================================================
# DELETE NEWS
# ====================================================
@router.get("/dashboard/news/delete/{news_id}")
def delete_news(news_id: int, db: Session = Depends(get_db)):

    news = db.query(News).filter(News.id == news_id).first()

    if not news:
        raise HTTPException(status_code=404, detail="News not found")

    if news.image:
        file_path = f"app{news.image}"
        if os.path.exists(file_path):
            os.remove(file_path)

    db.delete(news)
    db.commit()

    return RedirectResponse("/dashboard/news", status_code=302)


# ====================================================
# FRONTEND NEWS PAGE
# ====================================================
@router.get("/news")
def frontend_news(request: Request, db: Session = Depends(get_db)):

    news = db.query(News)\
        .options(joinedload(News.comments))\
        .filter(News.is_published == True)\
        .order_by(News.id.desc())\
        .all()

    return templates.TemplateResponse(
        "frontend/news.html",
        {
            "request": request,
            "news": news
        }
    )


# ====================================================
# NEWS DETAIL
# ====================================================
@router.get("/news/{slug}")
def news_detail(slug: str, request: Request, db: Session = Depends(get_db)):

    news = db.query(News)\
        .options(joinedload(News.comments))\
        .filter(News.slug == slug)\
        .first()

    if not news:
        raise HTTPException(status_code=404, detail="News not found")

    news.views = (news.views or 0) + 1
    db.commit()

    return templates.TemplateResponse(
        "frontend/news_detail.html",
        {
            "request": request,
            "news": news
        }
    )


# ====================================================
# ADD COMMENT
# ====================================================
@router.post("/news/{news_id}/comment")
def add_news_comment(
    news_id: int,
    name: str = Form(...),
    content: str = Form(...),
    db: Session = Depends(get_db)
):

    news = db.query(News).filter(News.id == news_id).first()

    if not news:
        raise HTTPException(status_code=404, detail="News not found")

    comment = Comment(
        name=name,
        content=content,
        news_id=news.id
    )

    db.add(comment)
    db.commit()

    return RedirectResponse(f"/news/{news.slug}", status_code=303)


# ====================================================
# JSON COMMENT
# ====================================================
@router.post("/news/{news_id}/comment/json")
def add_news_comment_json(
    news_id: int,
    name: str = Form(...),
    content: str = Form(...),
    db: Session = Depends(get_db)
):

    news = db.query(News).filter(News.id == news_id).first()

    if not news:
        return JSONResponse(status_code=404, content={"error": "News not found"})

    comment = Comment(
        name=name,
        content=content,
        news_id=news.id
    )

    db.add(comment)
    db.commit()
    db.refresh(comment)

    return {
        "id": comment.id,
        "name": comment.name,
        "content": comment.content,
        "created_at": str(comment.created_at)
    }
