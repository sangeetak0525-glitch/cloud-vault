from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from jose import jwt
import os
import shutil

from app.database import get_db
from app.models import User, File as FileModel

router = APIRouter(prefix="/admin", tags=["Admin"])

SECRET_KEY = os.getenv("SECRET_KEY", "cloudvault-super-secret-key-change-in-prod")
ALGORITHM = "HS256"


def require_admin(token: str, db: Session):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload.get("sub"))
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = db.query(User).filter(User.id == user_id).first()
    if not user or user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


@router.get("/stats")
def get_stats(token: str = Query(...), db: Session = Depends(get_db)):
    require_admin(token, db)
    total_users = db.query(User).count()
    total_files = db.query(FileModel).count()
    active_files = db.query(FileModel).filter(FileModel.trash == False).count()
    trashed = db.query(FileModel).filter(FileModel.trash == True).count()
    return {
        "total_users": total_users,
        "total_files": total_files,
        "active_files": active_files,
        "trashed_files": trashed,
    }


@router.get("/users")
def get_all_users(token: str = Query(...), db: Session = Depends(get_db)):
    require_admin(token, db)
    users = db.query(User).all()
    return [
        {
            "id": u.id,
            "name": u.name,
            "email": u.email,
            "role": u.role,
            "is_active": u.is_active,
            "created_at": str(u.created_at)[:10] if u.created_at else "",
        }
        for u in users
    ]


# ── DEACTIVATE / REACTIVATE (toggle) ─────────────────────────────────────────
@router.patch("/users/{user_id}/toggle")
def toggle_user(user_id: int, token: str = Query(...), db: Session = Depends(get_db)):
    admin = require_admin(token, db)
    if admin.id == user_id:
        raise HTTPException(status_code=400, detail="Cannot deactivate yourself")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = not user.is_active
    db.commit()
    return {"is_active": user.is_active}


# ── DELETE USER — removes everything ─────────────────────────────────────────
@router.delete("/users/{user_id}")
def delete_user(user_id: int, token: str = Query(...), db: Session = Depends(get_db)):
    admin = require_admin(token, db)
    if admin.id == user_id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # STEP 1 — Deactivate immediately so their JWT stops working right now
    user.is_active = False
    db.commit()

    # STEP 2 — Delete every file record from DB + the actual file from disk
    user_files = db.query(FileModel).filter(FileModel.owner_id == user_id).all()
    for f in user_files:
        if os.path.exists(f.path):
            try:
                os.remove(f.path)
            except Exception:
                pass
        db.delete(f)
    db.commit()

    # STEP 3 — Remove the user's upload folder completely
    safe_name = ''.join(
        c if c.isalnum() or c in ('-', '_') else '_'
        for c in (user.name or 'user').strip()
    )
    safe_name = safe_name.strip('_') or 'user'
    user_dir = os.path.join("uploads", f"{safe_name}_{user_id}")
    if os.path.isdir(user_dir):
        shutil.rmtree(user_dir, ignore_errors=True)

    # STEP 4 — Delete the user row from DB
    db.delete(user)
    db.commit()

    return {"message": f"User and all their data have been permanently deleted"}
