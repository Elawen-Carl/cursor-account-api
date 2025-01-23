from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import Column, String, DateTime, Text, text
from datetime import datetime
import os
from dotenv import load_dotenv
import logging
from contextlib import asynccontextmanager

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

def get_database_url():
    """获取数据库URL并验证配置"""
    required_vars = {
        'POSTGRES_USER': os.getenv('POSTGRES_USER'),
        'POSTGRES_PASSWORD': os.getenv('POSTGRES_PASSWORD'),
        'POSTGRES_HOST': os.getenv('POSTGRES_HOST'),
        'POSTGRES_DATABASE': os.getenv('POSTGRES_DATABASE')
    }
    
    # 检查所有必需的环境变量
    missing_vars = [key for key, value in required_vars.items() if not value]
    if missing_vars:
        error_msg = f"Missing required environment variables: {', '.join(missing_vars)}"
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    # 构建数据库URL
    url = f"postgresql+asyncpg://{required_vars['POSTGRES_USER']}:{required_vars['POSTGRES_PASSWORD']}@{required_vars['POSTGRES_HOST']}/{required_vars['POSTGRES_DATABASE']}"
    logger.info(f"Database configuration loaded successfully")
    return url

try:
    # 获取数据库URL
    POSTGRES_URL = get_database_url()
    
    # 创建异步引擎，优化连接池配置
    engine = create_async_engine(
        POSTGRES_URL,
        echo=False,
        connect_args={
            "ssl": True,
            "server_settings": {"client_encoding": "utf8"},
            "command_timeout": 10  # 添加命令超时
        },
        pool_pre_ping=True,
        pool_size=5,  # 减小连接池大小
        max_overflow=10,
        pool_timeout=30,  # 添加池超时
        pool_recycle=1800  # 30分钟后回收连接
    )
    
    # 使用 async_sessionmaker 替代 sessionmaker
    async_session = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    
    logger.info("Database engine and session configured successfully")
    
except Exception as e:
    logger.error(f"Failed to initialize database: {str(e)}")
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
async def get_session() -> AsyncSession:
    """创建数据库会话的异步上下文管理器"""
    session = async_session()
    try:
        # 确保连接有效
        await session.execute(text("SELECT 1"))
        yield session
    except Exception as e:
        logger.error(f"Database session error: {str(e)}")
        await session.rollback()
        raise
    finally:
        await session.close()

# 初始化数据库
async def init_db():
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {str(e)}")
        raise 