"""
Folder management routes
  POST   /folders/             – create a folder
  GET    /folders/             – list folders (root or inside a parent)
  GET    /folders/{id}         – get single folder info
  PATCH  /folders/{id}/rename  – rename
  PATCH  /folders/{id}/star    – toggle star
  PATCH  /folders/{id}/move    – move to another parent (or root)
  PATCH  /folders/{id}/trash   – move to trash
  PATCH  /folders/{id}/restore – restore from trash
  DELETE /folders/{id}         – permanent delete (also deletes all files inside)
  GET    /folders/trash        – list trashed folders
"""
import os
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from jose import jwt

from app.database import get_db
from app.models import Folder, File as FileModel, User

router = APIRouter(prefix="/folders", tags=["Folders"])

SECRET_KEY = os.getenv("SECRET_KEY", "cloudvault-super-secret-key-change-in-prod")
ALGORITHM  = "HS256"

ALLOWED_COLORS = {"yellow", "blue", "green", "red", "purple", "pink", "gray"}


# ── Auth helper ───────────────────────────────────────────────────────────────
def get_user_from_token(token: str, db: Session) -> User:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload.get("sub"))
    except Exception:
        raise HTTPException(401, "Invalid or expired token")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(401, "Account no longer exists")
    if not user.is_active:
        raise HTTPException(403, "This account has been deleted.")
    return user


def sanitize_name(name: str) -> str:
    """Strip dangerous characters from a folder name."""
    name = name.strip()
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', name)
    return name[:120] or "Untitled Folder"


def folder_dict(f: Folder, file_count: int = 0, subfolder_count: int = 0) -> dict:
    return {
        "id":              f.id,
        "name":            f.name,
        "owner_id":        f.owner_id,
        "parent_id":       f.parent_id,
        "color":           f.color,
        "starred":         f.starred,
        "trash":           f.trash,
        "file_count":      file_count,
        "subfolder_count": subfolder_count,
        "created_at":      str(f.created_at)[:10] if f.created_at else "",
    }


# ── Schemas ───────────────────────────────────────────────────────────────────
class CreateFolderSchema(BaseModel):
    name:      str
    parent_id: Optional[int] = None
    color:     str = "yellow"

class RenameFolderSchema(BaseModel):
    name: str

class MoveFolderSchema(BaseModel):
    parent_id: Optional[int] = None   # None = move to root

class ColorFolderSchema(BaseModel):
    color: str


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/", status_code=201)
def create_folder(
    data:  CreateFolderSchema,
    token: str     = Query(...),
    db:    Session = Depends(get_db),
):
    user = get_user_from_token(token, db)
    name = sanitize_name(data.name)
    color = data.color if data.color in ALLOWED_COLORS else "yellow"

    # Validate parent exists and belongs to this user
    if data.parent_id is not None:
        parent = db.query(Folder).filter(
            Folder.id == data.parent_id,
            Folder.owner_id == user.id,
            Folder.trash == False,
        ).first()
        if not parent:
            raise HTTPException(404, "Parent folder not found")

    # Prevent duplicate names inside the same parent
    exists = db.query(Folder).filter(
        Folder.owner_id == user.id,
        Folder.parent_id == data.parent_id,
        Folder.name == name,
        Folder.trash == False,
    ).first()
    if exists:
        raise HTTPException(400, f"A folder named '{name}' already exists here")

    folder = Folder(
        name=name, owner_id=user.id,
        parent_id=data.parent_id, color=color,
    )
    db.add(folder)
    db.commit()
    db.refresh(folder)
    return folder_dict(folder)


@router.get("/trash")
def get_trashed_folders(token: str = Query(...), db: Session = Depends(get_db)):
    user = get_user_from_token(token, db)
    folders = db.query(Folder).filter(
        Folder.owner_id == user.id,
        Folder.trash == True,
    ).order_by(Folder.name).all()
    return [folder_dict(f) for f in folders]


@router.get("/")
def list_folders(
    parent_id: Optional[int] = Query(None, description="None = root level"),
    filter:    str           = Query("all", description="all | starred | trash"),
    flat:      bool          = Query(False, description="Return all folders (for move picker)"),
    token:     str           = Query(...),
    db:        Session       = Depends(get_db),
):
    user = get_user_from_token(token, db)
    q = db.query(Folder).filter(Folder.owner_id == user.id)

    if filter == "trash":
        q = q.filter(Folder.trash == True)
    elif filter == "starred":
        q = q.filter(Folder.starred == True, Folder.trash == False)
    elif flat:
        q = q.filter(Folder.trash == False)
    else:
        q = q.filter(Folder.trash == False)
        if parent_id is None:
            q = q.filter(Folder.parent_id.is_(None))
        else:
            q = q.filter(Folder.parent_id == parent_id)

    folders = q.order_by(Folder.name).all()

    result = []
    for f in folders:
        fc  = db.query(FileModel).filter(FileModel.folder_id == f.id, FileModel.trash == False).count()
        sfc = db.query(Folder).filter(Folder.parent_id == f.id, Folder.trash == False).count()
        result.append(folder_dict(f, fc, sfc))
    return result


