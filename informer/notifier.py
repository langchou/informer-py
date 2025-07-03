"""
通知模块 - 处理钉钉通知
"""

import time
import hmac
import hashlib
import base64
import urllib.parse
import requests
import json
from loguru import logger


class DingTalkNotifier:
    """钉钉通知类"""
    
    def __init__(self, token, secret, name="未命名机器人"):
        """
        初始化钉钉通知器
        
        Args:
            token: 钉钉机器人的access_token
            secret: 钉钉机器人的签名密钥
            name: 机器人名称，用于日志
        """
        self.name = name
        self.token = token
        self.secret = secret
        self.webhook_url = f"https://oapi.dingtalk.com/robot/send?access_token={token}"
        logger.debug(f"初始化钉钉机器人: [{name}] token长度: {len(token)}, secret长度: {len(secret)}")
    
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
            # 检查token和secret
            if not self.token or not self.secret:
                logger.error(f"机器人 [{self.name}] 无效的token或secret")
                return False
                
            logger.debug(f"机器人 [{self.name}] 正在准备发送通知, @手机号: {at_mobiles}")
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
            
            logger.debug(f"机器人 [{self.name}] 正在发送请求到: {self.webhook_url[:50]}...，消息长度: {len(content)}字符")
            response = requests.post(webhook_url, json=data)
            result = response.json()
            
            if result.get('errcode') == 0:
                logger.info(f"钉钉通知 [{self.name}] 发送成功: {title if title else '无标题'}")
                return True
            else:
                logger.error(f"钉钉通知 [{self.name}] 发送失败: 错误码={result.get('errcode')}, 错误信息={result.get('errmsg')}")
                return False
        except requests.exceptions.RequestException as e:
            logger.error(f"钉钉通知 [{self.name}] 网络请求异常: {e}")
            return False
        except json.JSONDecodeError as e:
            logger.error(f"钉钉通知 [{self.name}] JSON解析异常: {e}")
            return False
        except Exception as e:
            logger.error(f"钉钉通知 [{self.name}] 发送异常: {e}")
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
                logger.info(f"钉钉通知 [{self.name}] 发送成功: {title if title else '无标题'}")
                return True
            else:
                logger.error(f"钉钉通知 [{self.name}] 发送失败: {result}")
                return False
        except Exception as e:
            logger.error(f"钉钉通知 [{self.name}] 发送异常: {e}")
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


