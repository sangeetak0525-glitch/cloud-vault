"""
One-time migration: add folder columns to existing SQLite DB.
Run from repo root: python -m app.fix_db
"""
from sqlalchemy import inspect, text

from app.database import engine


def column_exists(inspector, table: str, column: str) -> bool:
    return column in {c["name"] for c in inspector.get_columns(table)}


def migrate():
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    with engine.begin() as conn:
        if "folders" not in tables:
            conn.execute(text("""
                CREATE TABLE folders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name VARCHAR(120) NOT NULL,
                    owner_id INTEGER NOT NULL,
                    parent_id INTEGER REFERENCES folders(id),
                    color VARCHAR(20) DEFAULT 'yellow',
                    starred BOOLEAN DEFAULT 0,
                    trash BOOLEAN DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """))
            print("Created folders table")
        else:
            for col, ddl in [
                ("parent_id", "ALTER TABLE folders ADD COLUMN parent_id INTEGER"),
                ("color", "ALTER TABLE folders ADD COLUMN color VARCHAR(20) DEFAULT 'yellow'"),
                ("starred", "ALTER TABLE folders ADD COLUMN starred BOOLEAN DEFAULT 0"),
                ("trash", "ALTER TABLE folders ADD COLUMN trash BOOLEAN DEFAULT 0"),
            ]:
                if not column_exists(inspector, "folders", col):
                    conn.execute(text(ddl))
                    print(f"Added folders.{col}")

        if "files" in tables and not column_exists(inspector, "files", "folder_id"):
            conn.execute(text("ALTER TABLE files ADD COLUMN folder_id INTEGER REFERENCES folders(id)"))
            print("Added files.folder_id")

    print("Migration complete.")


if __name__ == "__main__":
    migrate()
