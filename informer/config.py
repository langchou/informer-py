"""
配置模块 - 读取和解析配置文件
"""

import os
import yaml
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from loguru import logger


@dataclass
class LogConfig:
    file: str
    max_size: int
    max_backups: int
    max_age: int
    compress: bool
    level: str


@dataclass
class UserConfig:
    """用户配置类"""
    phone: str  # 用户手机号
    keywords: List[str]  # 用户关注的关键词
    always_at: bool = False  # 是否总是@该用户
    expire_date: str = ""  # 用户有效期，格式为"YYYY-MM-DD"，空字符串表示永久有效
    is_permanent: bool = False  # 是否永久有效，默认为True


@dataclass
class DingTalkRobot:
    name: str  # 机器人名称
    token: str  # 机器人令牌
    secret: str  # 机器人密钥
    enabled: bool = True  # 是否启用，默认为True
    receive_all: bool = True  # 当无关键词匹配时是否接收所有通知，默认为True
    users: List[UserConfig] = field(default_factory=list)  # 该机器人的用户配置列表
    user_key_words: Dict[str, List[str]] = field(default_factory=dict)  # 旧版兼容：用户关键词字典


@dataclass
class DingTalk:
    robots: List[DingTalkRobot]  # 多个钉钉机器人配置


@dataclass
class WaitTimeRange:
    min: int
    max: int


@dataclass
class LLMConfig:
    api_key: str
    base_url: str
    model: str  # 使用的模型名称
    provider: str = "openai"  # API提供商，支持"openai"和"siliconflow"


@dataclass
class Config:
    log_config: LogConfig
    dingtalk: DingTalk
    proxy_pool_api: str
    cookies: str
    wait_time_range: WaitTimeRange
    llm_config: Optional[LLMConfig] = None


