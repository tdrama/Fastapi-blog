import os
import uuid
import hashlib
import aiofiles
from datetime import datetime
from fastapi import APIRouter, Request, Depends, Form, File, UploadFile, BackgroundTasks, HTTPException, status
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload
from werkzeug.utils import secure_filename

# Database and Core Engine Dependency Models
from app.core.database import get_db
from app.core.limiter import limiter
from app.models.video import Video
from app.models.comment import Comment
from app.models.category import Category
from app.models.subscriber import Subscriber
from app.services.email_service import send_email

router = APIRouter(tags=["Videos Management Control"])
templates = Jinja2Templates(directory="app/templates")

UPLOAD_DIR = "app/static/uploads/videos"
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}

class CommentPayload(BaseModel):
    name: str
    content: str


# ====================================================
# HELPER CORE CONSTRUCTORS
# ====================================================
def generate_file_hash(file_object) -> str:
    hasher = hashlib.md5()
    pos = file_object.tell()
    file_object.seek(0)
    for chunk in iter(lambda: file_object.read(4096), b""):
        hasher.update(chunk)
    file_object.seek(pos)
    return hasher.hexdigest()


def format_file_size(size_bytes: int) -> str:
    if size_bytes >= 1024 * 1024 * 1024:
        return f"{round(size_bytes / (1024 * 1024 * 1024), 2)} GB"
    elif size_bytes >= 1024 * 1024:
        return f"{round(size_bytes / (1024 * 1024), 2)} MB"
    elif size_bytes >= 1024:
        return f"{round(size_bytes / 1024, 2)} KB"
    return f"{size_bytes} Bytes"


