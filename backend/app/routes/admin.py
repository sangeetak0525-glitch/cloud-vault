from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from jose import jwt
import os

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


@router.delete("/users/{user_id}")
def delete_user(user_id: int, token: str = Query(...), db: Session = Depends(get_db)):
    admin = require_admin(token, db)
    if admin.id == user_id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()
    return {"message": "User deleted"}
