# utils/media.py

def media_url(path: str) -> str:
    if not path:
        return None
    return f"/static/uploads/{path}"