@router.get("/{folder_id}")
def get_folder(folder_id: int, token: str = Query(...), db: Session = Depends(get_db)):
    user = get_user_from_token(token, db)
    f = db.query(Folder).filter(Folder.id == folder_id, Folder.owner_id == user.id).first()
    if not f:
        raise HTTPException(404, "Folder not found")
    fc  = db.query(FileModel).filter(FileModel.folder_id == f.id, FileModel.trash == False).count()
    sfc = db.query(Folder).filter(Folder.parent_id == f.id, Folder.trash == False).count()
    return folder_dict(f, fc, sfc)


@router.patch("/{folder_id}/rename")
def rename_folder(folder_id: int, data: RenameFolderSchema, token: str = Query(...), db: Session = Depends(get_db)):
    user = get_user_from_token(token, db)
    f = db.query(Folder).filter(Folder.id == folder_id, Folder.owner_id == user.id).first()
    if not f:
        raise HTTPException(404, "Folder not found")
    name = sanitize_name(data.name)
    # Check duplicate in same parent
    dup = db.query(Folder).filter(
        Folder.owner_id == user.id, Folder.parent_id == f.parent_id,
        Folder.name == name, Folder.id != folder_id, Folder.trash == False,
    ).first()
    if dup:
        raise HTTPException(400, f"A folder named '{name}' already exists here")
    f.name = name
    db.commit()
    return {"message": "Renamed", "name": f.name}


@router.patch("/{folder_id}/star")
def toggle_star(folder_id: int, token: str = Query(...), db: Session = Depends(get_db)):
    user = get_user_from_token(token, db)
    f = db.query(Folder).filter(Folder.id == folder_id, Folder.owner_id == user.id).first()
    if not f:
        raise HTTPException(404, "Folder not found")
    f.starred = not f.starred
    db.commit()
    return {"starred": f.starred}


@router.patch("/{folder_id}/color")
def set_color(folder_id: int, data: ColorFolderSchema, token: str = Query(...), db: Session = Depends(get_db)):
    user = get_user_from_token(token, db)
    f = db.query(Folder).filter(Folder.id == folder_id, Folder.owner_id == user.id).first()
    if not f:
        raise HTTPException(404, "Folder not found")
    f.color = data.color if data.color in ALLOWED_COLORS else "yellow"
    db.commit()
    return {"color": f.color}


@router.patch("/{folder_id}/move")
def move_folder(folder_id: int, data: MoveFolderSchema, token: str = Query(...), db: Session = Depends(get_db)):
    user = get_user_from_token(token, db)
    f = db.query(Folder).filter(Folder.id == folder_id, Folder.owner_id == user.id).first()
    if not f:
        raise HTTPException(404, "Folder not found")
    if data.parent_id == folder_id:
        raise HTTPException(400, "Cannot move folder into itself")
    if data.parent_id is not None:
        parent = db.query(Folder).filter(
            Folder.id == data.parent_id, Folder.owner_id == user.id, Folder.trash == False,
        ).first()
        if not parent:
            raise HTTPException(404, "Target parent not found")
    f.parent_id = data.parent_id
    db.commit()
    return {"message": "Moved"}


@router.patch("/{folder_id}/trash")
def trash_folder(folder_id: int, token: str = Query(...), db: Session = Depends(get_db)):
    user = get_user_from_token(token, db)
    f = db.query(Folder).filter(Folder.id == folder_id, Folder.owner_id == user.id).first()
    if not f:
        raise HTTPException(404, "Folder not found")
    f.trash = True; f.starred = False
    db.commit()
    return {"message": "Folder moved to trash"}


@router.patch("/{folder_id}/restore")
def restore_folder(folder_id: int, token: str = Query(...), db: Session = Depends(get_db)):
    user = get_user_from_token(token, db)
    f = db.query(Folder).filter(Folder.id == folder_id, Folder.owner_id == user.id).first()
    if not f:
        raise HTTPException(404, "Folder not found")
    f.trash = False
    db.commit()
    return {"message": "Restored"}


@router.delete("/{folder_id}")
def delete_folder(folder_id: int, token: str = Query(...), db: Session = Depends(get_db)):
    """Permanently delete folder + all files inside it (recursively)."""
    user = get_user_from_token(token, db)
    f = db.query(Folder).filter(Folder.id == folder_id, Folder.owner_id == user.id).first()
    if not f:
        raise HTTPException(404, "Folder not found")

    def _delete_recursive(fid: int):
        # Delete files inside this folder
        files = db.query(FileModel).filter(FileModel.folder_id == fid).all()
        for file in files:
            if os.path.exists(file.path):
                os.remove(file.path)
            db.delete(file)
        # Delete sub-folders recursively
        subs = db.query(Folder).filter(Folder.parent_id == fid).all()
        for sub in subs:
            _delete_recursive(sub.id)
            db.delete(sub)

    _delete_recursive(f.id)
    db.delete(f)
    db.commit()
    return {"message": "Folder and all contents deleted permanently"}
