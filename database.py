from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import Column, String, DateTime, Text, text
from datetime import datetime
import os
from dotenv import load_dotenv
import logging
import asyncio
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

def ensure_event_loop():
    """确保有可用的事件循环，如果没有则创建一个新的"""
    try:
        # 尝试获取当前事件循环
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        
        # 如果没有事件循环或事件循环已关闭，创建新的
        if loop is None or loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        return loop
    except Exception as e:
        logger.error(f"Error ensuring event loop: {str(e)}")
        # 如果出现任何错误，强制创建新的事件循环
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop

def create_engine_and_session():
    """创建数据库引擎和会话工厂"""
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
                "command_timeout": 10
            },
            pool_pre_ping=True,
            pool_size=1,  # Serverless环境建议使用较小的连接池
            max_overflow=0,
            pool_timeout=30,
            pool_recycle=1800,
            pool_use_lifo=True,  # 使用后进先出策略
            future=True  # 使用新的 future 特性
        )
        
        # 创建会话工厂
        session_maker = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
            future=True
        )
        
        return engine, session_maker
        
    except Exception as e:
        logger.error(f"Failed to initialize database: {str(e)}")
        raise

# 创建全局引擎和会话工厂
engine, async_session = create_engine_and_session()

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
    # 确保有可用的事件循环
    loop = ensure_event_loop()
    
    # 创建新的会话
    session = async_session()
    try:
        # 确保连接有效
        await session.execute(text("SELECT 1"))
        yield session
    except Exception as e:
        logger.error(f"Database session error: {str(e)}")
        try:
            await session.rollback()
        except Exception as rollback_error:
            logger.error(f"Error during rollback: {str(rollback_error)}")
        raise
    finally:
        try:
            await session.close()
        except Exception as e:
            logger.error(f"Error closing session: {str(e)}")
            # 如果关闭会话时出错，尝试重置事件循环
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            except Exception as loop_error:
                logger.error(f"Error resetting event loop: {str(loop_error)}")

# 初始化数据库
async def init_db():
    """初始化数据库表结构"""
    try:
        # 确保有可用的事件循环
        loop = ensure_event_loop()
        
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {str(e)}")
        raise 