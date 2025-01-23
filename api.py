from fastapi import FastAPI, HTTPException, Depends, status
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete
from pathlib import Path
from database import get_session, AccountModel, init_db
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import uvicorn
import logging
import asyncio
import subprocess
import sys
import os
import traceback
from fastapi.responses import JSONResponse

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# 常量定义
MAX_ACCOUNTS = 50
REGISTRATION_INTERVAL = 60  # 每次注册间隔60秒

app = FastAPI(
    title="Cursor Account API",
    description="API for managing Cursor accounts",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    debug=os.getenv('DEBUG', 'false').lower() == 'true'
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    """启动时初始化数据库并开始自动注册进程"""
    try:
        await init_db()
        logger.info("Database initialized successfully")
        
        # 启动自动注册任务
        asyncio.create_task(run_registration())
        logger.info("Auto registration task started")
    except Exception as e:
        logger.error(f"Startup error: {str(e)}")
        raise

class Account(BaseModel):
    email: str
    password: Optional[str] = None
    token: str
    usage_limit: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class AccountResponse(BaseModel):
    success: bool
    data: Optional[Account] = None
    message: str = ""

async def get_account_count() -> int:
    """获取当前账号总数"""
    async with get_session() as session:
        result = await session.execute(select(func.count()).select_from(AccountModel))
        return result.scalar()

async def run_registration():
    """运行注册脚本"""
    while True:
        try:
            async with get_session() as session:
                count = await get_account_count()
                if count >= MAX_ACCOUNTS:
                    logger.info(f"Already have {count} accounts, no need to register more")
                    break

                logger.info(f"Current account count: {count}, starting registration...")
                
                # 获取当前工作目录
                current_dir = Path(__file__).parent.absolute()
                script_path = current_dir / "cursor_pro_keep_alive.py"
                
                # 设置环境变量
                env = os.environ.copy()
                env["PYTHONPATH"] = str(current_dir)
                env["PYTHONIOENCODING"] = "utf-8"
                
                # 直接运行脚本，实时显示输出
                try:
                    process = await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: subprocess.run(
                            [sys.executable, str(script_path)],
                            env=env,
                            cwd=str(current_dir)
                        )
                    )
                    
                    if process.returncode != 0:
                        logger.error(f"Registration failed with code {process.returncode}")
                        
                except Exception as e:
                    logger.error(f"Error running registration script: {str(e)}")
                
                logger.info(f"Waiting {REGISTRATION_INTERVAL} seconds before next attempt...")
                await asyncio.sleep(REGISTRATION_INTERVAL)
        except Exception as e:
            logger.error(f"Error in registration process: {str(e)}")
            await asyncio.sleep(REGISTRATION_INTERVAL)

@app.get("/", tags=["General"])
async def root():
    """API根路径，返回API信息"""
    try:
        # 获取当前账号数量
        account_count = await get_account_count()
        
        return {
            "service": {
                "name": "Cursor Account API",
                "version": "1.0.0",
                "status": "running",
                "description": "API for managing Cursor Pro accounts and automatic registration"
            },
            "statistics": {
                "total_accounts": account_count,
                "max_accounts": MAX_ACCOUNTS,
                "remaining_slots": MAX_ACCOUNTS - account_count,
                "registration_interval": f"{REGISTRATION_INTERVAL} seconds"
            },
            "endpoints": {
                "documentation": {
                    "swagger": "/docs",
                    "redoc": "/redoc"
                },
                "health": {
                    "check": "/health",
                    "registration_status": "/registration/status"
                },
                "accounts": {
                    "list_all": "/accounts",
                    "random": "/account/random",
                    "create": {
                        "path": "/account",
                        "method": "POST"
                    },
                    "delete": {
                        "path": "/account/{email}",
                        "method": "DELETE"
                    }
                }
            },
            "support": {
                "github": "https://github.com/Elawen-Carl/cursor-account-api",
                "author": "Elawen Carl",
                "contact": "elawencarl@gmail.com"
            },
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error in root endpoint: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error fetching API information"
        )

@app.get("/health", tags=["General"])
async def health_check():
    """健康检查端点"""
    return {"status": "healthy"}

@app.get("/accounts", response_model=List[Account], tags=["Accounts"])
async def get_accounts():
    """获取所有可用的账号和token"""
    try:
        async with get_session() as session:
            result = await session.execute(select(AccountModel))
            accounts = result.scalars().all()
            
            if not accounts:
                raise HTTPException(status_code=404, detail="No accounts found")
            return accounts
    except Exception as e:
        logger.error(f"Error fetching accounts: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/account/random", response_model=AccountResponse, tags=["Accounts"])
async def get_random_account():
    """随机获取一个可用的账号和token"""
    try:
        async with get_session() as session:
            result = await session.execute(
                select(AccountModel).order_by(func.random()).limit(1)
            )
            account = result.scalar_one_or_none()
            
            if not account:
                return AccountResponse(
                    success=False,
                    message="No accounts available"
                )
            
            return AccountResponse(
                success=True,
                data=Account.from_orm(account)
            )
    except Exception as e:
        logger.error(f"Error fetching random account: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/account", response_model=AccountResponse, tags=["Accounts"])
async def create_account(account: Account):
    """创建新账号"""
    try:
        async with get_session() as session:
            db_account = AccountModel(
                email=account.email,
                password=account.password,
                token=account.token,
                usage_limit=account.usage_limit
            )
            session.add(db_account)
            await session.commit()
            return AccountResponse(
                success=True,
                data=account,
                message="Account created successfully"
            )
    except Exception as e:
        logger.error(f"Error creating account: {str(e)}")
        return AccountResponse(
            success=False,
            message=f"Failed to create account: {str(e)}"
        )

@app.delete("/account/{email}", response_model=AccountResponse, tags=["Accounts"])
async def delete_account(email: str):
    """删除指定邮箱的账号"""
    try:
        async with get_session() as session:
            # 先检查账号是否存在
            result = await session.execute(
                select(AccountModel).where(AccountModel.email == email)
            )
            account = result.scalar_one_or_none()
            
            if not account:
                return AccountResponse(
                    success=False,
                    message=f"Account with email {email} not found"
                )
            
            # 删除账号
            await session.execute(
                delete(AccountModel).where(AccountModel.email == email)
            )
            await session.commit()
            
            return AccountResponse(
                success=True,
                message=f"Account {email} deleted successfully"
            )
    except Exception as e:
        logger.error(f"Error deleting account {email}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete account: {str(e)}"
        )

@app.get("/registration/status", tags=["Registration"])
async def get_registration_status():
    """获取注册状态"""
    try:
        async with get_session() as session:
            count = await get_account_count()
            return {
                "current_count": count,
                "max_accounts": MAX_ACCOUNTS,
                "is_registration_active": count < MAX_ACCOUNTS,
                "remaining_slots": MAX_ACCOUNTS - count
            }
    except Exception as e:
        logger.error(f"Error getting registration status: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

# 自定义异常处理
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    logger.error(f"HTTP error occurred: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "message": exc.detail}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    logger.error(f"Unexpected error occurred: {str(exc)}")
    logger.error(f"Error details: {traceback.format_exc()}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "message": "Internal server error occurred",
            "detail": str(exc) if app.debug else None
        }
    )

if __name__ == "__main__":
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        access_log=True
    ) 