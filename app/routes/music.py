from fastapi import (
    APIRouter, Request, Depends, Form, UploadFile, File, BackgroundTasks, HTTPException
)
import magic
import aiofiles  # Make sure to install aiofiles via pip
from werkzeug.utils import secure_filename
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from app.models.stream_log import StreamLog
from sqlalchemy.orm import Session, joinedload
from app.models.subscriber import Subscriber
from app.services.email_service import send_email
from app.models.category import Category
import os
import uuid
# Database and App Configuration Imports
from app.core.database import get_db
from app.core.config import settings
import secrets
import hashlib
import shutil
from sqlalchemy import update
from uuid import uuid4
from app.models.music import Music
from app.models.comment import Comment
#from app.main import csrf_signer

router = APIRouter(prefix="/dashboard/music", tags=["Music"])
templates = Jinja2Templates(directory="app/templates")

UPLOAD_DIR_AUDIO = "app/static/uploads/music/audio"
UPLOAD_DIR_COVERS = "app/static/uploads/music/covers"
os.makedirs(UPLOAD_DIR_AUDIO, exist_ok=True)
os.makedirs(UPLOAD_DIR_COVERS, exist_ok=True)

ALLOWED_AUDIO = [".mp3", ".wav", ".ogg", ".m4a", ".aac", ".flac"]
ALLOWED_IMAGES = [".jpg", ".jpeg", ".png", ".webp"]
def generate_file_hash(file):
    hasher = hashlib.sha256()
    pos = file.tell()  # save current position
    
    file.seek(0)
    for chunk in iter(lambda: file.read(4096), b""):
        hasher.update(chunk)
    
    file.seek(pos)  # restore position
    return hasher.hexdigest()

def format_file_size(size_bytes):
    if size_bytes >= 1024 ** 3:
        return f"{round(size_bytes / 1024 ** 3, 2)} GB"
    elif size_bytes >= 1024 ** 2:
        return f"{round(size_bytes / 1024 ** 2, 2)} MB"
    elif size_bytes >= 1024:
        return f"{round(size_bytes / 1024, 2)} KB"
    return f"{size_bytes} Bytes"

