from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from jose import jwt
from datetime import datetime, timedelta
import os
import base64
import hashlib
import hmac
try:
    import bcrypt
except Exception:
    bcrypt = None

from app.database import get_db
from app.models import User

router = APIRouter(prefix="/auth", tags=["Auth"])

# ── SECURITY CONFIG ───────────────────────────────────────────────────────────
SECRET_KEY         = os.getenv("SECRET_KEY", "cloudvault-super-secret-key-change-in-prod")
ALGORITHM          = "HS256"
TOKEN_EXPIRE_HOURS = 24

# ── HELPERS ───────────────────────────────────────────────────────────────────
def hash_password(plain: str) -> str:
    salt   = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", plain.encode("utf-8"), salt, 100_000)
    return (
        "pbkdf2_sha256$100000$"
        + base64.b64encode(salt).decode("ascii")
        + "$"
        + base64.b64encode(digest).decode("ascii")
    )

def verify_password(plain: str, hashed: str) -> bool:
    if hashed.startswith("pbkdf2_sha256$"):
        try:
            algo, rounds, salt_b64, digest_b64 = hashed.split("$", 3)
            if algo != "pbkdf2_sha256":
                return False
            salt     = base64.b64decode(salt_b64.encode("ascii"))
            expected = base64.b64decode(digest_b64.encode("ascii"))
        except Exception:
            return False
        current = hashlib.pbkdf2_hmac("sha256", plain.encode("utf-8"), salt, int(rounds))
        return hmac.compare_digest(current, expected)

    if hashed.startswith("$2") and bcrypt is not None:
        try:
            return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
        except Exception:
            return False

    return plain == hashed

def create_token(data: dict) -> str:
    payload       = data.copy()
    payload["exp"] = datetime.utcnow() + timedelta(hours=TOKEN_EXPIRE_HOURS)
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


# ── SCHEMAS ───────────────────────────────────────────────────────────────────
class RegisterSchema(BaseModel):
    name:         str
    email:        EmailStr
    password:     str
    role:         str = "user"
    admin_secret: str = ""

class LoginSchema(BaseModel):
    email:    EmailStr
    password: str


# ── ROUTES ────────────────────────────────────────────────────────────────────
ADMIN_SECRET = os.getenv("ADMIN_SECRET", "CLOUDVAULT_ADMIN_2024")

@router.post("/register", status_code=201)
def register(data: RegisterSchema, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    if data.role == "admin":
        existing_admin = db.query(User).filter(User.role == "admin").first()
        if existing_admin and data.admin_secret != ADMIN_SECRET:
            raise HTTPException(status_code=403, detail="Invalid admin secret key")

    new_user = User(
        name     = data.name,
        email    = data.email,
        password = hash_password(data.password),
        role     = data.role,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {
        "message": "Account created successfully. Please sign in.",
        "user": {"id": new_user.id, "name": new_user.name, "email": new_user.email},
    }


@router.post("/login")
def login(data: LoginSchema, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()

    # Wrong email or wrong password
    if not user or not verify_password(data.password, user.password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # FIX: Account was deleted/deactivated — block login completely
    if not user.is_active:
        raise HTTPException(status_code=403, detail="This account has been deleted. Please contact admin.")

    token = create_token({"sub": str(user.id), "role": user.role})

    return {
        "message": "Login successful",
        "token":   token,
        "user": {
            "id":    user.id,
            "name":  user.name,
            "email": user.email,
            "role":  user.role,
        },
    }


@router.get("/me")
def get_me(token: str, db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload.get("sub"))
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user = db.query(User).filter(User.id == user_id).first()

    # FIX: User row was deleted from DB — token is now invalid
    if not user:
        raise HTTPException(status_code=401, detail="Account no longer exists")

    # FIX: User was deactivated — block even with a valid token
    if not user.is_active:
        raise HTTPException(status_code=403, detail="This account has been deleted. Please contact admin.")

    return {"id": user.id, "name": user.name, "email": user.email, "role": user.role}
