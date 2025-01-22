from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy import Column, String, DateTime, Text
from datetime import datetime
import os
from dotenv import load_dotenv
import logging
from contextlib import asynccontextmanager

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 只在非生产环境加载 .env 文件
if not os.getenv('VERCEL'):
    load_dotenv()

# 从环境变量获取数据库配置
DB_USER = os.getenv('POSTGRES_USER')
DB_PASSWORD = os.getenv('POSTGRES_PASSWORD')
DB_HOST = os.getenv('POSTGRES_HOST')
DB_NAME = os.getenv('POSTGRES_DATABASE')

# 检查是否存在 POSTGRES_URL（Vercel 集成数据库会提供这个）
POSTGRES_URL = os.getenv('POSTGRES_URL')

if POSTGRES_URL:
    logger.info("Using direct POSTGRES_URL from environment")
else:
    # 检查必要的环境变量
    missing_vars = []
    if not DB_USER:
        missing_vars.append('POSTGRES_USER')
    if not DB_PASSWORD:
        missing_vars.append('POSTGRES_PASSWORD')
    if not DB_HOST:
        missing_vars.append('POSTGRES_HOST')
    if not DB_NAME:
        missing_vars.append('POSTGRES_DATABASE')

    if missing_vars:
        error_msg = f"Missing required environment variables: {', '.join(missing_vars)}"
        logger.error(error_msg)
        raise ValueError(error_msg)

    # 构建数据库URL
    POSTGRES_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"

logger.info(f"Connecting to database...")

# 为 Vercel 环境优化的数据库配置
IS_VERCEL = os.getenv('VERCEL') == '1'

try:
    # 创建异步引擎
    engine = create_async_engine(
        POSTGRES_URL,
        echo=False,
        # Vercel 环境使用较小的连接池
        pool_size=1 if IS_VERCEL else 20,
        max_overflow=0,
        pool_timeout=30,
        # Vercel 环境下更快地回收连接
        pool_recycle=1800 if not IS_VERCEL else 300,
        # Vercel 环境下更短的命令超时
        connect_args={
            "ssl": True,
            "server_settings": {"client_encoding": "utf8"},
            "command_timeout": 5 if IS_VERCEL else 10
        }
    )
    
    async_session_factory = sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False
    )
    
except Exception as e:
    logger.error(f"Failed to create database engine: {str(e)}")
    raise

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

@asynccontextmanager
async def get_db():
    """异步上下文管理器获取数据库会话"""
    session = async_session_factory()
    try:
        await session.execute("SELECT 1")  # 验证连接
        yield session
    except Exception as e:
        logger.error(f"Database connection error: {str(e)}")
        await session.rollback()
        raise
    finally:
        await session.close()

# 创建数据库会话
async def get_session() -> AsyncSession:
    """获取数据库会话的依赖函数"""
    async with get_db() as session:
        try:
            yield session
        except Exception as e:
            logger.error(f"Session error: {str(e)}")
            await session.rollback()
            raise

# 初始化数据库
async def init_db():
    """初始化数据库表结构"""
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {str(e)}")
        raise 