# ====================================================
# 1. ADMIN VIDEO GRID LISTING
# ====================================================
@router.get("/dashboard/videos", response_class=HTMLResponse)
# ✅ FIXED: Upgraded to async def to completely stop anyio thread-group errors
async def admin_videos(request: Request, db: Session = Depends(get_db)):


    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse(url="/auth/login", status_code=303)

    try:
        page = int(request.query_params.get("page", 1))
        if page < 1: page = 1
    except ValueError:
        page = 1

    per_page = 10  # Number of videos per listing viewport rows
    offset = (page - 1) * per_page

    # Query matching slice maps
    videos = (
        db.query(Video)
        .options(joinedload(Video.category), joinedload(Video.comments))
        .order_by(Video.created_at.desc())
        .offset(offset)
        .limit(per_page)
        .all()
    )
    
    total_videos = db.query(Video).count()
    categories = db.query(Category).all()

    # Pagination data boundaries structures
    total_pages = (total_videos + per_page - 1) // per_page
    has_prev = page > 1
    has_next = page < total_pages

    render_with_csrf = request.app.state.render_with_csrf
    return render_with_csrf(
        templates_instance=templates,
        request=request,
        template_name="dashboard/videos/index.html",
        context={
            "videos": videos,
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
# 2. RENDER CREATION PANEL SCREEN
# ====================================================
@router.get("/dashboard/videos/create", response_class=HTMLResponse)
# ✅ FIXED: Upgraded to async def
async def create_video_page(request: Request, db: Session = Depends(get_db)):
    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse(url="/auth/login", status_code=303)

    categories = db.query(Category).all()
    render_with_csrf = request.app.state.render_with_csrf
    return render_with_csrf(
        templates_instance=templates,
        request=request,
        template_name="dashboard/videos/create.html",
        context={
            "categories": categories
        }
    )


# ====================================================
# 3. ASYNCHRONOUS SECURE ASSET CREATION CORE
# ====================================================
@router.post("/dashboard/videos/create")
async def create_video(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required.")

    form_data = await request.form()
    title = form_data.get("title")
    description = form_data.get("description")
    category_id_raw = form_data.get("category_id")
    
    # Aligned target key extraction fallback check to accept 'video_file' from HTML input forms
    video_upload = form_data.get("video_file") or form_data.get("video")

    if not title or not video_upload or not category_id_raw:
        raise HTTPException(status_code=400, detail="Missing required input variables.")

    try:
        category_id = int(category_id_raw)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid category identity constraint value.")

    # Optional thumbnail file field parsing logic
    thumbnail_upload = form_data.get("thumbnail")
    thumbnail_url_path = "videos/thumbnail.mp4"  # Default video fallback mapping parameter string

    if not hasattr(video_upload, "filename") or not video_upload.filename:
        raise HTTPException(status_code=400, detail="The upload container lacks a valid file payload parameter.")

    safe_orig = secure_filename(video_upload.filename)
    ext = os.path.splitext(safe_orig)[1].lower()

    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Unsupported video format type extension.")

    # Run direct asset checksum validations
    file_hash = generate_file_hash(video_upload.file)
    existing = db.query(Video).filter(Video.file_hash == file_hash).first()
    if existing:
        raise HTTPException(status_code=400, detail="This exact video file is already registered.")

    video_upload.file.seek(0)

    secure_video_token = f"vid_{uuid.uuid4().hex}{ext}"
    physical_video_save_path = os.path.join(UPLOAD_DIR, secure_video_token)
    new_files_written = []

    #  FIXED FILE STREAM: Swapped old blocking chunks with full async buffer loops to protect Termux workers
    try:
        async with aiofiles.open(physical_video_save_path, "wb") as out_file:
            while chunk := await video_upload.read(1024 * 1024 * 4): # 4MB dynamic stream blocks
                await out_file.write(chunk)
        new_files_written.append(physical_video_save_path)
    except Exception as e:
        if os.path.exists(physical_video_save_path): os.remove(physical_video_save_path)
        raise HTTPException(status_code=500, detail="Disk streaming error during video generation loops.")

    # Process optional thumbnail preview artwork image uploads asynchronously if attached
    if thumbnail_upload and hasattr(thumbnail_upload, "filename") and thumbnail_upload.filename:
        thumb_orig = secure_filename(thumbnail_upload.filename)
        thumb_ext = os.path.splitext(thumb_orig)[1].lower()
        if thumb_ext in {".jpg", ".jpeg", ".png", ".webp"}:
            secure_thumb_token = f"thumb_{uuid.uuid4().hex}{thumb_ext}"
            physical_thumb_save_path = os.path.join(UPLOAD_DIR, secure_thumb_token)

            try:
                thumbnail_upload.file.seek(0)
                async with aiofiles.open(physical_thumb_save_path, "wb") as out_file:
                    while chunk := await thumbnail_upload.read(1024 * 1024):
                        await out_file.write(chunk)
                new_files_written.append(physical_thumb_save_path)
                thumbnail_url_path = f"videos/{secure_thumb_token}"
            except Exception:
                for p in new_files_written:
                    if os.path.exists(p): os.remove(p)
                raise HTTPException(status_code=500, detail="Disk streaming error during thumbnail processing.")

    # Compile explicit absolute prefix paths right inside the database record columns
    video_url_path = f"videos/{secure_video_token}"
    calculated_file_size = os.path.getsize(physical_video_save_path)

    try:
        new_video = Video(
            title=title.strip(),
            description=description.strip() if description else None,
            video_file=video_url_path,
            thumbnail=thumbnail_url_path,  # Now cleanly records complete absolute or placeholder strings
            file_size=calculated_file_size,
            file_size_display=format_file_size(calculated_file_size),
            file_hash=file_hash,
            user_id=int(user_id),
            category_id=category_id,
            views=0
        )
        db.add(new_video)
        db.commit()
        db.refresh(new_video)
    except Exception as db_err:
        db.rollback()
        for p in new_files_written:
            if os.path.exists(p): os.remove(p)
        raise HTTPException(status_code=500, detail="Database write sequence execution crash loop.")

    # Asynchronous broadcast loop notifications pipeline
    try:
        subscribers = db.query(Subscriber).all()
        for sub in subscribers:
            background_tasks.add_task(
                send_email,
                sub.email,
                f"New Video Upload: {new_video.title}",
                new_video.description or "Check out our fresh content additions!"
            )
    except Exception:
        pass

    if "application/x-www-form-urlencoded" in request.headers.get("content-type", "").lower():
        return RedirectResponse("/dashboard/videos", status_code=303)

    return JSONResponse(status_code=201, content={"success": True, "detail": "Video record saved securely."})


# ====================================================
# EDIT VIDEO PAGE (FINANCIAL/CMS VIEW WORKER PANEL)
# ====================================================
@router.get("/dashboard/videos/edit/{video_id}", response_class=HTMLResponse)
async def edit_video_page(
    video_id: int,                                                         
    request: Request,
    db: Session = Depends(get_db)
):
    # Enforce admin credentials matching your dashboard architecture requirements
    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse(url="/auth/login", status_code=303)

    # ✅ FIXED INDENTATION: Query the database object first before checking constraints
    video = db.query(Video).filter(Video.id == video_id).first()
    
    if not video:
        raise HTTPException(
            status_code=404, 
            detail="The requested video asset record was not found."
        )

    categories = db.query(Category).all()
    render_with_csrf = request.app.state.render_with_csrf

    # Return template view through secure helper tracking loop
    return render_with_csrf(
        templates_instance=templates,
        request=request,
        template_name="dashboard/videos/edit.html",
        context={
            "video": video,
            "categories": categories
        }
    )

@router.post("/dashboard/videos/update/{video_id}")
async def update_video_action(
    video_id: int,
    request: Request,
    title: str = Form(...),
    description: str = Form(None),
    category_id: int = Form(...),
    db: Session = Depends(get_db)
):
    # Enforce credentials matching your dashboard architecture requirements
    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse(url="/auth/login", status_code=303)

    # Query the database object first before checking constraints
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(
            status_code=404,
            detail="The requested video asset record was not found."
        )

    # Update text fields
    video.title = title.strip()
    video.description = description.strip() if description else None
    video.category_id = category_id

    # Commit changes securely to the database
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Database write sequence failed during update.")

    # Return redirect to the main videos list dashboard view
    return RedirectResponse(url="/dashboard/videos", status_code=303)

# ====================================================
# REMOVE/DROP DATABASE ENTITY RECORD CHANNEL
# ====================================================
@router.post("/dashboard/videos/delete/{video_id}")
async def delete_video(video_id: int, request: Request, db: Session = Depends(get_db)):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Login credentials required.")

    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video record not found.")

    # Safely clear physical files off disk storage
    for path_str in [video.video_file, video.thumbnail]:
        if path_str and path_str.startswith("/static/"):
            clean_filename = os.path.basename(path_str)
            physical_disk_path = os.path.join(UPLOAD_DIR, clean_filename)
            if os.path.exists(physical_disk_path):
                os.remove(physical_disk_path)

    try:
        db.delete(video)
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Database dropping transaction sequence fault.")

    if "application/x-www-form-urlencoded" in request.headers.get("content-type", "").lower():
        return RedirectResponse("/dashboard/videos", status_code=303)

    return JSONResponse(status_code=200, content={"success": True, "detail": "Video dropped successfully."})