class MultiRobotNotifier:
    """多机器人通知管理器"""
    
    def __init__(self, robot_configs):
        """
        初始化多机器人通知管理器
        
        Args:
            robot_configs: 机器人配置列表，每项包含 name, token, secret, user_key_words
        """
        self.notifiers = []
        self.robot_configs = []
        
        logger.debug(f"正在初始化多机器人通知管理器，配置了 {len(robot_configs)} 个机器人")
        
        # 创建所有启用的通知器实例
        for config in robot_configs:
            logger.debug(f"检查机器人配置: {config.name}, enabled={config.enabled}, token长度={len(config.token) if config.token else 0}, secret长度={len(config.secret) if config.secret else 0}")
            if config.enabled and config.token and config.secret:
                notifier = DingTalkNotifier(
                    token=config.token,
                    secret=config.secret,
                    name=config.name
                )
                self.notifiers.append(notifier)
                self.robot_configs.append(config)  # 保存机器人配置，用于关键词匹配
                logger.info(f"初始化钉钉机器人: {config.name}, receive_all={config.receive_all}")
                
                # 打印每个机器人配置的用户信息
                if hasattr(config, 'users') and config.users:
                    for user in config.users:
                        logger.debug(f"机器人 [{config.name}] 配置用户: {user.phone}, always_at={user.always_at}, 关键词数量={len(user.keywords)}")
            else:
                logger.warning(f"机器人 [{config.name}] 未启用或缺少token/secret，已跳过")
        
        if not self.notifiers:
            logger.warning("没有可用的钉钉机器人，通知功能将被禁用")
    
    def match_keyword_to_robot(self, title):
        """
        将帖子标题匹配到对应的机器人和要@的手机号
        
        Args:
            title: 帖子标题
            
        Returns:
            list: 元组列表 [(机器人索引, [匹配到的关键词手机号列表], [总是@的手机号列表]), ...]
        """
        matches = []
        logger.debug(f"正在匹配标题: '{title}' 到 {len(self.robot_configs)} 个机器人")
        
        for robot_idx, config in enumerate(self.robot_configs):
            # 收集两类需要@的手机号
            matched_phones = []  # 关键词匹配到的手机号
            always_at_phones = []  # 配置了always_at=True的手机号
            
            logger.debug(f"检查机器人 [{config.name}] 的关键词匹配")
            
            # 优先使用新的用户配置
            if hasattr(config, 'users') and config.users:
                logger.debug(f"机器人 [{config.name}] 使用新版用户配置，有 {len(config.users)} 个用户")
                for user in config.users:
                    # 检查是否需要总是@
                    if user.always_at:
                        always_at_phones.append(user.phone)
                        logger.debug(f"机器人 [{config.name}] 用户 {user.phone} 配置了总是@")
                        continue  # 如果总是@，不需要再检查关键词匹配
                    
                    # 检查关键词匹配
                    if user.keywords:  # 如果用户有关键词配置
                        logger.debug(f"机器人 [{config.name}] 用户 {user.phone} 配置了 {len(user.keywords)} 个关键词")
                        for keyword in user.keywords:
                            lower_keyword = keyword.lower()
                            lower_title = title.lower()
                            if lower_keyword in lower_title:
                                matched_phones.append(user.phone)
                                logger.debug(f"机器人 [{config.name}] 标题 '{title}' 匹配到关键词 '{keyword}'，将@手机号 {user.phone}")
                                break  # 找到一个匹配即可
            
            # 兼容旧版配置（如果没有使用新版user配置）
            elif hasattr(config, 'user_key_words') and config.user_key_words:
                logger.debug(f"机器人 [{config.name}] 使用旧版关键词配置，有 {len(config.user_key_words)} 个用户")
                # 遍历机器人配置的用户关键词
                for phone, keywords in config.user_key_words.items():
                    logger.debug(f"机器人 [{config.name}] 用户 {phone} 配置了 {len(keywords)} 个关键词")
                    for keyword in keywords:
                        lower_keyword = keyword.lower()
                        lower_title = title.lower()
                        if lower_keyword in lower_title:
                            # 该手机号的关键词匹配到了标题
                            matched_phones.append(phone)
                            logger.debug(f"机器人 [{config.name}] 标题 '{title}' 匹配到关键词 '{keyword}'，将@手机号 {phone}")
                            break  # 找到一个匹配关键词即可，不需要继续检查该手机号的其他关键词
            
            # 如果该机器人有需要@的手机号，添加到结果中
            if matched_phones or always_at_phones:
                matches.append((robot_idx, matched_phones, always_at_phones))
                logger.debug(f"机器人 [{config.name}] 匹配到 {len(matched_phones)} 个关键词匹配手机号, {len(always_at_phones)} 个总是@的手机号")
            # 如果没有任何匹配，但机器人配置了receive_all=True，也将其添加到结果中（只@总是@的用户）
            elif config.receive_all:
                logger.debug(f"机器人 [{config.name}] 没有匹配关键词，但配置了receive_all=True，将添加到结果中")
                matches.append((robot_idx, [], always_at_phones))
        
        return matches
    
    def send_notification_by_keyword_match(self, title, message, post_title):
        """
        根据帖子标题匹配关键词，向对应机器人发送通知并@匹配到的手机号
        
        Args:
            title: 通知标题
            message: 通知内容
            post_title: 帖子标题，用于关键词匹配
            
        Returns:
            bool: 是否至少有一个机器人成功发送
        """
        if not self.notifiers:
            logger.warning("没有可用的钉钉机器人，跳过通知发送")
            return False
        
        logger.debug(f"开始为标题 '{post_title}' 匹配机器人，当前有 {len(self.notifiers)} 个机器人可用")
        
        # 匹配标题与机器人关键词，获取匹配的机器人和需要@的手机号
        # 现在match_keyword_to_robot会返回所有匹配关键词的机器人，以及配置了receive_all=True的机器人
        robot_matches = self.match_keyword_to_robot(post_title)
        logger.info(f"标题 '{post_title}' 匹配到 {len(robot_matches)} 个机器人")
        
        # 如果没有任何匹配，直接返回
        if not robot_matches:
            logger.info(f"标题 '{post_title}' 没有匹配到任何机器人，跳过通知")
            return False
        
        # 有匹配的机器人，向它们发送通知
        success_count = 0
        for robot_idx, matched_phones, always_at_phones in robot_matches:
            # 合并两种需要@的手机号（去重）
            at_phones = list(set(matched_phones + always_at_phones))
            
            notifier = self.notifiers[robot_idx]
            config = self.robot_configs[robot_idx]
            logger.debug(f"正在通过机器人 [{config.name}] 发送通知, @手机号: {at_phones}")
            if notifier.send_text_notification(title, message, at_phones):
                success_count += 1
                logger.info(f"机器人 [{config.name}] 成功发送通知")
            else:
                logger.error(f"机器人 [{config.name}] 发送通知失败")
        
        if success_count > 0:
            logger.info(f"成功通过 {success_count}/{len(robot_matches)} 个匹配的机器人发送通知")
            return True
        else:
            logger.error("所有匹配的机器人发送通知均失败")
            return False
    
    def send_text_notification(self, title, message, at_mobiles=None):
        """
        向所有启用的机器人发送文本通知
        
        Args:
            title: 通知标题
            message: 通知内容
            at_mobiles: 需要@的手机号列表
            
        Returns:
            bool: 是否至少有一个机器人成功发送
        """
        if not self.notifiers:
            logger.warning("没有可用的钉钉机器人，跳过通知发送")
            return False
        
        success_count = 0
        for notifier in self.notifiers:
            if notifier.send_text_notification(title, message, at_mobiles):
                success_count += 1
        
        if success_count > 0:
            logger.info(f"成功通过 {success_count}/{len(self.notifiers)} 个机器人发送通知")
            return True
        else:
            logger.error("所有机器人发送通知均失败")
            return False
    
    def send_markdown_notification(self, title, message, at_mobiles=None):
        """
        向所有启用的机器人发送Markdown格式通知
        
        Args:
            title: 通知标题
            message: Markdown格式的通知内容
            at_mobiles: 需要@的手机号列表
            
        Returns:
            bool: 是否至少有一个机器人成功发送
        """
        if not self.notifiers:
            logger.warning("没有可用的钉钉机器人，跳过通知发送")
            return False
        
        success_count = 0
        for notifier in self.notifiers:
            if notifier.send_markdown_notification(title, message, at_mobiles):
                success_count += 1
        
        if success_count > 0:
            logger.info(f"成功通过 {success_count}/{len(self.notifiers)} 个机器人发送通知")
            return True
        else:
            logger.error("所有机器人发送通知均失败")
            return False
    
    def report_error(self, title, error_message):
        """
        通过所有启用的机器人报告错误信息
        
        Args:
            title: 错误标题
            error_message: 错误信息
            
        Returns:
            bool: 是否至少有一个机器人成功发送
        """
        if not self.notifiers:
            logger.warning("没有可用的钉钉机器人，跳过错误报告")
            return False
        
        success_count = 0
        for notifier in self.notifiers:
            if notifier.report_error(title, error_message):
                success_count += 1
                
        return success_count > 0 