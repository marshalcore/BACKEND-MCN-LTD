import os
from fastapi import UploadFile
from uuid import uuid4

UPLOAD_DIR = "static/uploads"

def save_upload(file: UploadFile, subfolder: str) -> str:
    ext = file.filename.split(".")[-1]
    filename = f"{uuid4().hex}.{ext}"
    folder_path = os.path.join(UPLOAD_DIR, subfolder)

    os.makedirs(folder_path, exist_ok=True)

    file_path = os.path.join(folder_path, filename)

    with open(file_path, "wb") as buffer:
        buffer.write(file.file.read())

    return file_path
