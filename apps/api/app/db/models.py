"""
SQLAlchemy ORM 模型
所有数据库表都在这里定义，替代裸 SQL 建表。
概念：
  DeclarativeBase — SQLAlchemy 2.0 的基类，所有 Model 继承它
  relationship() — 定义表之间的关系，可以通过 user.files 直接访问关联数据
  cascade="all, delete-orphan" — 删用户时自动删他的文件和任务
  UUID(as_uuid=True) — PostgreSQL 原生 UUID 类型
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import (
  Column, String, Text, BigInteger, Integer, Numeric,
  Boolean, DateTime, ForeignKey, Index,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
  """ 所有ORM模型的基类 """
  pass

class User(Base):
  __tablename__ = "users"
  __table_args__ = {"schema": "public"}

  id= Column(String, primary_key=True)  # Clerk userId
  email = Column(String, nullable=True)
  created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

  # 关系
  files = relationship("File", back_populates="user", cascade="all, delete-orphan")
  runs = relationship("Run", back_populates="user", cascade="all, delete-orphan")

class File(Base):
  __tablename__ = "files"
  __table_args__ = (
    Index("idx_files_user_id", "user_id"),
    {"schema": "public"},
  )

  id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
  user_id = Column(String, ForeignKey("public.users.id", ondelete="CASCADE"), nullable=False)
  filename = Column(String, nullable=False)
  storage_key = Column(String, nullable=False)
  mime = Column(String, nullable=True)
  size = Column(BigInteger, nullable=True)
  status = Column(String, nullable=False, default="uploaded")
  created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

  # 关系
  user = relationship("User", back_populates="files")
  runs = relationship("Run", back_populates="file", cascade="all, delete-orphan")
  chunks = relationship("FileChunk", back_populates="file", cascade="all, delete-orphan")
  qa_messages = relationship("FileQaMessage", back_populates="file", cascade="all, delete-orphan")

class Run(Base):
  __tablename__ = "runs"
  __table_args__ = (
    Index("idx_runs_user_id", "user_id"),
    Index("idx_runs_file_id", "file_id"),
    {"schema": "public"},
  )

  id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
  user_id = Column(String, ForeignKey("public.users.id", ondelete="CASCADE"), nullable=False)
  file_id = Column(UUID(as_uuid=True), ForeignKey("public.files.id", ondelete="CASCADE"), nullable=False)
  template = Column(String, nullable=False)        # sop | checklist | summary
  status = Column(String, nullable=False, default="queued")  # queued | running | done | failed
  result_json = Column(JSONB, nullable=True)
  error = Column(Text, nullable=True)
  usage_tokens = Column(Integer, nullable=True)
  cost_usd = Column(Numeric(10, 4), nullable=True)
  created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
  share_id = Column(String, nullable=True)
  is_public = Column(Boolean, nullable=False, default=False)

  # 关系
  user = relationship("User", back_populates="runs")
  file = relationship("File", back_populates="runs")

class FileChunk(Base):
  __tablename__ = "file_chunks"
  __table_args__ = {"schema": "public"}

  id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
  file_id = Column(UUID(as_uuid=True), ForeignKey("public.files.id", ondelete="CASCADE"), nullable=False)
  user_id = Column(String, ForeignKey("public.users.id", ondelete="CASCADE"), nullable=False)
  chunk_index = Column(Integer, nullable=False)
  content = Column(Text, nullable=False)
  embedding = Column(Text, nullable=True)          # JSON 字符串存储向量
  meta = Column(JSONB, nullable=True)
  created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

  # 关系
  file = relationship("File", back_populates="chunks")

class FileQaMessage(Base):
  __tablename__ = "file_qa_messages"
  __table_args__ = {"schema": "public"}

  id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
  file_id = Column(UUID(as_uuid=True), ForeignKey("public.files.id", ondelete="CASCADE"), nullable=False)
  user_id = Column(String, ForeignKey("public.users.id", ondelete="CASCADE"), nullable=False)
  role = Column(String, nullable=False)            # user | assistant
  content = Column(Text, nullable=False)
  citations = Column(JSONB, nullable=True)
  created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

  # 关系
  file = relationship("File", back_populates="qa_messages")
