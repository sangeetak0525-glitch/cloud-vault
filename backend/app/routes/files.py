from typing import Optional
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from jose import jwt
import uuid
from datetime import datetime, timedelta
import os

from app.database import get_db
from app.models import File as FileModel, User, Share

router = APIRouter(prefix="/files", tags=["Files"])

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

SECRET_KEY = os.getenv("SECRET_KEY", "cloudvault-super-secret-key-change-in-prod")
ALGORITHM  = "HS256"


# ── AUTH HELPER ───────────────────────────────────────────────────────────────
def get_user_from_token(token: str, db: Session):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload.get("sub"))
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user = db.query(User).filter(User.id == user_id).first()

    # FIX: User row deleted from DB — reject their token
    if not user:
        raise HTTPException(status_code=401, detail="Account no longer exists")

    # FIX: User deactivated/deleted — block every API call instantly
    if not user.is_active:
        raise HTTPException(status_code=403, detail="This account has been deleted. Please contact admin.")

    return user


# ── UTILS ─────────────────────────────────────────────────────────────────────
def human_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 ** 2:
        return f"{size_bytes/1024:.1f} KB"
    elif size_bytes < 1024 ** 3:
        return f"{size_bytes/1024**2:.1f} MB"
    return f"{size_bytes/1024**3:.1f} GB"


def make_owner_folder(user: User) -> str:
    name      = (user.name or "user").strip()
    safe_name = ''.join(c if c.isalnum() or c in ('-', '_') else '_' for c in name)
    safe_name = safe_name.strip('_') or 'user'
    return f"{safe_name}_{user.id}"


# ── LIST FILES ────────────────────────────────────────────────────────────────
@router.get("/")
def get_files(
    filter: str     = Query("all", description="all | starred | shared | trash | recent"),
    token:  str     = Query(...),
    db:     Session = Depends(get_db),
):
    user  = get_user_from_token(token, db)
    query = db.query(FileModel, User.name.label("owner_name")).join(User, FileModel.owner_id == User.id)

    if user.role != "admin":
        query = query.filter(FileModel.owner_id == user.id)

    if filter == "starred":
        query = query.filter(FileModel.starred == True,  FileModel.trash == False)
    elif filter == "shared":
        query = query.filter(FileModel.shared  == True,  FileModel.trash == False)
    elif filter == "trash":
        query = query.filter(FileModel.trash   == True)
    elif filter == "recent":
        query = query.filter(FileModel.trash   == False).order_by(FileModel.id.desc()).limit(20)
    else:
        query = query.filter(FileModel.trash   == False)

    return [
        {
            "id":         f.id,
            "name":       f.name,
            "size":       f.size,
            "file_type":  f.file_type,
            "starred":    f.starred,
            "shared":     f.shared,
            "trash":      f.trash,
            "owner_name": owner_name,
            "created_at": str(f.created_at)[:10] if f.created_at else "",
        }
        for f, owner_name in query.all()
    ]


# ── UPLOAD ────────────────────────────────────────────────────────────────────
@router.post("/upload")
def upload_file(
    file:     UploadFile       = File(...),
    token:    str              = Query(...),
    owner_id: Optional[int]   = Query(None, description="Optional owner id (admins only)"),
    db:       Session          = Depends(get_db),
):
    user            = get_user_from_token(token, db)
    target_owner_id = user.id
    target_user     = user

    if owner_id is not None:
        if user.role != "admin":
            raise HTTPException(status_code=403, detail="Only admins may set owner_id")
        target_user = db.query(User).filter(User.id == owner_id).first()
        if not target_user:
            raise HTTPException(status_code=404, detail="Target owner not found")
        target_owner_id = owner_id

    user_dir  = os.path.join(UPLOAD_DIR, make_owner_folder(target_user))
    os.makedirs(user_dir, exist_ok=True)
    file_path = os.path.join(user_dir, file.filename)

    with open(file_path, "wb") as buf:
        content    = file.file.read()
        buf.write(content)
        size_bytes = len(content)

    new_file = FileModel(
        name      = file.filename,
        path      = file_path,
        size      = human_size(size_bytes),
        file_type = file.content_type or "application/octet-stream",
        owner_id  = target_owner_id,
    )
    db.add(new_file)
    db.commit()
    db.refresh(new_file)

    return {"message": "Uploaded successfully", "file_id": new_file.id, "name": new_file.name, "owner_id": target_owner_id}


# ── STAR / UNSTAR ─────────────────────────────────────────────────────────────
@router.patch("/{file_id}/star")
def toggle_star(file_id: int, token: str = Query(...), db: Session = Depends(get_db)):
    user  = get_user_from_token(token, db)
    query = db.query(FileModel).filter(FileModel.id == file_id)
    if user.role != "admin":
        query = query.filter(FileModel.owner_id == user.id)
    f = query.first()
    if not f:
        raise HTTPException(status_code=404, detail="File not found")
    f.starred = not f.starred
    db.commit()
    return {"starred": f.starred}


