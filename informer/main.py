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
from informer.notifier import MultiRobotNotifier, DingTalkNotifier
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
        
        # 初始化多机器人通知器
        notifier = MultiRobotNotifier(config.dingtalk.robots)
        logger.info(f"钉钉通知器初始化完成，共配置 {len(config.dingtalk.robots)} 个机器人")
        
        # 初始化代理管理器
        proxy_manager = None
        if config.proxy_pool_api:
            proxy_manager = ProxyManager(config.proxy_pool_api)
            # 启动代理检查器
            proxy_manager.start_proxy_checker()
            logger.info(f"代理管理器初始化完成，API: {config.proxy_pool_api}")
        else:
            logger.info("未配置代理API，将不使用代理")
        
        # 检查是否有LLM配置
        if config.llm_config:
            logger.info(f"LLM配置已加载，使用模型: {config.llm_config.model}")
        else:
            logger.info("未配置LLM，内容分析功能将被禁用")
        
        # 创建并启动监控器
        monitor = ChiphellMonitor(
            config.cookies,
            None,  # 不再需要传递全局的user_key_words，关键词已经移到各个机器人配置中
            notifier,
            database,
            config.wait_time_range,
            proxy_manager,
            config.llm_config
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
            # 尝试使用多机器人通知器发送错误报告
            if 'notifier' in locals() and isinstance(notifier, MultiRobotNotifier):
                notifier.report_error("程序异常", str(e))
            else:
                # 兼容旧版，如果多机器人通知器初始化失败，使用单一机器人通知
                first_robot = config.dingtalk.robots[0] if config.dingtalk.robots else None
                if first_robot:
                    emergency_notifier = DingTalkNotifier(
                        first_robot.token,
                        first_robot.secret,
                        first_robot.name
                    )
                    emergency_notifier.report_error("程序异常", str(e))
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