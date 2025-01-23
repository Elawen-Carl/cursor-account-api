import os
import sys
import logging
from datetime import datetime
from pathlib import Path

def setup_logger():
    """设置日志记录器"""
    logger = logging.getLogger("cursor_api")
    logger.setLevel(logging.INFO)
    
    # 创建格式化器
    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # 在非 Vercel 环境中使用文件处理器
    if not os.environ.get("VERCEL"):
        try:
            log_dir = Path("logs")
            log_dir.mkdir(exist_ok=True)
            
            log_file = log_dir / f"{datetime.now().strftime('%Y-%m-%d')}.log"
            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except OSError:
            # 如果无法创建文件处理器，使用标准输出
            stream_handler = logging.StreamHandler(sys.stdout)
            stream_handler.setFormatter(formatter)
            logger.addHandler(stream_handler)
    else:
        # 在 Vercel 环境中使用标准输出
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)
    
    return logger

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