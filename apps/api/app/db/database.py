"""
数据库引擎模块
创建 SQLAlchemy 连接引擎，供所有数据库操作使用。
"""
from sqlalchemy import create_engine
from app.core.config import settings

# pool_pre_ping=True: 每次从连接池取连接前先 ping 一下，防止使用已断开的连接
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)