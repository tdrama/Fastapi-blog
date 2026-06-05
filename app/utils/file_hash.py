import hashlib
from fastapi import UploadFile

def generate_file_hash(file: UploadFile) -> str:
    content = file.file.read()
    file.file.seek(0)  # IMPORTANT reset pointer

    return hashlib.sha256(content).hexdigest()
