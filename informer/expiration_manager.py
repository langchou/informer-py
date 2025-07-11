"""
过期管理模块 - 处理用户订阅过期相关功能
"""

from datetime import datetime, timedelta
from loguru import logger


class ExpirationManager:
    """用户过期管理器"""
    
    def __init__(self, notifier):
        """初始化过期管理器
        
        Args:
            notifier: 通知管理器实例
        """
        self.notifier = notifier
        self.logger = logger.bind(name="ExpirationManager")
        
    def is_user_expired(self, expire_date: str, is_permanent: bool) -> bool:
        """检查用户是否已过期
        
        Args:
            expire_date: 过期日期 (YYYY-MM-DD)
            is_permanent: 是否永久有效
            
        Returns:
            bool: 如果用户已过期，返回True，否则返回False
        """
        if is_permanent or not expire_date:
            return False
            
        try:
            expire_datetime = datetime.strptime(expire_date, "%Y-%m-%d")
            current_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            return current_date > expire_datetime
        except Exception as e:
            self.logger.error(f"检查用户过期失败: {e}")
            return False

    def check_and_notify_expiring_users(self):
        """检查并通知即将过期或已过期的用户"""
        try:
            if not self.notifier or not hasattr(self.notifier, "robots") or not self.notifier.robots:
                self.logger.warning("无法执行过期检查：通知器实例不可用或没有配置机器人")
                return

            self.logger.info("开始检查用户过期状态...")
            current_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            
            # 提前7天和3天通知
            warning_days = [7, 3]
            
            # 遍历所有机器人
            for robot in self.notifier.robots:
                robot_config = robot.get("config")
                robot_notifier = robot.get("notifier")
                
                if not robot_config or not robot_notifier or not hasattr(robot_config, "users"):
                    continue
                    
                self.logger.debug(f"检查机器人 [{robot_config.name}] 的用户过期状态")
                
                # 新配置格式：通过 users 字典访问
                if isinstance(robot_config.users, dict):
                    for phone, user_data in robot_config.users.items():
                        # 检查是否永久有效 - 使用字典访问方式
                        is_permanent = user_data.get("is_permanent", True)
                        expire_date = user_data.get("expire_date", "")
                        
                        if is_permanent:
                            self.logger.debug(f"用户 {phone} 是永久有效的，跳过检查")
                            continue
                        
                        if not expire_date:
                            self.logger.debug(f"用户 {phone} 没有设置过期日期，跳过检查")
                            continue
                        
                        self._check_user_expiration(robot_notifier, phone, expire_date, current_date, warning_days)
                # 新配置格式：通过 UserConfig 对象列表访问
                elif hasattr(robot_config, "users") and isinstance(robot_config.users, list):
                    for user in robot_config.users:
                        if not hasattr(user, "phone"):
                            continue
                            
                        # 检查是否永久有效 - 使用对象访问方式
                        is_permanent = False  # 默认假设不是永久有效
                        if hasattr(user, "is_permanent"):
                            is_permanent = user.is_permanent
                        
                        expire_date = ""
                        if hasattr(user, "expire_date"):
                            expire_date = user.expire_date
                        
                        if is_permanent:
                            self.logger.debug(f"用户 {user.phone} 是永久有效的，跳过检查")
                            continue
                        
                        if not expire_date:
                            self.logger.debug(f"用户 {user.phone} 没有设置过期日期，跳过检查")
                            continue
                        
                        self._check_user_expiration(robot_notifier, user.phone, expire_date, current_date, warning_days)
                        
            self.logger.info("用户过期检查完成")
            
        except Exception as e:
            self.logger.error(f"执行过期检查时出错: {e}")
            
    def _check_user_expiration(self, robot_notifier, phone, expire_date, current_date, warning_days):
        """检查单个用户的过期状态并发送通知
        
        Args:
            robot_notifier: 机器人通知器
            phone: 用户手机号
            expire_date: 过期日期
            current_date: 当前日期
            warning_days: 提前警告的天数列表
        """
        try:
            # 解析过期日期
            expire_datetime = datetime.strptime(expire_date, "%Y-%m-%d")
            
            # 检查是否已过期
            if current_date > expire_datetime:
                self.logger.info(f"用户 {phone} 已过期 ({expire_date})")
                
                # 发送已过期通知
                message = (
                    f"⚠️ 用户订阅已过期\n\n"
                    f"尊敬的用户，您的订阅已于 **{expire_date}** 过期。\n\n"
                    f"请尽快联系管理员续费以继续使用服务。"
                )
                
                robot_notifier.send_markdown_notification(
                    "账户过期通知", 
                    message, 
                    [phone]
                )
                
                return
            
            # 检查是否即将过期
            days_to_expire = (expire_datetime - current_date).days
            
            if days_to_expire in warning_days:
                self.logger.info(f"用户 {phone} 将在 {days_to_expire} 天后过期 ({expire_date})")
                
                # 发送即将过期通知
                message = (
                    f"⚠️ 用户订阅即将过期\n\n"
                    f"尊敬的用户，您的订阅将在 **{days_to_expire}** 天后 ({expire_date}) 过期。\n\n"
                    f"请及时联系管理员续费以确保服务不中断。"
                )
                
                robot_notifier.send_markdown_notification(
                    "账户即将过期通知", 
                    message, 
                    [phone]
                )
            
        except Exception as e:
            self.logger.error(f"检查用户 {phone} 过期状态时出错: {e}")
