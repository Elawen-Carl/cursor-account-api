from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy import Column, String, DateTime, Text
from datetime import datetime, UTC
import os
from dotenv import load_dotenv

load_dotenv()

# 从环境变量获取数据库配置
DB_USER = os.getenv('POSTGRES_USER')
DB_PASSWORD = os.getenv('POSTGRES_PASSWORD')
DB_HOST = os.getenv('POSTGRES_HOST')
DB_NAME = os.getenv('POSTGRES_DATABASE')

# 构建数据库URL
POSTGRES_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"

print(f"Using database URL: {POSTGRES_URL}")  # 调试用

# 创建异步引擎 - 关闭echo
engine = create_async_engine(
    POSTGRES_URL,
    echo=False,
    connect_args={
        "ssl": True,
        "server_settings": {"client_encoding": "utf8"}
    },
    pool_pre_ping=True
)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# 基础模型类
class Base(DeclarativeBase):
    pass

# 账号模型
class AccountModel(Base):
    __tablename__ = "accounts"
    
    email = Column(String, primary_key=True)
    password = Column(String, nullable=True)
    token = Column(String, nullable=False)
    usage_limit = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now())
    updated_at = Column(DateTime, default=lambda: datetime.now(), onupdate=lambda: datetime.now())

# 创建数据库会话
async def get_session() -> AsyncSession:
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()

# 初始化数据库
async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all) 