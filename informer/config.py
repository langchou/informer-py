"""
配置模块 - 读取和解析配置文件
"""

import os
import yaml
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class LogConfig:
    file: str
    max_size: int
    max_backups: int
    max_age: int
    compress: bool
    level: str


@dataclass
class DingTalk:
    token: str
    secret: str


@dataclass
class WaitTimeRange:
    min: int
    max: int


@dataclass
class LLMConfig:
    api_key: str
    base_url: str
    provider: str  # "openai" 或 "deepseek"
    model: str  # 使用的模型名称


@dataclass
class Config:
    log_config: LogConfig
    dingtalk: DingTalk
    proxy_pool_api: str
    cookies: str
    user_key_words: Dict[str, List[str]]
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

    dingtalk = DingTalk(
        token=data['dingtalk']['token'],
        secret=data['dingtalk']['secret']
    )

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
            provider=data['llm']['provider'],
            model=data['llm']['model']
        )

    return Config(
        log_config=log_config,
        dingtalk=dingtalk,
        proxy_pool_api=data['proxy_pool_api'],
        cookies=data['cookies'],
        user_key_words=data['user_key_words'],
        wait_time_range=wait_time_range,
        llm_config=llm_config
    ) 