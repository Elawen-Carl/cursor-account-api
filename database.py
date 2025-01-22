from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy import Column, String, DateTime, Text
from datetime import datetime
import os
from dotenv import load_dotenv
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

# 从环境变量获取数据库配置
DB_USER = os.getenv('POSTGRES_USER')
DB_PASSWORD = os.getenv('POSTGRES_PASSWORD')
DB_HOST = os.getenv('POSTGRES_HOST')
DB_NAME = os.getenv('POSTGRES_DATABASE')

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

logger.info(f"Connecting to database at: {DB_HOST}")

try:
    # 创建异步引擎
    engine = create_async_engine(
        POSTGRES_URL,
        echo=False,
        connect_args={
            "ssl": True,
            "server_settings": {"client_encoding": "utf8"}
        },
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10
    )
    
    async_session = sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False
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

# 创建数据库会话
async def get_session() -> AsyncSession:
    try:
        async with async_session() as session:
            # 测试数据库连接
            await session.execute("SELECT 1")
            yield session
    except Exception as e:
        logger.error(f"Database session error: {str(e)}")
        raise
    finally:
        await session.close()

# 初始化数据库
async def init_db():
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {str(e)}")
        raise 