@router.get("")
def music_page(
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
    musics = (
        db.query(Music)
        .options(joinedload(Music.category))
        .order_by(Music.id.desc())
        .offset(offset)
        .limit(per_page)
        .all()
    )
    
    # 3. Aggregate tracking parameters metric metrics
    total_musics = db.query(Music).count()
    categories = db.query(Category).all()

    total_pages = (total_musics + per_page - 1) // per_page
    if total_pages < 1:
        total_pages = 1
        
    has_prev = page > 1
    has_next = page < total_pages

    #  Explicitly named parameters pass structural token pipelines
    return request.app.state.render_with_csrf(
        templates_instance=templates,
        request=request,
        template_name="dashboard/music/index.html",
        context={
            "musics": musics,
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
# CREATE MUSIC PAGE                                                                     # ====================================================
@router.get("/create")
def create_music_page(request: Request, db: Session = Depends(get_db)):
    categories = db.query(Category).all()
    return request.app.state.render_with_csrf(
        templates_instance=templates,
        request=request,
        template_name="dashboard/music/create.html",
        context={
            "categories": categories
        }
    )

@router.post("/create")
async def create_music(
    request: Request,
    background_tasks: BackgroundTasks,
    title: str = Form(...),
    artist: str = Form(...),
    category_id: int = Form(...),
    music: UploadFile = File(...),
    description: str = Form(None),
    cover_image: UploadFile = File(None),
    db: Session = Depends(get_db),
):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(401, "Login required")

    # 🔑 FIXED: Restored the tuple slice [1] so splitext doesn't cause a tuple error
    ext = os.path.splitext(music.filename)[1].lower()

    if ext not in ALLOWED_AUDIO:
        raise HTTPException(400, f"Invalid audio format extension: {ext}")

    # ====================================================
    # ASYNCHRONOUS HEADER AND VALIDATION FIX
    # ====================================================
    # 1. Read file headers asynchronously
    header_bytes = await music.read(2048)
    await music.seek(0)  

    # 2. Extract and validate MIME headers cleanly
    mime = magic.from_buffer(header_bytes, mime=True)
    
    # 🔑 FIXED: Added 'application/octet-stream' to allow raw stream uploads sent by JavaScript FormData
    ALLOWED_MIMES = [
        "audio/mpeg", "audio/wav", "audio/ogg", "audio/mp4", 
        "audio/aac", "audio/flac", "application/octet-stream"
    ]
    
    if mime not in ALLOWED_MIMES:
        raise HTTPException(400, f"Invalid file type: detected {mime}")

    # 3. Generate and check file hash securely
    file_hash = generate_file_hash(music.file)
    music.file.seek(0)  

    existing = db.query(Music).filter(Music.file_hash == file_hash).first()
    if existing:
        raise HTTPException(400, "Music file already exists in our system storage.")

    # 4. Stream and write the media asset file to hard disk space
    audio_filename = f"{uuid4()}{ext}"
    audio_path = os.path.join(UPLOAD_DIR_AUDIO, audio_filename)

    with open(audio_path, "wb") as buffer:
        shutil.copyfileobj(music.file, buffer)

    audio_url = f"music/audio/{audio_filename}"
    file_size = os.path.getsize(audio_path)
    # ======================
    # COVER IMAGE
    # ======================
    cover_url = None

    if cover_image and cover_image.filename:
        safe_cover = secure_filename(cover_image.filename)
        img_ext = os.path.splitext(safe_cover)[1].lower()

        if img_ext not in ALLOWED_IMAGES:
            raise HTTPException(400, "Invalid image format")

        # Removed unused dead code vars (secure_img_name, UPLOAD_DIR) causing compilation errors
        cover_filename = f"{uuid4()}{img_ext}"
        cover_path = os.path.join(UPLOAD_DIR_COVERS, cover_filename)
        with open(cover_path, "wb") as buffer:
            shutil.copyfileobj(cover_image.file, buffer)

        cover_url = f"music/covers/{cover_filename}"

    # ======================
    # SAVE DB
    # ======================
    new_music = Music(
        title=title.strip(),
        artist=artist.strip(),
        description=description.strip() if description else None,
        music_file=audio_url,
        cover_image=cover_url,
        file_size=file_size,
        file_size_display=format_file_size(file_size),
        file_hash=file_hash,
        user_id=int(user_id),
        category_id=category_id
    )
    
    db.add(new_music)
    db.commit()
    db.refresh(new_music)

    # ======================
    # EMAIL NOTIFICATIONS
    # ======================
    subscribers = db.query(Subscriber).all()
    for sub in subscribers:
        background_tasks.add_task(
            send_email,
            sub.email,
            f"New Music: {new_music.title}",
            f"{new_music.artist} just uploaded new music."
        )
    return RedirectResponse("/dashboard/music", status_code=303)

@router.get("/edit/{music_id}")
def edit_music(music_id: int, request: Request,db: Session = Depends(get_db)):
    music = db.query(Music).filter(Music.id == music_id).first()
    if not music:
        raise HTTPException(404, "Music not found")
    categories = db.query(Category).all()
    return request.app.state.render_with_csrf(
        templates_instance=templates,
        request=request,
        template_name="dashboard/music/edit.html",
        context={
            "music": music,
            "categories": categories
        }
    )
@router.post("/update/{music_id}")
async def update_music(
    music_id: int, 
    request: Request,
    title: str = Form(...), 
    artist: str = Form(...),
    description: str = Form(None),
    music_file: UploadFile = File(None),
    cover_image: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    # 1. Access Control Validation
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(401, "Login required")

    music = db.query(Music).filter(Music.id == music_id).first()
    if not music:
        raise HTTPException(404, "Music record not found")
    if music.user_id != user_id:
        raise HTTPException(403, "Not authorized to modify this track")

    # 2. Update metadata text properties
    music.title = title.strip()
    music.artist = artist.strip()
    music.description = description.strip() if description else None

    # Lists to clean up if database commit crashes downstream
    new_files_written = []

    # 3. Handle asynchronous audio file updates
    if music_file and music_file.filename:
        safe_orig = secure_filename(music_file.filename)
        ext = os.path.splitext(safe_orig)[1].lower()
        if ext not in ALLOWED_AUDIO:
            raise HTTPException(400, f"Unsupported audio format: {ext}")

        # Remove old track asset from disk safely
        if music.music_file:
            old_path = os.path.join("app/static", music.music_file)
            if os.path.exists(old_path):
                os.remove(old_path)

        secure_audio_name = f"{uuid4().hex}{ext}"
        audio_save_path = os.path.join(UPLOAD_DIR_AUDIO, secure_audio_name)
        
        # Async writing pipeline via 1MB stream chunks
        async with aiofiles.open(audio_save_path, "wb") as out_file:
            while chunk := await music_file.read(1024 * 1024):
                await out_file.write(chunk)
        
        new_files_written.append(audio_save_path)

        # Map reference paths cleanly (omitting parent /static prefix)
        music.music_file = f"music/audio/{secure_audio_name}"
        music.file_size = os.path.getsize(audio_save_path)
        music.file_size_display = format_file_size(music.file_size)

    # 4. Handle asynchronous cover image updates
    if cover_image and cover_image.filename:
        safe_cover = secure_filename(cover_image.filename)
        img_ext = os.path.splitext(safe_cover)[1].lower()
        if img_ext not in ALLOWED_IMAGES:
            # Drop the freshly saved audio track if image type validation checks fail
            for path in new_files_written:
                if os.path.exists(path): os.remove(path)
            raise HTTPException(400, f"Unsupported cover artwork format: {img_ext}")

        # Remove old cover asset from disk safely
        if music.cover_image:
            old_cover_path = os.path.join("app/static", music.cover_image)
            if os.path.exists(old_cover_path):
                os.remove(old_cover_path)

        secure_img_name = f"{uuid.uuid4().hex}{img_ext}"
        img_save_path = os.path.join(UPLOAD_DIR_COVERS, secure_img_name)
        
        async with aiofiles.open(img_save_path, "wb") as out_file:
            while chunk := await cover_image.read(1024 * 1024):
                await out_file.write(chunk)
        new_files_written.append(img_save_path)
        music.cover_image = f"music/covers/{secure_img_name}"

    # 5. Commit state variations to your database with fallback rolls
    try:
        db.commit()
        db.refresh(music)
    except Exception as e:
        db.rollback()
        # Clean up disk leakage variations if database record indexing snaps
        for path in new_files_written:
            if os.path.exists(path): 
                os.remove(path)
        raise HTTPException(500, "Database processing transaction execution failure.")

    # 6. Redirect back using standard 303 browser redirect
    return RedirectResponse("/dashboard/music", status_code=303)
 # ====================================================
 # DELETE MUSIC
  # ====================================================
@router.post("/delete/{music_id}")
async def delete_music(
    request: Request,
    music_id: int,
    db: Session = Depends(get_db)
):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(401, "Login required")

    music = db.query(Music).filter(Music.id == music_id).first()
    if not music:
        raise HTTPException(404, "Music not found")
    if music.user_id != user_id:
        raise HTTPException(403, "Not allowed")
    if music.music_file:
        path = os.path.join("app", music.music_file.lstrip("/"))
        if os.path.exists(path):
            os.remove(path)
    if music.cover_image:
        path = os.path.join("app", music.cover_image.lstrip("/"))
        if os.path.exists(path):
            os.remove(path)

    db.delete(music)
    db.commit()

    return RedirectResponse("/dashboard/music", status_code=302)
 # ====================================================
 # Download MUSIC
 # ====================================================
@router.get("/download/{music_id}")
def download_music(music_id: int, request: Request, db: Session = Depends(get_db)):
    music = db.query(Music).filter(Music.id == music_id).first()
    if not music:
        raise HTTPException(404, "Music not found")

    safe_name = os.path.basename(music.music_file)
    file_path = os.path.join(
        "app/static/uploads/music/audio", 
         safe_name)

    if not os.path.exists(file_path):
        raise HTTPException(404, "Audio file not found")

    db.execute(
        update(Music)
      .where(Music.id == music_id)
      .values(downloads=Music.downloads + 1) # fixed: downloads not views
    )

    log = StreamLog(
        user_id=request.session.get("user_id"),
        content_type="music_download",
        content_id=music.id,
        ip_address=hashlib.sha256(request.client.host.encode()).hexdigest()
    )
    db.add(log)
    db.commit()

    return FileResponse(
        path=file_path,
        filename=f"{music.title}{os.path.splitext(safe_name)[1]}",
        media_type="audio/mpeg",
        filename_compat="utf-8"
    )

 # ====================================================
 # track MUSIC
# ====================================================
@router.post("/{music_id}/play")
def track_music_play(music_id: int, request: Request, db: Session = Depends(get_db)):
    music = db.query(Music).filter(Music.id == music_id).first()
    if not music:
        raise HTTPException(404, "Music not found")

    db.execute(update(Music).where(Music.id == music_id).values(views=Music.views + 1))
    log = StreamLog(
        user_id=request.session.get("user_id"),
        content_type="music",
        content_id=music.id,
        ip_address=hashlib.sha256(request.client.host.encode()).hexdigest()
    )
    db.add(log)
    db.commit()
    return {"success": True}
# ====================================================
# MUSIC DETAILS PAGE
# ====================================================

@router.get("/{music_id}")
def music_detail(music_id: int, request: Request, db: Session = Depends(get_db)):
    music = db.query(Music).options(joinedload(Music.comments)).filter(Music.id == music_id).first()
    if not music:
        raise HTTPException(404, "Music not found")

    db.execute(update(Music).where(Music.id == music_id).values(views=Music.views + 1))
    db.commit()
    db.refresh(music)
    return request.app.state.render_with_csrf(
        templates_instance=templates,
        request=request,
        template_name="frontend/music_detail.html",
        context={
            "music": music
        }
    )

# ====================================================                                  # FRONTEND MUSIC PAGE
# ====================================================

@router.get("/frontend")
def frontend_music(request: Request, db: Session = Depends(get_db)):
    musics = db.query(Music).options(joinedload(Music.comments)).order_by(Music.id.desc()).all()
    return request.app.state.render_with_csrf(
        templates_instance=templates,
        request=request,
        template_name="frontend/music.html",
        context={
            "musics": musics
        }
    )
# ====================================================
# ADD MUSIC COMMENT
# NORMAL FORM POST
# ====================================================

@router.post("/{music_id}/comment")
async def add_music_comment(music_id: int, request: Request, db: Session = Depends(get_db)):
    music = db.query(Music).filter(Music.id == music_id).first()
    if not music:
        raise HTTPException(404, "Music not found")
    comment = Comment(name=form.get("name"), content=form.get("content"), music_id=music_id)
    db.add(comment)
    db.commit()
    return RedirectResponse("/dashboard/music/frontend", status_code=303)
# ====================================================
# AJAX LIVE COMMENT
# ====================================================
@router.post("/{music_id}/comment/json")
def add_music_comment_json(
    music_id: int,
    request: Request,
    name: str = Form(...),
    content: str = Form(...),
    db: Session = Depends(get_db)
):
    music = db.query(Music).filter(Music.id == music_id).first()

    if not music:
        raise HTTPException(status_code=404, detail="Music not found")
    
    comment = Comment(name=name, content=content, music_id=music_id)
    db.add(comment)
    db.commit()
    db.refresh(comment)

    return {
        "id": comment.id,
        "name": comment.name,
        "content": comment.content,
        "created_at": str(comment.created_at)
    }

@router.get("/stream/{music_id}")
def stream_music(music_id: int, db: Session = Depends(get_db)):
    music = db.query(Music).filter(Music.id == music_id).first()

    if not music:
        raise HTTPException(404)

    filename = os.path.basename(music.music_file)
    file_path = os.path.join("app/static/uploads/music/audio", filename)

    return FileResponse(
        file_path,
        media_type="audio/mpeg"
    )
