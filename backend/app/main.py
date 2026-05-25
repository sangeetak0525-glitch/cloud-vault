
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import os

from app.database import Base, engine, SessionLocal
from app.models import User

from app.routes.auth import router as auth_router, hash_password
from app.routes.files import router as files_router
from app.routes.folders import router as folders_router
from app.routes.admin import router as admin_router

# ─── CREATE TABLES ───────────────────────────────────────────────────────
Base.metadata.create_all(bind=engine)

# ─── DEFAULT ADMIN SEED ───────────────────────────────────────────────────
def create_default_admin():
    db = SessionLocal()
    try:
        default_email = os.getenv("DEFAULT_ADMIN_EMAIL", "admin@cloudvault.io").strip()
        default_password = os.getenv("DEFAULT_ADMIN_PASSWORD", "admin")
        default_name = os.getenv("DEFAULT_ADMIN_NAME", "Administrator").strip()

        if not default_email or not default_password:
            return

        # Ensure the known default admin account exists.
        admin_user = db.query(User).filter(User.email == default_email).first()
        if admin_user:
            return

        admin = User(
            name=default_name,
            email=default_email,
            password=hash_password(default_password),
            role="admin",
        )
        db.add(admin)
        db.commit()
        print(f"Created default admin account: {default_email}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

create_default_admin()

# Repo layout: backend/app/main.py → parents[2] = CloudVault
REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_INDEX = REPO_ROOT / "frontend" / "index.html"

# ─── APP INIT ────────────────────────────────────────────────────────────
app = FastAPI(title="CloudVault API", version="2.0.0")

# ─── CORS ────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # ⚠️ tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── API ROUTES ──────────────────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(files_router)
app.include_router(folders_router)
app.include_router(admin_router)

# ─── UPLOAD STORAGE ───────────────────────────────────────────────────────
os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# ─── FRONTEND (same process as API; open http://localhost:8000/) ────────────
@app.get("/", include_in_schema=False)
def serve_frontend():
    if not FRONTEND_INDEX.is_file():
        return {
            "error": "frontend/index.html not found",
            "expected": str(FRONTEND_INDEX),
        }
    return FileResponse(FRONTEND_INDEX)