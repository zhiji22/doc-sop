"""
数据库引擎与会话管理
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# pool_pre_ping=True: 每次从连接池取连接前先 ping 一下，防止使用已断开的连接
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)

# Session 工厂 — 后续所有数据库操作都通过 Session 来做
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db():
  """
  FastAPI依赖注入用的generator.
  每个请求获得一个独立的数据库session，请求结束后自动关闭
  用法：db = Depends(get_db)
  """
  db = SessionLocal()
  try:
    yield db

  finally:
    db.close()
