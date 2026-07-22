# app/utils/file.py
import os
from pathlib import Path
from fastapi import HTTPException

BASE_DIR = Path("app/static").resolve()

def safe_file_path(requested_path: str) -> Path:
    """
    Prevent path traversal attacks like ../../.env
    """
    # Clean the path and prevent '..' escapes
    clean_path = requested_path.lstrip("/")
    path = (BASE_DIR /static).resolve()
    
    # Make sure the resolved path is still inside BASE_DIR
    if not str(path).startswith(str(BASE_DIR)):
        raise HTTPException(status_code=400, detail="Invalid file path")
    
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    
    return path