# ── TRASH / RESTORE ───────────────────────────────────────────────────────────
@router.patch("/{file_id}/trash")
def trash_file(file_id: int, token: str = Query(...), db: Session = Depends(get_db)):
    user  = get_user_from_token(token, db)
    query = db.query(FileModel).filter(FileModel.id == file_id)
    if user.role != "admin":
        query = query.filter(FileModel.owner_id == user.id)
    f = query.first()
    if not f:
        raise HTTPException(status_code=404, detail="File not found")
    f.trash   = True
    f.starred = False
    db.commit()
    return {"message": "Moved to trash"}


@router.patch("/{file_id}/restore")
def restore_file(file_id: int, token: str = Query(...), db: Session = Depends(get_db)):
    user  = get_user_from_token(token, db)
    query = db.query(FileModel).filter(FileModel.id == file_id)
    if user.role != "admin":
        query = query.filter(FileModel.owner_id == user.id)
    f = query.first()
    if not f:
        raise HTTPException(status_code=404, detail="File not found")
    f.trash = False
    db.commit()
    return {"message": "Restored"}


# ── PERMANENT DELETE ──────────────────────────────────────────────────────────
@router.delete("/{file_id}")
def delete_file(file_id: int, token: str = Query(...), db: Session = Depends(get_db)):
    user  = get_user_from_token(token, db)
    query = db.query(FileModel).filter(FileModel.id == file_id)
    if user.role != "admin":
        query = query.filter(FileModel.owner_id == user.id)
    f = query.first()
    if not f:
        raise HTTPException(status_code=404, detail="File not found")
    if os.path.exists(f.path):
        os.remove(f.path)
    db.delete(f)
    db.commit()
    return {"message": "Deleted permanently"}


# ── DOWNLOAD ──────────────────────────────────────────────────────────────────
@router.get("/{file_id}/download")
def download_file(file_id: int, token: str = Query(...), db: Session = Depends(get_db)):
    user = get_user_from_token(token, db)
    f    = db.query(FileModel).filter(FileModel.id == file_id).first()
    if not f:
        raise HTTPException(status_code=404, detail="File not found")
    if user.role != "admin" and f.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Not allowed to download this file")
    if not os.path.exists(f.path):
        raise HTTPException(status_code=404, detail="File missing on disk")
    return FileResponse(f.path, filename=f.name)


# ── ADMIN: ALL FILES ──────────────────────────────────────────────────────────
@router.get("/admin/all")
def admin_all_files(token: str = Query(...), db: Session = Depends(get_db)):
    user = get_user_from_token(token, db)
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admins only")
    files = db.query(FileModel, User.name.label("owner_name")).join(User, FileModel.owner_id == User.id).all()
    return [
        {
            "id": f.id, "name": f.name, "size": f.size, "owner_id": f.owner_id,
            "owner_name": owner_name, "shared": f.shared, "starred": f.starred,
            "trash": f.trash, "created_at": str(f.created_at)[:10],
        }
        for f, owner_name in files
    ]


# ── SHARE: create public link ─────────────────────────────────────────────────
@router.post("/{file_id}/share")
def create_share(file_id: int, token: str = Query(...), expires_hours: int = Query(0), db: Session = Depends(get_db)):
    user = get_user_from_token(token, db)
    f    = db.query(FileModel).filter(FileModel.id == file_id).first()
    if not f:
        raise HTTPException(status_code=404, detail="File not found")
    if user.role != "admin" and f.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Not allowed to share this file")

    share_token = uuid.uuid4().hex
    expires_at  = None
    if expires_hours and expires_hours > 0:
        expires_at = datetime.utcnow() + timedelta(hours=expires_hours)

    from app.models import Share
    f.shared = True
    share    = Share(file_id=f.id, token=share_token, expires_at=expires_at)
    db.add(share)
    db.commit()
    db.refresh(share)

    app_url = os.getenv("APP_URL", "http://localhost:8000")
    return {"token": share_token, "url": f"{app_url}/files/shared/{share_token}", "expires_at": str(expires_at) if expires_at else None}


# ── DOWNLOAD shared file (no auth needed) ────────────────────────────────────
@router.get("/shared/{share_token}")
def download_shared(share_token: str, db: Session = Depends(get_db)):
    from app.models import Share
    share = db.query(Share).filter(Share.token == share_token).first()
    if not share:
        raise HTTPException(status_code=404, detail="Share link not found")
    if share.expires_at and datetime.utcnow() > share.expires_at:
        raise HTTPException(status_code=404, detail="Share link expired")
    f = db.query(FileModel).filter(FileModel.id == share.file_id).first()
    if not f:
        raise HTTPException(status_code=404, detail="File not found")
    if not os.path.exists(f.path):
        raise HTTPException(status_code=404, detail="File missing on disk")
    return FileResponse(f.path, filename=f.name)
