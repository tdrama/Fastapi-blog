import os
from pathlib import Path
from fastapi import HTTPException

BASE_DIR = Path("app/static/uploads").resolve()


def safe_file_path(requested_path: str) -> Path:
    """
    Safely resolve a requested upload path.

    Prevents path traversal attacks such as:
        ../../.env
        ../../../etc/passwd
    """

    if not requested_path:
        raise HTTPException(
            status_code=400,
            detail="Invalid file path"
        )

    # Remove a leading slash so the path stays relative to BASE_DIR
    clean_path = requested_path.lstrip("/")

    # Resolve the complete path
    path = (BASE_DIR / clean_path).resolve()

    # Verify the resolved path is actually inside BASE_DIR
    try:
        path.relative_to(BASE_DIR)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid file path"
        )

    # Make sure it is a real file
    if not path.is_file():
        raise HTTPException(
            status_code=404,
            detail="File not found"
        )

    return path
