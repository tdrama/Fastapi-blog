from fastapi import (
    APIRouter,
    Request,
    Depends,
    Form,
    File,
    UploadFile,
    BackgroundTasks,
    HTTPException
)
from app.models.stream_log import StreamLog
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from app.models.subscriber import Subscriber
from app.services.email_service import send_email
from sqlalchemy.orm import Session, joinedload
from app.models.category import Category

import os
import shutil
import hashlib

from uuid import uuid4

from app.core.database import get_db

from app.models.video import Video
from app.models.comment import Comment

# ====================================================
# ROUTER
# ====================================================

router = APIRouter()

templates = Jinja2Templates(
    directory="app/templates"
)

# ====================================================
# UPLOAD DIRECTORY
# ====================================================

UPLOAD_DIR = "app/static/uploads/videos"

os.makedirs(
    UPLOAD_DIR,
    exist_ok=True
)

# ====================================================
# ALLOWED FORMATS
# ====================================================

ALLOWED_EXTENSIONS = [
    ".mp4",
    ".mov",
    ".avi",
    ".mkv",
    ".webm"
]

# ====================================================
# FILE HASH
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
# FORMAT FILE SIZE
# ====================================================

def format_file_size(size_bytes):

    if size_bytes >= 1024 * 1024 * 1024:

        return f"{round(size_bytes / (1024 * 1024 * 1024), 2)} GB"

    elif size_bytes >= 1024 * 1024:

        return f"{round(size_bytes / (1024 * 1024), 2)} MB"

    elif size_bytes >= 1024:

        return f"{round(size_bytes / 1024, 2)} KB"

    return f"{size_bytes} Bytes"

# ====================================================
# ADMIN VIDEO LIST
# ====================================================

@router.get("/dashboard/videos")
def admin_videos(
    request: Request,
    db: Session = Depends(get_db)
):

    videos = db.query(Video)\
        .options(joinedload(Video.comments))\
        .order_by(Video.id.desc())\
        .all()

    categories = db.query(Category).all()
    return templates.TemplateResponse(
        "dashboard/videos/index.html",
        {
            "request": request,
            "videos": videos,
            "categories": categories
        }
    )

# ====================================================
# CREATE VIDEO PAGE
# ====================================================

@router.get("/dashboard/videos/create")
def create_video_page(
    request: Request,db: Session = Depends(get_db)
):
   
    videos = db.query(Video).all() 
    categories = db.query(Category).all()
    

    for cat in categories:
        print(cat.id, cat.name)
    return templates.TemplateResponse(
        "dashboard/videos/create.html",
        {
            "request": request,
            "categories": categories
        }
    )

# =========================================
# CREATE VIDEO
# ====================================================
@router.post("/dashboard/videos/create")
def create_video(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    title: str = Form(...),
    description: str = Form(None),
    video: UploadFile = File(...),
    category_id: int = Form(...)
):

    # Get logged-in user
    user_id = request.session.get("user_id")

    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="Login required"
        )

    ext = os.path.splitext(video.filename)[1].lower()

    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Invalid video format"
        )

    file_hash = generate_file_hash(video.file)

    existing = db.query(Video)\
        .filter(Video.file_hash == file_hash)\
        .first()

    if existing:
        raise HTTPException(
            status_code=400,
            detail="Video already exists"
        )

    video.file.seek(0)

    filename = f"{uuid4()}_{video.filename}"

    file_path = os.path.join(
        UPLOAD_DIR,
        filename
    )

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(
            video.file,
            buffer
        )

    video_url = f"/static/uploads/videos/{filename}"

    file_size = os.path.getsize(file_path)

    new_video = Video(
        title=title,
        description=description,
        video_file=video_url,
        file_size=file_size,
        file_size_display=format_file_size(file_size),
        file_hash=file_hash,
        user_id=user_id,
        category_id=category_id,
        views=0
    )

    db.add(new_video)

    db.commit()

    db.refresh(new_video)

    subscribers = db.query(Subscriber).all()
    for sub in subscribers:
        background_tasks.add_task(
           send_email,
               sub.email,
               f"New Video: {new_video.title}",
               new_video.description or ""
           )

    return RedirectResponse(
           "/dashboard/videos",
           status_code=302
    )

# ====================================================
# EDIT VIDEO PAGE
# ====================================================

@router.get("/dashboard/videos/edit/{video_id}")
def edit_video_page(
    video_id: int,
    request: Request,
    db: Session = Depends(get_db)
):

    video = db.query(Video)\
        .filter(Video.id == video_id)\
        .first()

    if not video:

        raise HTTPException(
            status_code=404,
            detail="Video not found"
        )
    categories = db.query(Category).all()

    return templates.TemplateResponse(
        "dashboard/videos/edit.html",
        {
            "request": request,
            "video": video,
            "categories": categories
        }
    )