def load_config(config_path="data/config.yaml") -> Config:
    """
    加载配置文件
    
    Args:
        config_path: 配置文件路径
        
    Returns:
        Config: 配置对象
    """
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"配置文件不存在: {config_path}")

    logger.info(f"正在加载配置文件: {config_path}")

    with open(config_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)

    log_config = LogConfig(
        file=data['log_config']['file'],
        max_size=data['log_config']['max_size'],
        max_backups=data['log_config']['max_backups'],
        max_age=data['log_config']['max_age'],
        compress=data['log_config']['compress'],
        level=data['log_config']['level']
    )
    logger.info(f"日志配置: 级别={log_config.level}, 文件={log_config.file}")

    # 处理钉钉机器人配置
    robots = []
    if 'dingtalk' in data:
        # 检查钉钉配置格式
        if 'robots' in data['dingtalk']:
            logger.info(f"检测到多机器人配置，共 {len(data['dingtalk']['robots'])} 个机器人")
        elif 'token' in data['dingtalk']:
            logger.info("检测到单机器人配置")
        else:
            logger.warning("钉钉配置格式不正确，请检查")
            
        # 兼容旧版配置（单个机器人）
        if 'token' in data['dingtalk'] and 'secret' in data['dingtalk']:
            # 获取全局用户关键词配置（旧版格式）
            global_keywords = data.get('user_key_words', {})
            logger.debug(f"单机器人模式: 找到 {len(global_keywords)} 个用户关键词配置")
            
            # 处理用户关键词（旧版格式转新版格式）
            users = []
            for phone, keywords in global_keywords.items():
                users.append(UserConfig(
                    phone=phone,
                    keywords=keywords,
                    always_at=False
                ))
            
            robots.append(DingTalkRobot(
                name="默认机器人",
        token=data['dingtalk']['token'],
                secret=data['dingtalk']['secret'],
                enabled=True,
                receive_all=True,  # 默认机器人接收所有通知
                users=users,
                user_key_words=global_keywords  # 保留旧版格式以兼容
            ))
            logger.info(f"已配置默认钉钉机器人，token长度: {len(data['dingtalk']['token'])}, secret长度: {len(data['dingtalk']['secret'])}")
            
        # 新版配置（多个机器人）
        elif 'robots' in data['dingtalk'] and isinstance(data['dingtalk']['robots'], list):
            # 获取全局用户关键词配置（用于向下兼容）
            global_keywords = data.get('user_key_words', {})
            
            for idx, robot_data in enumerate(data['dingtalk']['robots']):
                users = []
                robot_keywords = {}  # 收集关键词用于旧版兼容
                robot_name = robot_data.get('name', f'未命名机器人{idx+1}')
                robot_enabled = robot_data.get('enabled', True)
                robot_receive_all = robot_data.get('receive_all', True)
                
                logger.debug(f"配置钉钉机器人 [{robot_name}], enabled={robot_enabled}, receive_all={robot_receive_all}")
                
                # 检查token和secret是否有效
                if not robot_data.get('token') or not robot_data.get('secret'):
                    logger.warning(f"机器人 [{robot_name}] 缺少有效的token或secret，可能无法正常工作")
                
                # 处理新版配置格式
                if 'users' in robot_data:
                    logger.debug(f"机器人 [{robot_name}] 使用新版用户配置，有 {len(robot_data['users'])} 个用户")
                    for phone, user_data in robot_data['users'].items():
                        # 获取关键词列表
                        keywords = user_data.get('keywords', [])
                        always_at = user_data.get('always_at', False)
                        expire_date = user_data.get('expire_date', "")
                        is_permanent = user_data.get('is_permanent', True)
                        
                        # 将关键词保存到旧格式字典中，用于旧代码的兼容
                        robot_keywords[phone] = keywords
                        
                        users.append(UserConfig(
                            phone=phone,
                            keywords=keywords,
                            always_at=always_at,
                            expire_date=expire_date,
                            is_permanent=is_permanent
                        ))
                        logger.debug(f"机器人 [{robot_name}] 配置用户: {phone}, always_at={always_at}, 关键词数量={len(keywords)}")
                # 处理旧版配置格式
                elif 'user_key_words' in robot_data:
                    logger.debug(f"机器人 [{robot_name}] 使用旧版用户配置，有 {len(robot_data['user_key_words'])} 个用户")
                    for phone, keywords in robot_data['user_key_words'].items():
                        users.append(UserConfig(
                            phone=phone,
                            keywords=keywords,
                            always_at=False  # 旧版默认值
                        ))
                    robot_keywords = robot_data['user_key_words']
                # 如果都没有，使用全局配置（最大程度兼容）
                else:
                    if global_keywords:
                        logger.debug(f"机器人 [{robot_name}] 没有专用用户配置，使用全局配置，有 {len(global_keywords)} 个用户")
                        for phone, keywords in global_keywords.items():
                            users.append(UserConfig(
                                phone=phone,
                                keywords=keywords,
                                always_at=False
                            ))
                        robot_keywords = global_keywords
                    else:
                        logger.warning(f"机器人 [{robot_name}] 没有用户配置，也没有全局用户配置")
                
                robots.append(DingTalkRobot(
                    name=robot_name,
                    token=robot_data['token'],
                    secret=robot_data['secret'],
                    enabled=robot_enabled,
                    receive_all=robot_receive_all,
                    users=users,
                    user_key_words=robot_keywords  # 保留旧版格式以兼容
                ))
                logger.info(f"已配置钉钉机器人 [{robot_name}], enabled={robot_enabled}, receive_all={robot_receive_all}, token长度: {len(robot_data['token'])}, 用户数: {len(users)}")

    # 如果没有配置任何机器人，添加一个空配置（避免程序崩溃）
    if not robots:
        logger.warning("未找到有效的钉钉机器人配置，将使用空配置")
        robots.append(DingTalkRobot(
            name="未配置机器人", 
            token="", 
            secret="",
            enabled=False,
            receive_all=True,
            users=[],
            user_key_words={}
        ))

    dingtalk = DingTalk(robots=robots)
    logger.info(f"共配置了 {len(robots)} 个钉钉机器人")

    wait_time_range = WaitTimeRange(
        min=data['wait_time_range']['min'],
        max=data['wait_time_range']['max']
    )
    
    # 加载LLM配置（如果存在）
    llm_config = None
    if 'llm' in data:
        llm_config = LLMConfig(
            api_key=data['llm']['api_key'],
            base_url=data['llm']['base_url'],
            model=data['llm']['model'],
            provider=data['llm'].get('provider', 'openai')  # 默认为openai
        )
        logger.info(f"已配置LLM: 提供商={llm_config.provider}, 模型={llm_config.model}, API URL={llm_config.base_url}")

    return Config(
        log_config=log_config,
        dingtalk=dingtalk,
        proxy_pool_api=data['proxy_pool_api'],
        cookies=data['cookies'],
        wait_time_range=wait_time_range,
        llm_config=llm_config
    ) 