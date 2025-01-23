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
import asyncio
import subprocess
import sys
import os
import traceback
from fastapi.responses import JSONResponse
from cursor_pro_keep_alive import main as register_account
from browser_utils import BrowserManager
from logger import info, error

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
        # 初始化注册状态
        global registration_status
        registration_status.update({
            "is_running": False,
            "last_status": None,
            "last_run": None,
            "next_run": None,
            "total_runs": 0,
            "successful_runs": 0,
            "failed_runs": 0
        })
        info("系统启动完成，数据库已初始化")
    except Exception as e:
        error(f"系统启动失败: {str(e)}")
        error(traceback.format_exc())
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """关闭时清理资源"""
    try:
        # 取消注册任务
        if background_tasks["registration_task"]:
            if not background_tasks["registration_task"].done():
                background_tasks["registration_task"].cancel()
                try:
                    await background_tasks["registration_task"]
                except asyncio.CancelledError:
                    info("关机时取消注册任务")
            background_tasks["registration_task"] = None
            registration_status["is_running"] = False
        info("系统关闭完成")
    except Exception as e:
        error(f"系统关闭出错: {str(e)}")
        error(traceback.format_exc())

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
    browser_manager = None
    
    try:
        info("注册任务开始运行")
        
        while registration_status["is_running"]:
            try:
                count = await get_account_count()
                if count >= MAX_ACCOUNTS:
                    info(f"已达到最大账号数量 ({count}/{MAX_ACCOUNTS})")
                    registration_status["last_status"] = "completed"
                    registration_status["is_running"] = False
                    break

                info(f"开始注册尝试 (当前账号数: {count}/{MAX_ACCOUNTS})")
                registration_status["last_run"] = datetime.now().isoformat()
                registration_status["total_runs"] += 1

                # 初始化浏览器管理器
                if not browser_manager:
                    browser_manager = BrowserManager()
                
                # 调用注册函数
                success = await asyncio.get_event_loop().run_in_executor(None, register_account)
                
                if success:
                    registration_status["successful_runs"] += 1
                    registration_status["last_status"] = "success"
                    info("注册成功")
                else:
                    registration_status["failed_runs"] += 1
                    registration_status["last_status"] = "failed"
                    info("注册失败")
                
                # 更新下次运行时间
                next_run = datetime.now().timestamp() + REGISTRATION_INTERVAL
                registration_status["next_run"] = next_run
                
                info(f"等待 {REGISTRATION_INTERVAL} 秒后进行下一次尝试")
                await asyncio.sleep(REGISTRATION_INTERVAL)
                
            except asyncio.CancelledError:
                info("注册迭代被取消")
                raise
            except Exception as e:
                registration_status["failed_runs"] += 1
                registration_status["last_status"] = "error"
                error(f"注册过程出错: {str(e)}")
                error(traceback.format_exc())
                if not registration_status["is_running"]:
                    break
                await asyncio.sleep(REGISTRATION_INTERVAL)
    except asyncio.CancelledError:
        info("注册任务被取消")
        raise
    except Exception as e:
        error(f"注册任务致命错误: {str(e)}")
        error(traceback.format_exc())
        raise
    finally:
        registration_status["is_running"] = False
        if browser_manager:
            browser_manager.cleanup()

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
        error(f"根端点错误: {str(e)}")
        error(traceback.format_exc())
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
        error(f"获取账号失败: {str(e)}")
        error(traceback.format_exc())
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
        error(f"获取随机账号失败: {str(e)}")
        error(traceback.format_exc())
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
        error(f"创建账号失败: {str(e)}")
        error(traceback.format_exc())
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
        error(f"删除账号失败: {str(e)}")
        error(traceback.format_exc())
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
            info(f"拒绝注册请求 - 已达到最大账号数 ({count}/{MAX_ACCOUNTS})")
            return {
                "success": False,
                "message": f"Already have maximum number of accounts ({MAX_ACCOUNTS})"
            }

        # 如果任务已在运行，返回相应消息
        if background_tasks["registration_task"] and not background_tasks["registration_task"].done():
            info("注册请求被忽略 - 任务已在运行")
            return {
                "success": True,
                "message": "Registration task is already running",
                "status": {
                    "is_running": registration_status["is_running"],
                    "last_run": registration_status["last_run"],
                    "next_run": datetime.fromtimestamp(registration_status["next_run"]).isoformat() if registration_status["next_run"] else None,
                    "last_status": registration_status["last_status"]
                }
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
                info("注册任务被取消")
                registration_status["last_status"] = "cancelled"
            except Exception as e:
                error(f"注册任务失败: {str(e)}")
                error(traceback.format_exc())
                registration_status["last_status"] = "error"
            finally:
                if registration_status["is_running"]:  # 只有在任务仍在运行时才更新状态
                    registration_status["is_running"] = False
                background_tasks["registration_task"] = None
        
        task.add_done_callback(task_done_callback)
        info("手动启动注册任务")
        
        # 等待任务实际开始运行
        await asyncio.sleep(1)
        
        # 检查任务是否成功启动
        if task.done():
            try:
                task.result()  # 如果任务已完成，检查是否有异常
            except Exception as e:
                error(f"注册任务启动失败: {str(e)}")
                error(traceback.format_exc())
                registration_status["is_running"] = False
                registration_status["last_status"] = "error"
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to start registration task: {str(e)}"
                )
        
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
        error(f"启动注册任务失败: {str(e)}")
        error(traceback.format_exc())
        registration_status["is_running"] = False
        registration_status["last_status"] = "error"
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
            info("注册任务被取消")
        
        background_tasks["registration_task"] = None
        registration_status["is_running"] = False
        registration_status["last_status"] = "manually stopped"
        
        return {
            "success": True,
            "message": "Registration task stopped successfully"
        }
    except Exception as e:
        error(f"停止注册任务失败: {str(e)}")
        error(traceback.format_exc())
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
        
        status_info = {
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
        
        info(f"请求注册状态 (当前账号数: {count}, 状态: {task_status})")
        return status_info
        
    except Exception as e:
        error(f"获取注册状态失败: {str(e)}")
        error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get registration status: {str(e)}"
        )

# 自定义异常处理
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    error(f"HTTP错误发生: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "message": exc.detail}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    error(f"意外错误发生: {str(exc)}")
    error(f"错误详情: {traceback.format_exc()}")
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