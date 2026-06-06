from fastapi import (
    APIRouter,
    Request,
    Depends,
    Form,
    UploadFile,
    File,
    BackgroundTasks,
    HTTPException
)
from fastapi.responses import FileResponse
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from app.models.stream_log import StreamLog
from sqlalchemy.orm import Session, joinedload
from app.models.subscriber import Subscriber
from app.services.email_service import send_email
from app.models.category import Category
import os
import hashlib
import shutil

from uuid import uuid4

from app.core.database import get_db

from app.models.music import Music
from app.models.comment import Comment

# ====================================================
# ROUTER
# ====================================================

router = APIRouter(
    prefix="/dashboard/music",
    tags=["Music"]
)

templates = Jinja2Templates(
    directory="app/templates"
)

# ====================================================
# STORAGE PATHS
# ====================================================

UPLOAD_DIR_AUDIO = "app/static/uploads/music/audio"
UPLOAD_DIR_COVERS = "app/static/uploads/music/covers"

os.makedirs(UPLOAD_DIR_AUDIO, exist_ok=True)
os.makedirs(UPLOAD_DIR_COVERS, exist_ok=True)

# ====================================================
# ALLOWED FILES
# ====================================================

ALLOWED_AUDIO = [
    ".mp3",
    ".wav",
    ".ogg",
    ".m4a",
    ".aac",
    ".flac"
]

ALLOWED_IMAGES = [
    ".jpg",
    ".jpeg",
    ".png",
    ".webp"
]

# ====================================================
# FILE HASH
# ====================================================

def generate_file_hash(file):

    hasher = hashlib.sha256()

    pos = file.tell()

    file.seek(0)

    for chunk in iter(lambda: file.read(4096), b""):
        hasher.update(chunk)

    file.seek(pos)

    return hasher.hexdigest()

# ====================================================
# FILE SIZE FORMAT
# ====================================================

def format_file_size(size_bytes):

    if size_bytes >= 1024 ** 3:
        return f"{round(size_bytes / (1024 ** 3), 2)} GB"

    elif size_bytes >= 1024 ** 2:
        return f"{round(size_bytes / (1024 ** 2), 2)} MB"

    elif size_bytes >= 1024:
        return f"{round(size_bytes / 1024, 2)} KB"

    return f"{size_bytes} Bytes"

