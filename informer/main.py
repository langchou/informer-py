"""
Chiphell二手区监控工具入口文件
"""

import os
import time
import urllib3
import warnings
from loguru import logger

# 禁用SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore", message="Unverified HTTPS request")

from informer.config import load_config
from informer.logger import setup_logger
from informer.database import Database
from informer.notifier import DingTalkNotifier
from informer.proxy_manager import ProxyManager
from informer.monitor import ChiphellMonitor


def main():
    """主函数入口"""
    try:
        # 加载配置
        config = load_config()
        
        # 设置日志
        setup_logger(
            config.log_config.file,
            config.log_config.max_size,
            config.log_config.max_backups,
            config.log_config.max_age,
            config.log_config.compress,
            config.log_config.level
        )
        
        logger.info("Chiphell二手区监控工具启动")
        
        # 初始化数据库
        db_file = "data/posts.db"
        os.makedirs(os.path.dirname(db_file), exist_ok=True)
        database = Database(db_file)
        logger.info(f"数据库初始化完成: {db_file}")
        
        # 初始化钉钉通知器
        notifier = DingTalkNotifier(
            config.dingtalk.token,
            config.dingtalk.secret
        )
        logger.info("钉钉通知器初始化完成")
        
        # 初始化代理管理器
        proxy_manager = None
        if config.proxy_pool_api:
            proxy_manager = ProxyManager(config.proxy_pool_api)
            # 启动代理检查器
            proxy_manager.start_proxy_checker()
            logger.info(f"代理管理器初始化完成，API: {config.proxy_pool_api}")
        else:
            logger.info("未配置代理API，将不使用代理")
        
        # 创建并启动监控器
        monitor = ChiphellMonitor(
            config.cookies,
            config.user_key_words,
            notifier,
            database,
            config.wait_time_range,
            proxy_manager
        )
        logger.info("监控器初始化完成，开始监控...")
        
        # 开始监控
        monitor.monitor()
    
    except KeyboardInterrupt:
        logger.info("程序被用户中断")
    except Exception as e:
        logger.error(f"程序运行出错: {e}")
        
        # 尝试发送错误报告
        try:
            notifier = DingTalkNotifier(
                config.dingtalk.token, 
                config.dingtalk.secret
            )
            notifier.report_error("程序异常", str(e))
        except:
            pass
        
        # 等待5秒后退出
        time.sleep(5)
    finally:
        # 关闭数据库连接
        try:
            database.close()
        except:
            pass
        
        logger.info("程序已退出")


if __name__ == "__main__":
    main() 