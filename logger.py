import os
import sys
import logging
from pathlib import Path
from datetime import datetime

def setup_logger(name='cursor_logger'):
    """设置日志系统"""
    # 创建logs目录
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # 设置日志文件名（使用当前日期）
    log_file = log_dir / f"{datetime.now().strftime('%Y-%m-%d')}.log"
    
    # 创建格式化器
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 文件处理器
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)
    
    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)
    
    # 配置根日志记录器
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

# 创建全局logger实例
logger = setup_logger()

def info(*args):
    """记录信息日志"""
    try:
        message = ' '.join(str(arg) for arg in args)
        logger.info(message)
    except Exception as e:
        logger.error(f"记录信息日志时出错: {str(e)}")

def error(*args):
    """记录错误日志"""
    try:
        message = ' '.join(str(arg) for arg in args)
        logger.error(message)
    except Exception as e:
        logger.error(f"记录错误日志时出错: {str(e)}")

def warning(*args):
    """记录警告日志"""
    try:
        message = ' '.join(str(arg) for arg in args)
        logger.warning(message)
    except Exception as e:
        logger.error(f"记录警告日志时出错: {str(e)}")

def debug(*args):
    """记录调试日志"""
    try:
        message = ' '.join(str(arg) for arg in args)
        logger.debug(message)
    except Exception as e:
        logger.error(f"记录调试日志时出错: {str(e)}") 