# ====================================================
# ADMIN MUSIC LIST
# ====================================================
@router.get("")
def music_page(
    request: Request,
    page: int = 1,
    db: Session = Depends(get_db)
):
    page = max(page, 1)
    per_page = 10

    total = db.query(Music).count()

    music = (
        db.query(Music)
        .order_by(Music.id.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    total_pages = (total + per_page - 1) // per_page
    categories = db.query(Category).all()
    return templates.TemplateResponse(
        "dashboard/music/index.html",
        {
            "request": request,
            "musics": music,
            "categories": categories,
            "page": page,
            "total_pages": total_pages
        }
    )
# ====================================================
# CREATE MUSIC PAGE
# ====================================================

@router.get("/create")
def create_music_page(
    request: Request,db: Session = Depends(get_db)
  ):

    categories = db.query(Category).all()
    return templates.TemplateResponse(
        "dashboard/music/create.html",
        {
            "request": request,
            "categories": categories
        }
    )

# ====================================================
# create  music
# ====================================================
@router.post("/create")
def create_music(
    request: Request,
    background_tasks: BackgroundTasks,
    title: str = Form(...),
    artist: str = Form(...),
    description: str = Form(None),
    music: UploadFile = File(...),
    category_id: int = Form(...),
    cover_image: UploadFile = File(None),
    db: Session = Depends(get_db)
   ):

    # GET LOGGED-IN USER ID
    user_id = request.session.get("user_id")

    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="Login required"
        )

    # VALIDATE AUDIO
    ext = os.path.splitext(
        music.filename
    )[1].lower()

    if ext not in ALLOWED_AUDIO:
        raise HTTPException(
            status_code=400,
            detail="Invalid audio format"
        )

    file_hash = generate_file_hash(
        music.file
    )

    existing = db.query(Music)\
        .filter(Music.file_hash == file_hash)\
        .first()

    if existing:
        raise HTTPException(
            status_code=400,
            detail="Music already exists"
        )

    music.file.seek(0)

    # SAVE AUDIO
    audio_filename = f"{uuid4()}_{music.filename}"

    audio_path = os.path.join(
        UPLOAD_DIR_AUDIO,
        audio_filename
    )

    with open(audio_path, "wb") as buffer:
        shutil.copyfileobj(
            music.file,
            buffer
        )

    audio_url = (
        f"/static/uploads/music/audio/{audio_filename}"
    )

    file_size = os.path.getsize(
        audio_path
    )

    # SAVE COVER
    cover_url = None

    if cover_image and cover_image.filename:

        img_ext = os.path.splitext(
            cover_image.filename
        )[1].lower()

        if img_ext not in ALLOWED_IMAGES:
            raise HTTPException(
                status_code=400,
                detail="Invalid image format"
            )

        cover_filename = (
            f"{uuid4()}_{cover_image.filename}"
        )

        cover_path = os.path.join(
            UPLOAD_DIR_COVERS,
            cover_filename
        )

        with open(cover_path, "wb") as buffer:
            shutil.copyfileobj(
                cover_image.file,
                buffer
            )

        cover_url = (
            f"/static/uploads/music/covers/{cover_filename}"
        )

    # SAVE DATABASE
    new_music = Music(
        title=title,
        artist=artist,
        description=description,
        music_file=audio_url,
        cover_image=cover_url,
        file_size=file_size,
        file_size_display=format_file_size(file_size),
        file_hash=file_hash,
        user_id=user_id,
        category_id=category_id
    )

    db.add(new_music)

    db.commit()

    db.refresh(new_music)
   # SEND EMAIL TO SUBSCRIBERS
    subscribers = db.query(Subscriber).all()

    for sub in subscribers:
        background_tasks.add_task(
                send_email,
                sub.email,
                f"New Music: {new_music.title}",
                f"{new_music.artist} just uploaded new music."
            )
        

    return RedirectResponse(
         "/dashboard/music",
         status_code=303
)
#ediy
@router.get("/edit/{music_id}")
def edit_music(
    music_id: int,
    request: Request,
    db: Session = Depends(get_db)
):

    music = db.query(Music).filter(Music.id == music_id).first()

    if not music:
        raise HTTPException(status_code=404, detail="Music not found")
   
    categories = db.query(Category).all()
    return templates.TemplateResponse(
        "dashboard/music/edit.html",
        {
            "request": request,
            "music": music,
            "categories":categories
        }
    )
# ====================================================
# UPDATE MUSIC
# ====================================================
@router.post("/update/{music_id}")
def update_music(
    music_id: int,
    title: str = Form(...),
    artist: str = Form(...),
    description: str = Form(None),
    music_file: UploadFile = File(None),
    cover_image: UploadFile = File(None),
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

    # UPDATE BASIC INFO
    music.title = title
    music.artist = artist
    music.description = description

    # =========================
    # UPDATE AUDIO
    # =========================
    if music_file:

        ext = os.path.splitext(music_file.filename)[1].lower()

        if ext not in ALLOWED_AUDIO:
            raise HTTPException(
                status_code=400,
                detail="Invalid audio format: {ext}"
            )
         # DELETE OLD AUDIO
        if music.music_file:
                 old_path = music.music_file.replace(
                 "/static/",
                 "app/static/"
            )
        if os.path.exists(old_path):
                 os.remove(old_path)
        filename = f"{uuid4()}_{music_file.filename}"

        path = os.path.join(UPLOAD_DIR_AUDIO, filename)

        with open(path, "wb") as buffer:
            shutil.copyfileobj(music_file.file, buffer)

        music.music_file = f"/static/uploads/music/audio/{filename}"

        music.file_size = os.path.getsize(path)

        music.file_size_display = format_file_size(music.file_size)

    # =========================
    # UPDATE COVER
    # =========================
    if cover_image and cover_image.filename:

        ext = os.path.splitext(cover_image.filename)[1].lower()

        if ext not in ALLOWED_IMAGES:
            raise HTTPException(
                status_code=400,
                detail="Invalid image format:{ext}"
            )

        filename = f"{uuid4()}_{cover_image.filename}"

        path = os.path.join(UPLOAD_DIR_COVERS, filename)

        with open(path, "wb") as buffer:
            shutil.copyfileobj(cover_image.file, buffer)

        music.cover_image = f"/static/uploads/music/covers/{filename}"

    # ✅ SAVE CHANGES (VERY IMPORTANT)
    db.commit()
    db.refresh(music)

    return RedirectResponse(
        "/dashboard/music",
        status_code=302
    )
# ====================================================
# DELETE MUSIC
# ====================================================

@router.get("/delete/{music_id}")
def delete_music(
    music_id: int,
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

    # DELETE AUDIO FILE
    if music.music_file:

        path = music.music_file.replace(
            "/static/",
            "app/static/"
        )

        if os.path.exists(path):

            os.remove(path)

    # DELETE COVER FILE
    if music.cover_image:

        path = music.cover_image.replace(
            "/static/",
            "app/static/"
        )

        if os.path.exists(path):

            os.remove(path)

    db.delete(music)

    db.commit()

    return RedirectResponse(
        "/dashboard/music",
        status_code=302
    )

# ====================================================
# FRONTEND MUSIC PAGE
# ====================================================

@router.get("/frontend")
def frontend_music(
    request: Request,
    db: Session = Depends(get_db)
):

    musics = db.query(Music)\
        .options(joinedload(Music.comments))\
        .order_by(Music.id.desc())\
        .all()

    return templates.TemplateResponse(
        "frontend/music.html",
        {
            "request": request,
            "musics": musics
        }
    )

# ====================================================
# ADD MUSIC COMMENT
# NORMAL FORM POST
# ====================================================

@router.post("/{music_id}/comment")
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

    comment = Comment(
        name=name,
        content=content,
        music_id=music_id
    )

    db.add(comment)

    db.commit()

    return RedirectResponse(
        "/dashboard/music/frontend",
        status_code=303
    )

# ====================================================
# AJAX LIVE COMMENT
# ====================================================

@router.post("/{music_id}/comment/json")
def add_music_comment_json(
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

    comment = Comment(
        name=name,
        content=content,
        music_id=music_id
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

@router.post("/{music_id}/play")
def track_music_play(
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

    log = StreamLog(
        user_id=request.session.get("user_id"),
        content_type="music",
        content_id=music.id,
        ip_address=request.client.host
    )

    db.add(log)
    db.commit()

    return {"success": True}
#music download


@router.get("/download/{music_id}")
def download_music(
    music_id: int,
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

    if not os.path.exists(music.music_file):
        raise HTTPException(
            status_code=404,
            detail="Audio file not found"
        )

    music.downloads += 1
    db.commit()

    return FileResponse(
        path=music.music_file,
        filename=f"{music.title}.mp3",
        media_type="audio/mpeg"
    )
# ====================================================
# MUSIC DETAILS PAGE
# ====================================================

@router.get("/{music_id}")
def music_detail(
    music_id: int,
    request: Request,
    db: Session = Depends(get_db)
):

    music = db.query(Music)\
        .options(joinedload(Music.comments))\
        .filter(Music.id == music_id)\
        .first()

    if not music:
        raise HTTPException(
            status_code=404,
            detail="Music not found"
        )

    # COUNT VIEW
    music.views = (music.views or 0) + 1

    db.commit()

    return templates.TemplateResponse(
        "frontend/music_detail.html",
        {
            "request": request,
            "music": music
        }
    )
