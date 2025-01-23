import os
import sys
import logging
from datetime import datetime
from pathlib import Path

def setup_logger():
    """设置日志记录器"""
    # 配置根日志记录器
    logging.basicConfig(
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        level=logging.INFO,
        force=True  # 强制所有处理器使用这个格式
    )
    
    # 获取根日志记录器
    root_logger = logging.getLogger()
    
    # 移除所有现有的处理器
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # 创建我们的日志记录器
    logger = logging.getLogger("cursor_api")
    logger.propagate = False  # 防止日志传播到父记录器
    
    # 在非 Vercel 环境中使用文件处理器
    if not os.environ.get("VERCEL"):
        try:
            log_dir = Path("logs")
            log_dir.mkdir(exist_ok=True)
            
            log_file = log_dir / f"{datetime.now().strftime('%Y-%m-%d')}.log"
            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setFormatter(logging.Formatter(
                "%(asctime)s - %(levelname)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            ))
            logger.addHandler(file_handler)
        except OSError:
            pass
    
    # 总是添加标准输出处理器
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    ))
    logger.addHandler(stream_handler)
    
    return logger

# 创建全局logger实例
logger = setup_logger()

def info(message):
    """记录信息级别的日志"""
    logger.info(message)

def error(message):
    """记录错误级别的日志"""
    logger.error(message)

def warning(message):
    """记录警告级别的日志"""
    logger.warning(message)

def debug(message):
    """记录调试级别的日志"""
    logger.debug(message) 