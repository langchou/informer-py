"""
日志模块 - 处理日志输出
"""

import os
import sys
from loguru import logger


def setup_logger(file, max_size, max_backups, max_age, compress, level):
    """
    配置日志记录器
    
    Args:
        file: 日志文件路径
        max_size: 单个日志文件最大大小 (MB)
        max_backups: 最大备份文件数
        max_age: 日志保留天数
        compress: 是否压缩旧日志
        level: 日志级别
    
    Returns:
        配置好的logger对象
    """
    # 确保日志目录存在
    log_dir = os.path.dirname(file)
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # 移除默认处理器
    logger.remove()

    # 添加控制台输出
    logger.add(
        sys.stdout,
        level=level.upper(),
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
    )

    # 添加文件输出
    logger.add(
        file,
        rotation=f"{max_size} MB",
        retention=max_backups,
        enqueue=True,
        compression="zip" if compress else None,
        level=level.upper(),
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}"
    )

    return logger 