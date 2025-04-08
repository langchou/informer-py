"""
通知模块 - 处理钉钉通知
"""

import time
import hmac
import hashlib
import base64
import urllib.parse
import requests
from loguru import logger


class DingTalkNotifier:
    """钉钉通知类"""
    
    def __init__(self, token, secret):
        """
        初始化钉钉通知器
        
        Args:
            token: 钉钉机器人的access_token
            secret: 钉钉机器人的签名密钥
        """
        self.token = token
        self.secret = secret
        self.webhook_url = f"https://oapi.dingtalk.com/robot/send?access_token={token}"
    
    def _generate_signature(self):
        """
        生成钉钉签名
        
        Returns:
            str: 签名字符串
        """
        timestamp = str(round(time.time() * 1000))
        string_to_sign = f"{timestamp}\n{self.secret}"
        hmac_code = hmac.new(
            self.secret.encode(), string_to_sign.encode(), digestmod=hashlib.sha256
        ).digest()
        sign = urllib.parse.quote_plus(base64.b64encode(hmac_code).decode())
        return timestamp, sign
    
    def send_text_notification(self, title, message, at_mobiles=None):
        """
        发送文本通知
        
        Args:
            title: 通知标题
            message: 通知内容
            at_mobiles: 需要@的手机号列表
            
        Returns:
            bool: 是否发送成功
        """
        try:
            timestamp, sign = self._generate_signature()
            webhook_url = f"{self.webhook_url}&timestamp={timestamp}&sign={sign}"
            
            # 构建消息内容，去除不必要的空行
            content = message
            if title:
                content = f"{title}\n\n{message}"
            
            data = {
                "msgtype": "text",
                "text": {
                    "content": content
                },
                "at": {
                    "atMobiles": at_mobiles or [],
                    "isAtAll": False
                }
            }
            
            response = requests.post(webhook_url, json=data)
            result = response.json()
            
            if result.get('errcode') == 0:
                logger.info(f"钉钉通知发送成功: {title if title else '无标题'}")
                return True
            else:
                logger.error(f"钉钉通知发送失败: {result}")
                return False
        except Exception as e:
            logger.error(f"钉钉通知发送异常: {e}")
            return False
    
    def send_markdown_notification(self, title, message, at_mobiles=None):
        """
        发送Markdown格式通知
        
        Args:
            title: 通知标题
            message: Markdown格式的通知内容
            at_mobiles: 需要@的手机号列表
            
        Returns:
            bool: 是否发送成功
        """
        try:
            timestamp, sign = self._generate_signature()
            webhook_url = f"{self.webhook_url}&timestamp={timestamp}&sign={sign}"
            
            # 构建@文本
            at_text = ""
            if at_mobiles:
                for mobile in at_mobiles:
                    at_text += f"@{mobile} "
            
            # 构建消息文本，有@用户时才添加额外的换行
            content = message
            if at_text:
                content = f"{message}\n\n{at_text}"
            
            data = {
                "msgtype": "markdown",
                "markdown": {
                    "title": title,
                    "text": content
                },
                "at": {
                    "atMobiles": at_mobiles or [],
                    "isAtAll": False
                }
            }
            
            response = requests.post(webhook_url, json=data)
            result = response.json()
            
            if result.get('errcode') == 0:
                logger.info(f"钉钉通知发送成功: {title if title else '无标题'}")
                return True
            else:
                logger.error(f"钉钉通知发送失败: {result}")
                return False
        except Exception as e:
            logger.error(f"钉钉通知发送异常: {e}")
            return False
    
    def report_error(self, title, error_message):
        """
        报告错误信息
        
        Args:
            title: 错误标题
            error_message: 错误信息
            
        Returns:
            bool: 是否发送成功
        """
        message = f"❌ 错误报告\n\n**错误类型**: {title}\n\n**错误信息**: {error_message}\n\n**发生时间**: {time.strftime('%Y-%m-%d %H:%M:%S')}"
        return self.send_markdown_notification(f"{title}", message) 