# from sqlalchemy import create_engine
# from sqlalchemy.orm import sessionmaker, declarative_base

# DB_USER = "root"
# DB_PASSWORD = "mysql"
# DB_HOST = "localhost"
# DB_NAME = "cloudvault"

# DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"

# engine = create_engine(DATABASE_URL)
# SessionLocal = sessionmaker(bind=engine)

# Base = declarative_base()
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import SQLAlchemyError
import os
from pathlib import Path

# ─── DATABASE CONFIG ──────────────────────────────────────────────────────────
# Use absolute SQLite path so DB location is stable regardless of cwd.
REPO_ROOT = Path(__file__).resolve().parents[2]
SQLITE_DB_PATH = REPO_ROOT / "cloudvault.db"
SQLITE_URL = f"sqlite:///{SQLITE_DB_PATH.as_posix()}"

# Priority 1: explicit full URL (recommended for production)
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

# Priority 2: choose engine from DB_ENGINE (default: sqlite for local dev)
if not DATABASE_URL:
    DB_ENGINE = os.getenv("DB_ENGINE", "sqlite").lower()
    if DB_ENGINE == "mysql":
        DB_USER = os.getenv("DB_USER", "root")
        DB_PASSWORD = os.getenv("DB_PASSWORD", "")
        DB_HOST = os.getenv("DB_HOST", "localhost")
        DB_PORT = os.getenv("DB_PORT", "3306")
        DB_NAME = os.getenv("DB_NAME", "cloudvault")
        DATABASE_URL = (
            f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
        )
    else:
        DATABASE_URL = SQLITE_URL

engine_kwargs = {
    "echo": False,
    "pool_pre_ping": True,   # recovers stale/disconnected DB sockets
    "pool_recycle": 1800,    # avoid long-idle MySQL disconnect issues
}
if DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **engine_kwargs)

# Permanent safety net: if MySQL is unreachable, auto-fallback to local SQLite.
if DATABASE_URL.startswith("mysql"):
    try:
        with engine.connect():
            pass
    except SQLAlchemyError:
        DATABASE_URL = SQLITE_URL
        engine = create_engine(
            DATABASE_URL,
            echo=False,
            connect_args={"check_same_thread": False},
        )

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()