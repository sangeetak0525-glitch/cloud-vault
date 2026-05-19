# from sqlalchemy import Column, Integer, String, Boolean
# from .database import Base

# class User(Base):
#     __tablename__ = "users"

#     id = Column(Integer, primary_key=True)
#     email = Column(String(255), unique=True)
#     password = Column(String(255))
#     role = Column(String(50))


# class File(Base):
#     __tablename__ = "files"

#     id = Column(Integer, primary_key=True)
#     name = Column(String(255))
#     path = Column(String(255))
#     size = Column(String(50))
#     owner_id = Column(Integer)
#     starred = Column(Boolean, default=False)
#     shared = Column(Boolean, default=False)

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.sql import func
from .database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password = Column(String(255), nullable=False)   # bcrypt hash
    role = Column(String(50), default="user")        # "user" or "admin"
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class File(Base):
    __tablename__ = "files"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    path = Column(String(500), nullable=False)
    size = Column(String(50), default="0 KB")
    file_type = Column(String(100), default="application/octet-stream")
    owner_id = Column(Integer, nullable=False)
    starred = Column(Boolean, default=False)
    shared = Column(Boolean, default=False)
    trash = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Share(Base):
    __tablename__ = "shares"

    id = Column(Integer, primary_key=True, index=True)
    file_id = Column(Integer, ForeignKey("files.id"), nullable=False, index=True)
    token = Column(String(128), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())