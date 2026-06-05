from app.core.cloud_config import cloudinary
from uuid import uuid4

def upload_video(file, folder="videos"):
    result = cloudinary.uploader.upload_large(
        file,
        resource_type="video",
        folder=folder,
        public_id=str(uuid4())
    )

    return {
        "url": result["secure_url"],
        "public_id": result["public_id"],
        "size": result.get("bytes", 0)
    }


def upload_audio(file, folder="music"):
    result = cloudinary.uploader.upload(
        file,
        resource_type="video",  # audio also uses video type in Cloudinary
        folder=folder,
        public_id=str(uuid4())
    )

    return {
        "url": result["secure_url"],
        "public_id": result["public_id"],
        "size": result.get("bytes", 0)
    }


def upload_image(file, folder="images"):
    result = cloudinary.uploader.upload(
        file,
        folder=folder,
        public_id=str(uuid4())
    )

    return {
        "url": result["secure_url"],
        "public_id": result["public_id"],
        "size": result.get("bytes", 0)
    }
