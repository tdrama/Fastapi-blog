import os
import shutil
import mimetypes
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.video import Video
from app.models.music import Music

router = APIRouter()

# ====================================================
# CONFIGURATIONS & STORAGE PATHS
# ====================================================
# Absolute path to your base upload directory
BASE_UPLOAD_DIR = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "../../static/uploads"
    )
)

# Summernote-specific target subfolders
UPLOAD_DIR_IMAGE = os.path.join(BASE_UPLOAD_DIR, "news/images")
UPLOAD_DIR_VIDEO = os.path.join(BASE_UPLOAD_DIR, "news/videos")
UPLOAD_DIR_PDF   = os.path.join(BASE_UPLOAD_DIR, "news/documents")

# Auto-generate storage paths securely on initialization
os.makedirs(UPLOAD_DIR_IMAGE, exist_ok=True)
os.makedirs(UPLOAD_DIR_VIDEO, exist_ok=True)
os.makedirs(UPLOAD_DIR_PDF, exist_ok=True)


# ====================================================
# 1. NEW: SUMMERNOTE MEDIA UPLOAD CONTROLLER (POST)
# ====================================================
@router.post("/api/media/upload", tags=["Media Upload Manager"])
async def upload_editor_media(
    request: Request,
    file: UploadFile = File(...)
):
    """
    Asynchronous handler that intercepts file streams dropped or selected 
    inside Summernote Lite across all administration editor interfaces.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing valid file payload")

    filename = file.filename
    ext = os.path.splitext(filename)[1].lower()
    unique_filename = f"{uuid4()}{ext}"

    # Route and sort files into dedicated filesystem paths
    if ext in [".jpg", ".jpeg", ".png", ".gif", ".webp"]:
        file_path = os.path.join(UPLOAD_DIR_IMAGE, unique_filename)
        public_url = f"/static/uploads/news/images/{unique_filename}"

    elif ext in [".mp4", ".webm", ".ogg", ".mov"]:
        file_path = os.path.join(UPLOAD_DIR_VIDEO, unique_filename)
        public_url = f"/static/uploads/news/videos/{unique_filename}"

    elif ext == ".pdf":
        file_path = os.path.join(UPLOAD_DIR_PDF, unique_filename)
        public_url = f"/static/uploads/news/documents/{unique_filename}"

    else:
        raise HTTPException(status_code=400, detail=f"Media extensions of type '{ext}' are not permitted")

    # Stream multi-part byte chunks natively down to the disk storage block
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Filesystem write failure: {str(e)}")

    # Return structural JSON tracking map directly back to JavaScript callback loop
    return {"url": public_url}


# ====================================================
# 2. EXISTING: SECURE STORAGE FILE STREAMER (GET)
# ====================================================
@router.get("/file/{file_type}/{file_id}")
def serve_file(
    file_type: str,
    file_id: int,
    db: Session = Depends(get_db)
):
    if file_type not in ["music", "video"]:
        raise HTTPException(status_code=404)

    model = Music if file_type == "music" else Video
    item = db.query(model).filter(model.id == file_id).first()

    if not item:
        raise HTTPException(status_code=404)

    relative_path = (
        item.music_file
        if file_type == "music"
        else item.video_file
    )

    if not relative_path:
        raise HTTPException(status_code=404)

    relative_path = relative_path.lstrip("/")
    file_path = os.path.join(BASE_UPLOAD_DIR, relative_path)
    file_path = os.path.abspath(file_path)

    # Path traversal protection rules
    if not file_path.startswith(BASE_UPLOAD_DIR):
        raise HTTPException(
            status_code=403,
            detail="Access denied"
        )

    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=404,
            detail=f"File not found: {file_path}"
        )

    media_type, _ = mimetypes.guess_type(file_path)

    return FileResponse(
        path=file_path,
        media_type=media_type or "application/octet-stream",
        filename=os.path.basename(file_path)
    )