# ====================================================
# UPDATE VIDEO
# ====================================================
@router.post("/dashboard/videos/update/{video_id}")
def update_video(
    video_id: int,
    title: str = Form(...),
    description: str = Form(None),
    video_file: UploadFile = File(None),
    db: Session = Depends(get_db)
):

    video = db.query(Video).filter(Video.id == video_id).first()

    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    video.title = title
    video.description = description

    # =========================================
    # SAFE VIDEO UPDATE (FIXED)
    # =========================================
    if video_file and video_file.filename:

        ext = os.path.splitext(video_file.filename)[1].lower()

        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail="Invalid video format"
            )

        # delete old file safely
        if video.video_file:
            old_path = "app" + video.video_file
            if os.path.exists(old_path):
                os.remove(old_path)

        # save new file
        filename = f"{uuid4()}_{video_file.filename}"
        file_path = os.path.join(UPLOAD_DIR, filename)

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(video_file.file, buffer)

        video.video_file = f"/static/uploads/videos/{filename}"
        video.file_size = os.path.getsize(file_path)
        video.file_size_display = format_file_size(video.file_size)

    db.commit()

    return RedirectResponse("/dashboard/videos", status_code=302)
# ====================================================
# DELETE VIDEO
# ====================================================

@router.get("/dashboard/videos/delete/{video_id}")
def delete_video(
    video_id: int,
    db: Session = Depends(get_db)
):

    video = db.query(Video)\
        .filter(Video.id == video_id)\
        .first()

    if not video:

        raise HTTPException(
            status_code=404,
            detail="Video not found"
        )

    # DELETE FILE

    if video.video_file:

        file_path = f"app{video.video_file}"

        if os.path.exists(file_path):

            os.remove(file_path)

    db.delete(video)

    db.commit()

    return RedirectResponse(
        "/dashboard/videos",
        status_code=302
    )

# ====================================================
# FRONTEND VIDEOS PAGE
# ====================================================

@router.get("/videos")
def frontend_videos(
    request: Request,
    db: Session = Depends(get_db)
):

    videos = db.query(Video)\
        .options(joinedload(Video.comments))\
        .order_by(Video.id.desc())\
        .all()

    return templates.TemplateResponse(
        "frontend/videos.html",
        {
            "request": request,
            "videos": videos
        }
    )

# ====================================================
# VIDEO DETAIL PAGE
# ====================================================

@router.get("/videos/{video_id}")
def video_detail(
    video_id: int,
    request: Request,
    db: Session = Depends(get_db)
):

    video = db.query(Video)\
        .options(joinedload(Video.comments))\
        .filter(Video.id == video_id)\
        .first()

    if not video:

        raise HTTPException(
            status_code=404,
            detail="Video not found"
        )

    # INCREASE VIEWS

    video.views += 1

    db.commit()
   # save stream activity
    log = StreamLog(
        user_id=request.session.get("user_id"),
        content_type="video",
        content_id=video.id,
        ip_address=request.client.host
    )

    db.add(log)
    db.commit()

    return templates.TemplateResponse(
        "frontend/video_detail.html",
        {
            "request": request,
            "video": video
        }
    )

# ====================================================
# ADD VIDEO COMMENT
# ====================================================

@router.post("/videos/{video_id}/comment")
def add_video_comment(
    video_id: int,
    name: str = Form(...),
    content: str = Form(...),
    db: Session = Depends(get_db)
):

    video = db.query(Video)\
        .filter(Video.id == video_id)\
        .first()

    if not video:

        raise HTTPException(
            status_code=404,
            detail="Video not found"
        )

    comment = Comment(
        name=name,
        content=content,
        video_id=video.id
    )

    db.add(comment)

    db.commit()

    return RedirectResponse(
        f"/videos/{video_id}",
        status_code=303
    )

# ====================================================
# AJAX VIDEO COMMENT
# ====================================================

@router.post("/videos/{video_id}/comment/json")
def add_video_comment_json(
    video_id: int,
    name: str = Form(...),
    content: str = Form(...),
    db: Session = Depends(get_db)
):

    video = db.query(Video)\
        .filter(Video.id == video_id)\
        .first()

    if not video:

        raise HTTPException(
            status_code=404,
            detail="Video not found"
        )

    comment = Comment(
        name=name,
        content=content,
        video_id=video.id
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

