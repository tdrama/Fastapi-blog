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
from werkzeug.utils import secure_filename
from sqlalchemy.orm import Session, joinedload
from slugify import slugify
import secrets
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
EDITOR_MEDIA_DIR = "app/static/uploads/news/editor"

EDITOR_IMAGE_DIR = os.path.join(EDITOR_MEDIA_DIR, "images")
EDITOR_VIDEO_DIR = os.path.join(EDITOR_MEDIA_DIR, "videos")
EDITOR_PDF_DIR = os.path.join(EDITOR_MEDIA_DIR, "pdf")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(EDITOR_IMAGE_DIR, exist_ok=True)
os.makedirs(EDITOR_VIDEO_DIR, exist_ok=True)
os.makedirs(EDITOR_PDF_DIR, exist_ok=True)

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

@router.get("/dashboard/news")
def news_page(
    request: Request,
    db: Session = Depends(get_db)
):

    # 1. Extract current page parameter safely out of the browser URL query state
    try:
        page = int(request.query_params.get("page", 1))
        if page < 1:
            page = 1
    except (ValueError, TypeError):
        page = 1

    per_page = 10  # Enforce matching limit constraints per list view frame
    offset = (page - 1) * per_page

    # 2. Query matching slice maps pre-loaded with category relational mappings
    news_list = (
        db.query(News)
        .options(joinedload(News.category))
        .order_by(News.id.desc())
        .offset(offset)
        .limit(per_page)
        .all()
    )

    # 3. Aggregate tracking parameters metric metrics
    total_news = db.query(News).count()
    categories = db.query(Category).all()

    total_pages = (total_news + per_page - 1) // per_page
    if total_pages < 1:
        total_pages = 1
 
    has_prev = page > 1
    has_next = page < total_pages

    # ✅ PERFECT JINJA2 KEYWORDS: Explicitly named parameters pass structural token pipelines
    return request.app.state.render_with_csrf(
        templates_instance=templates,
        request=request,
        template_name="dashboard/news/index.html",
        context={
            "news": news_list,
            "categories": categories,
            "page": page,
            "has_prev": has_prev,
            "has_next": has_next,
            "prev_page": page - 1,
            "next_page": page + 1,
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
    return request.app.state.render_with_csrf(
        templates_instance=templates,
        request=request,
        template_name="dashboard/news/create.html",
        context={
            "categories": categories
        }
    )
# ====================================================
# CREATE NEWS
# ====================================================
@router.post("/dashboard/news/create")
async def create_news_article(
    request: Request,
    background_tasks: BackgroundTasks,
    title: str = Form(...),
    category_id: int = Form(...),
    content: str = Form(...),
    tags: str = Form(None),
    image: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    # ====================================================
    # AUTHENTICATION
    # ====================================================

    user_id = request.session.get("user_id")

    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="Login required"
        )

    # ====================================================
    # BASIC VALIDATION
    # ====================================================

    if not title or not title.strip():
        raise HTTPException(
            status_code=400,
            detail="Title is required"
        )

    if not content or not content.strip():
        raise HTTPException(
            status_code=400,
            detail="Content is required"
        )

    # ====================================================
    # SLUG
    # ====================================================

    slug = slugify(title)

    existing_slug = (
        db.query(News)
        .filter(News.slug == slug)
        .first()
    )

    if existing_slug:
        slug = f"{slug}-{uuid4().hex[:6]}"

    # ====================================================
    # DEFAULT IMAGE VALUES
    # ====================================================

    image_path = None
    image_hash = None
    image_size = 0

    # ====================================================
    # FEATURE IMAGE UPLOAD
    # ====================================================

    if image and image.filename:

        print(
            "========================================"
        )
        print(
            "NEWS CREATE - IMAGE RECEIVED"
        )
        print(
            "Filename:",
            image.filename
        )
        print(
            "Content type:",
            image.content_type
        )
        print(
            "========================================"
        )

        # ------------------------------------------------
        # Secure filename
        # ------------------------------------------------

        safe_name = secure_filename(
            image.filename
        )

        if not safe_name:

            raise HTTPException(
                status_code=400,
                detail="Invalid image filename"
            )

        # ------------------------------------------------
        # Get extension
        # ------------------------------------------------

        ext = os.path.splitext(
            safe_name
        )[1].lower()

        if ext not in ALLOWED_IMAGES:

            raise HTTPException(
                status_code=400,
                detail=(
                    f"Invalid image format: {ext}. "
                    f"Allowed formats: "
                    f"{', '.join(ALLOWED_IMAGES)}"
                )
            )

        # ------------------------------------------------
        # Move pointer to beginning
        # ------------------------------------------------

        image.file.seek(0)

        # ------------------------------------------------
        # Generate image hash
        # ------------------------------------------------

        image_hash = generate_file_hash(
            image.file
        )

        # ------------------------------------------------
        # Duplicate image check
        # ------------------------------------------------

        existing_image = (
            db.query(News)
            .filter(
                News.image_hash == image_hash
            )
            .first()
        )

        if existing_image:

            raise HTTPException(
                status_code=400,
                detail="Image already exists"
            )

        # ------------------------------------------------
        # IMPORTANT:
        # generate_file_hash() reads the file.
        # Reset the pointer before saving.
        # ------------------------------------------------

        image.file.seek(0)

        # ------------------------------------------------
        # Generate unique filename
        # ------------------------------------------------

        filename = (
            f"{uuid4().hex}{ext}"
        )

        # ------------------------------------------------
        # Physical file path
        # ------------------------------------------------

        file_path = os.path.join(
            UPLOAD_DIR,
            filename
        )

        # ------------------------------------------------
        # Save image
        # ------------------------------------------------

        try:

            with open(
                file_path,
                "wb"
            ) as buffer:

                shutil.copyfileobj(
                    image.file,
                    buffer
                )

        except Exception as exc:

            print(
                "NEWS IMAGE SAVE ERROR:",
                repr(exc)
            )

            raise HTTPException(
                status_code=500,
                detail="Failed to save image"
            )

        # ------------------------------------------------
        # Verify physical file
        # ------------------------------------------------

        if not os.path.isfile(
            file_path
        ):

            raise HTTPException(
                status_code=500,
                detail="Image file was not created"
            )

        # ------------------------------------------------
        # Get file size
        # ------------------------------------------------

        image_size = os.path.getsize(
            file_path
        )

        if image_size <= 0:

            try:

                os.remove(
                    file_path
                )

            except OSError:

                pass

            raise HTTPException(
                status_code=500,
                detail="Uploaded image is empty"
            )

        # ------------------------------------------------
        # Database URL
        # ------------------------------------------------

        image_path = (
            f"/static/uploads/news/{filename}"
        )

        # ------------------------------------------------
        # Verification logs
        # ------------------------------------------------

        print(
            "========================================"
        )

        print(
            "NEWS CREATE - IMAGE SAVED"
        )

        print(
            "Database image:",
            image_path
        )

        print(
            "Physical path:",
            file_path
        )

        print(
            "Image hash:",
            image_hash
        )

        print(
            "Image size:",
            image_size
        )

        print(
            "File exists:",
            os.path.isfile(file_path)
        )

        print(
            "========================================"
        )

    else:

        print(
            "========================================"
        )

        print(
            "NEWS CREATE - NO FEATURE IMAGE"
        )

        print(
            "========================================"
        )

    # ====================================================
    # SANITIZE ARTICLE CONTENT
    # ====================================================

    clean_content = sanitize_html(
        content or ""
    )

    # ====================================================
    # CREATE NEWS DATABASE RECORD
    # ====================================================

    news = News(
        title=title.strip(),
        slug=slug,
        content=clean_content,
        category_id=category_id,
        tags=tags,
        image=image_path,
        image_hash=image_hash,
        image_size=image_size,
        author_id=user_id
    )

    # ====================================================
    # SAVE NEWS
    # ====================================================

    try:

        db.add(news)

        db.commit()

        db.refresh(news)

    except Exception as exc:

        db.rollback()

        # If database save failed after image upload,
        # remove the orphaned physical image.

        if image_path:

            orphan_path = os.path.join(
                "app",
                image_path.lstrip("/")
            )

            if os.path.isfile(
                orphan_path
            ):

                try:

                    os.remove(
                        orphan_path
                    )

                except OSError:

                    pass

        print(
            "NEWS DATABASE ERROR:",
            repr(exc)
        )

        raise HTTPException(
            status_code=500,
            detail="Failed to create news article"
        )

    # ====================================================
    # FINAL VERIFICATION
    # ====================================================

    print(
        "========================================"
    )

    print(
        "NEWS CREATED SUCCESSFULLY"
    )

    print(
        "News ID:",
        news.id
    )

    print(
        "Title:",
        news.title
    )

    print(
        "Image:",
        repr(news.image)
    )

    print(
        "Image hash:",
        repr(news.image_hash)
    )

    print(
        "Image size:",
        news.image_size
    )

    print(
        "========================================"
    )

    # ====================================================
    # SEND EMAILS TO SUBSCRIBERS
    # ====================================================

    subscribers = (
        db.query(Subscriber)
        .all()
    )

    for sub in subscribers:

        background_tasks.add_task(
            send_email,
            sub.email,
            f"Breaking News: {news.title}",
            news.content or ""
        )

    # ====================================================
    # REDIRECT
    # ====================================================

    return RedirectResponse(
        "/dashboard/news",
        status_code=303
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
    return request.app.state.render_with_csrf(
        templates_instance=templates,
        request=request,
        template_name="dashboard/news/edit.html",
        context={
            "news": news,
            "categories": categories
        }
    )
# ====================================================
# UPDATE NEWS
# ====================================================
@router.post("/dashboard/news/update/{news_id}")
async def update_news(
    news_id: int,
    request: Request,
    title: str = Form(...),
    content: str = Form(...),
    category_id: int = Form(...),
    tags: str = Form(None),
    image: UploadFile = File(None),
    db: Session = Depends(get_db)
):


    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(401, "Login required")

    news = db.query(News).filter(News.id == news_id).first()

    if not news:
        raise HTTPException(status_code=404, detail="News not found")

    news.title = title
    news.slug = slugify(title)
    news.content = sanitize_html(content)
    news.category_id = category_id
    news.tags = tags

    if image and image.filename:
        safe_name = secure_filename(image.filename)
        ext = os.path.splitext(safe_name)[1].lower()

        if ext not in ALLOWED_IMAGES:
            raise HTTPException(status_code=400, detail="Invalid image format")
        new_image_hash = generate_file_hash(image.file)  
        
        # Check duplicate hash only if it's completely different from its current old image
        if new_image_hash != news.image_hash:
            existing_image = db.query(News).filter(News.image_hash == new_image_hash).first()  
            if existing_image:  
                raise HTTPException(status_code=400, detail="Image content already exists on another post")  

            # Delete old image physical asset from disk if it exists
            if news.image:
                old_file_relative = news.image.lstrip("/")
                old_file_path = os.path.join("app", old_file_relative) if not old_file_relative.startswith("app/") else old_file_relative
                if os.path.exists(old_file_path):
                    try:
                        os.remove(old_file_path)
                    except Exception:
                        pass # 
        if news.image:
            old_file = f"app{news.image}"
            if os.path.exists(old_file):
                os.remove(old_file)

        image.file.seek(0)
        filename = f"{uuid4()}{ext}"
        file_path = f"{UPLOAD_DIR}/{filename}"

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(image.file, buffer)

        news.image = f"/static/uploads/news/{filename}"
        news.image_hash = new_image_hash
        news.image_size = os.path.getsize(file_path)

    db.commit()

    return RedirectResponse("/dashboard/news", status_code=302)


# ====================================================
# DELETE NEWS
# ====================================================
@router.post("/dashboard/news/delete/{news_id}")
def delete_news(news_id: int,request:Request, db: Session = Depends(get_db)):

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
    return request.app.state.render_with_csrf(
        templates_instance=templates,
        request=request,
        template_name="frontend/news.html",
        context={
            "news": news
        }
    )


# ====================================================
# NEWS DETAIL
# ====================================================
# ====================================================
@router.get("/news/{slug}")
def news_detail(slug: str, request: Request, db: Session = Depends(get_db)):
    news = db.query(News).options(joinedload(News.comments)).filter(News.slug == slug).first()
    
    if not news:
        raise HTTPException(status_code=404, detail="News not found")

    comments = news.comments if news.comments else []
    related_news = db.query(News).filter(News.id != news.id).order_by(News.created_at.desc()).limit(4).all()

    # 🔒 PHASE 1: HARDENED DEDUPLICATED IP RESOLUTION & HASHING
    ip_raw = request.headers.get("CF-Connecting-IP") or request.headers.get("X-Real-IP") or request.client.host
    ip_str = str(ip_raw).split(",")[0].strip()
    hashed_ip = hashlib.sha256(ip_str.encode("utf-8")).hexdigest()

    # 🔒 PHASE 2: DEFENSIVE LEDGER QUERY BOUNDARIES
    session_user_id = request.session.get("user_id")
    view_query = db.query(StreamLog).filter(
        StreamLog.content_type == "news_view",
        StreamLog.content_id == news.id
    )
    
    if session_user_id:
        already_viewed = view_query.filter(
            (StreamLog.ip_address == hashed_ip) | (StreamLog.user_id == session_user_id)
        ).first()
    else:
        already_viewed = view_query.filter(StreamLog.ip_address == hashed_ip).first()

    # 🔒 PHASE 3: IMMUTABLE VIEW INCREMENTATION LOCK
    if not already_viewed:
        news.views = (news.views or 0) + 1
        log = StreamLog(
            user_id=session_user_id,
            content_type="news_view",
            content_id=news.id,
            ip_address=hashed_ip
        )
        db.add(log)
        try:
            db.commit()
            print(f"[Analytics] Logged unique news view for ID: #{news.id}")
        except Exception:
            db.rollback()
    else:
        db.refresh(news)

    # 🔒 PHASE 4: SECURE DYNAMIC LINK PREVIEW ROUTING METRICS
    if news.image:
        meta_image = f"https://therealbam.com{news.image}"
    else:
        meta_image = "https://therealbam.com"

    return request.app.state.render_with_csrf(
        templates_instance=templates,
        request=request,
        template_name="frontend/news_detail.html",
        context={
            "news": news,
            "comments": comments,
            "related_news": related_news,
            "meta_title": news.title,
            "meta_description": (
                news.content[:160]
                if news.content
                else "Read the latest tech updates and news on BAM-Tech."
            ),
            "meta_image": meta_image
        }
    )

# ====================================================
# ADD COMMENT
# ====================================================
@router.post("/news/{news_id}/comment")
async def add_news_comment(
    news_id: int,
    request: Request,
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
