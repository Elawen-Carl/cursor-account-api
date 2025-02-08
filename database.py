from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import Column, String, DateTime, Text, text
from datetime import datetime
import os
from dotenv import load_dotenv
from contextlib import asynccontextmanager
from logger import info, error

load_dotenv()


def get_database_url():
    """获取数据库URL并验证配置"""
    required_vars = {
        "POSTGRES_USER": os.getenv("POSTGRES_USER"),
        "POSTGRES_PASSWORD": os.getenv("POSTGRES_PASSWORD"),
        "POSTGRES_HOST": os.getenv("POSTGRES_HOST"),
        "POSTGRES_DATABASE": os.getenv("POSTGRES_DATABASE"),
    }

    # 检查所有必需的环境变量
    missing_vars = [key for key, value in required_vars.items() if not value]
    if missing_vars:
        error_msg = f"缺少必需的环境变量: {', '.join(missing_vars)}"
        error(error_msg)
        raise ValueError(error_msg)

    # 构建数据库URL
    url = f"postgresql+asyncpg://{required_vars['POSTGRES_USER']}:{required_vars['POSTGRES_PASSWORD']}@{required_vars['POSTGRES_HOST']}/{required_vars['POSTGRES_DATABASE']}"
    info("数据库配置加载成功")
    return url


def create_engine():
    """创建数据库引擎"""
    POSTGRES_URL = get_database_url()
    return create_async_engine(
        POSTGRES_URL,
        echo=False,
        connect_args={
            "ssl": True,
            "server_settings": {"client_encoding": "utf8"},
            "command_timeout": 10,
        },
        pool_pre_ping=True,
        poolclass=None,  # 禁用连接池
        future=True,
    )


# 基础模型类
class Base(DeclarativeBase):
    pass


# 账号模型
class AccountModel(Base):
    __tablename__ = "accounts"
    email = Column(String, primary_key=True)
    user = Column(String, nullable=False)
    password = Column(String, nullable=True)
    token = Column(String, nullable=False)
    usage_limit = Column(Text, nullable=True)


@asynccontextmanager
async def get_session() -> AsyncSession:
    """创建数据库会话的异步上下文管理器"""
    # 为每个请求创建新的引擎和会话
    engine = create_engine()
    async_session = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False, future=True
    )

    session = async_session()
    try:
        # 确保连接有效
        await session.execute(text("SELECT 1"))
        yield session
    except Exception as e:
        error(f"数据库会话错误: {str(e)}")
        try:
            await session.rollback()
        except Exception as rollback_error:
            error(f"回滚过程中出错: {str(rollback_error)}")
        raise
    finally:
        try:
            await session.close()
        except Exception as e:
            error(f"关闭会话时出错: {str(e)}")
        try:
            await engine.dispose()
        except Exception as e:
            error(f"释放引擎时出错: {str(e)}")


async def init_db():
    """初始化数据库表结构"""
    try:
        engine = create_engine()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await engine.dispose()
        info("数据库初始化成功")
    except Exception as e:
        error(f"数据库初始化失败: {str(e)}")
        raise
