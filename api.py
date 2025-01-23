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

# 全局状态追踪
registration_status = {
    "is_running": False,
    "last_run": None,
    "last_status": None,
    "next_run": None,
    "total_runs": 0,
    "successful_runs": 0,
    "failed_runs": 0
}

# 全局任务存储
background_tasks = {
    "registration_task": None
}

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
    """启动时初始化数据库"""
    try:
        await init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Startup error: {str(e)}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """关闭时清理资源"""
    try:
        # 取消注册任务
        if background_tasks["registration_task"] and not background_tasks["registration_task"].done():
            background_tasks["registration_task"].cancel()
            try:
                await background_tasks["registration_task"]
            except asyncio.CancelledError:
                logger.info("Registration task cancelled")
    except Exception as e:
        logger.error(f"Shutdown error: {str(e)}")

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
    global registration_status
    try:
        logger.info("Registration task started running")
        
        while registration_status["is_running"]:
            try:
                count = await get_account_count()
                if count >= MAX_ACCOUNTS:
                    logger.info(f"Already have {count} accounts, no need to register more")
                    registration_status["last_status"] = "completed"
                    break

                logger.info(f"Current account count: {count}, starting registration...")
                registration_status["last_run"] = datetime.now().isoformat()
                registration_status["total_runs"] += 1
                
                # 获取当前工作目录
                current_dir = Path(__file__).parent.absolute()
                script_path = current_dir / "cursor_pro_keep_alive.py"
                
                if not script_path.exists():
                    error_msg = "Registration script not found"
                    logger.error(error_msg)
                    registration_status["last_status"] = f"error: {error_msg}"
                    registration_status["failed_runs"] += 1
                    raise FileNotFoundError(error_msg)
                
                # 设置环境变量
                env = os.environ.copy()
                env["PYTHONPATH"] = str(current_dir)
                env["PYTHONIOENCODING"] = "utf-8"
                
                # 运行脚本并实时获取输出
                process = await asyncio.create_subprocess_exec(
                    sys.executable,
                    str(script_path),
                    env=env,
                    cwd=str(current_dir),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                
                stdout, stderr = await process.communicate()
                
                if process.returncode == 0:
                    registration_status["successful_runs"] += 1
                    registration_status["last_status"] = "success"
                    logger.info(f"Registration successful: {stdout.decode()}")
                else:
                    registration_status["failed_runs"] += 1
                    error_msg = stderr.decode() if stderr else f"failed with code {process.returncode}"
                    registration_status["last_status"] = f"failed: {error_msg}"
                    logger.error(f"Registration failed: {error_msg}")
                
                # 更新下次运行时间
                next_run = datetime.now().timestamp() + REGISTRATION_INTERVAL
                registration_status["next_run"] = next_run
                
                logger.info(f"Waiting {REGISTRATION_INTERVAL} seconds before next attempt...")
                await asyncio.sleep(REGISTRATION_INTERVAL)
                
            except asyncio.CancelledError:
                logger.info("Registration iteration cancelled")
                raise
            except Exception as e:
                registration_status["failed_runs"] += 1
                registration_status["last_status"] = f"error: {str(e)}"
                logger.error(f"Error in registration process: {str(e)}")
                logger.error(traceback.format_exc())
                # 如果发生错误，等待一段时间后继续
                await asyncio.sleep(REGISTRATION_INTERVAL)
    except asyncio.CancelledError:
        logger.info("Registration task cancelled")
        raise
    except Exception as e:
        logger.error(f"Fatal error in registration task: {str(e)}")
        logger.error(traceback.format_exc())
        raise
    finally:
        registration_status["is_running"] = False

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
            "registration_status": {
                "is_running": registration_status["is_running"],
                "last_run": registration_status["last_run"],
                "last_status": registration_status["last_status"],
                "next_run": registration_status["next_run"],
                "statistics": {
                    "total_runs": registration_status["total_runs"],
                    "successful_runs": registration_status["successful_runs"],
                    "failed_runs": registration_status["failed_runs"],
                    "success_rate": f"{(registration_status['successful_runs'] / registration_status['total_runs'] * 100):.1f}%" if registration_status['total_runs'] > 0 else "N/A"
                }
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

@app.post("/registration/start", tags=["Registration"])
async def start_registration():
    """手动启动注册任务"""
    global background_tasks, registration_status
    try:
        # 检查是否已达到最大账号数
        count = await get_account_count()
        if count >= MAX_ACCOUNTS:
            return {
                "success": False,
                "message": f"Already have maximum number of accounts ({MAX_ACCOUNTS})"
            }

        # 如果任务已在运行，返回相应消息
        if background_tasks["registration_task"] and not background_tasks["registration_task"].done():
            return {
                "success": False,
                "message": "Registration task is already running"
            }
        
        # 重置注册状态
        registration_status.update({
            "is_running": True,
            "last_status": "starting",
            "last_run": datetime.now().isoformat(),
            "next_run": datetime.now().timestamp() + REGISTRATION_INTERVAL,
            "total_runs": 0,
            "successful_runs": 0,
            "failed_runs": 0
        })
        
        # 创建并启动新任务
        loop = asyncio.get_running_loop()
        task = loop.create_task(run_registration())
        background_tasks["registration_task"] = task
        
        # 添加任务完成回调
        def task_done_callback(task):
            try:
                task.result()  # 这将重新引发任何未处理的异常
            except asyncio.CancelledError:
                logger.info("Registration task was cancelled")
                registration_status["last_status"] = "cancelled"
            except Exception as e:
                logger.error(f"Registration task failed with error: {str(e)}")
                registration_status["last_status"] = f"error: {str(e)}"
                logger.error(traceback.format_exc())
            finally:
                if registration_status["is_running"]:  # 只有在任务仍在运行时才更新状态
                    registration_status["is_running"] = False
        
        task.add_done_callback(task_done_callback)
        logger.info("Registration task manually started")
        
        return {
            "success": True,
            "message": "Registration task started successfully",
            "status": {
                "is_running": registration_status["is_running"],
                "last_run": registration_status["last_run"],
                "next_run": datetime.fromtimestamp(registration_status["next_run"]).isoformat(),
                "last_status": registration_status["last_status"]
            }
        }
    except Exception as e:
        logger.error(f"Error starting registration task: {str(e)}")
        logger.error(traceback.format_exc())
        registration_status["is_running"] = False
        registration_status["last_status"] = f"error: {str(e)}"
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start registration task: {str(e)}"
        )

@app.post("/registration/stop", tags=["Registration"])
async def stop_registration():
    """手动停止注册任务"""
    global background_tasks
    try:
        if not background_tasks["registration_task"] or background_tasks["registration_task"].done():
            return {
                "success": False,
                "message": "No running registration task found"
            }
        
        background_tasks["registration_task"].cancel()
        try:
            await background_tasks["registration_task"]
        except asyncio.CancelledError:
            logger.info("Registration task cancelled")
        
        background_tasks["registration_task"] = None
        registration_status["is_running"] = False
        registration_status["last_status"] = "manually stopped"
        
        return {
            "success": True,
            "message": "Registration task stopped successfully"
        }
    except Exception as e:
        logger.error(f"Error stopping registration task: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stop registration task: {str(e)}"
        )

@app.get("/registration/status", tags=["Registration"])
async def get_registration_status():
    """获取注册状态"""
    try:
        count = await get_account_count()
        task_status = "running" if (background_tasks["registration_task"] and not background_tasks["registration_task"].done()) else "stopped"
        
        return {
            "current_count": count,
            "max_accounts": MAX_ACCOUNTS,
            "is_registration_active": count < MAX_ACCOUNTS,
            "remaining_slots": MAX_ACCOUNTS - count,
            "task_status": task_status,
            "registration_details": {
                "is_running": registration_status["is_running"],
                "last_run": registration_status["last_run"],
                "last_status": registration_status["last_status"],
                "next_run": registration_status["next_run"],
                "statistics": {
                    "total_runs": registration_status["total_runs"],
                    "successful_runs": registration_status["successful_runs"],
                    "failed_runs": registration_status["failed_runs"],
                    "success_rate": f"{(registration_status['successful_runs'] / registration_status['total_runs'] * 100):.1f}%" if registration_status['total_runs'] > 0 else "N/A"
                }
            }
        }
    except Exception as e:
        logger.error(f"Error getting registration status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get registration status: {str(e)}"
        )

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