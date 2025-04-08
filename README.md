# Chiphell 二手区监控 - Python版本

Python实现的Chiphell论坛二手交易区监控工具，支持关键词匹配、钉钉通知等功能。

## 功能特点

- 🔍 实时监控二手交易区新帖
- 🎯 支持多关键词匹配
- 📱 钉钉机器人通知，支持@指定用户
- 🔄 智能代理池管理
- 🗃️ SQLite 本地持久化
- 🚫 智能去重和过滤

## 安装方法

### 方法一：Docker（推荐）

最简单的方式是使用Docker运行此应用：

```bash
# 1. 克隆仓库
git clone https://github.com/langchou/informer-py.git
cd informer-py

# 2. 配置
cp data/config_example.yaml data/config.yaml
# 编辑配置文件
nano data/config.yaml

# 3. 启动服务
docker-compose up -d
```

#### Docker相关命令

```bash
# 查看日志
docker logs -f informer

# 停止服务
docker-compose down

# 更新镜像
docker-compose pull
docker-compose up -d

# 重启服务
docker-compose restart
```

### 方法二：本地安装

#### 1. 克隆仓库

```bash
git clone https://github.com/langchou/informer-py.git
cd informer-py
```

#### 2. 安装依赖

```bash
pip install -r requirements.txt
```

或者使用开发模式安装：

```bash
pip install -e .
```

## 配置说明

### 1. 创建配置文件

```bash
mkdir -p data
cp data/config_example.yaml data/config.yaml
```

### 2. 编辑 `data/config.yaml` 配置文件

```yaml
# 日志配置
log_config:
  file: "logs/app.log"    # 日志文件路径
  max_size: 10            # 每个日志文件的最大大小（MB）
  max_backups: 5          # 保留的旧日志文件数量
  max_age: 30             # 保留日志文件的最大天数
  compress: true          # 是否压缩旧日志
  level: "INFO"           # 日志级别：DEBUG, INFO, WARNING, ERROR

# 钉钉机器人配置
dingtalk:
  token: "your_dingtalk_token"  # 钉钉机器人的访问令牌
  secret: "your_dingtalk_secret"  # 钉钉机器人的签名密钥

# 代理池API
proxy_pool_api: ""  # 代理池API地址，留空表示不使用代理

# Cookies设置
cookies: "your_cookies_string"  # Cookies字符串，用于网站访问认证

# 用户关键词配置
user_key_words:
  "13812345678":  # 手机号码，用于@通知
    - "RTX 4090"  # 关键词
    - "3090"
    - "显卡"

# 等待时间范围（秒）
wait_time_range:
  min: 30  # 最小等待时间（秒）
  max: 60  # 最大等待时间（秒）
```

## 本地运行方法

```bash
python -m informer.main
```

## 开发说明

### 项目结构

```
informer-py/
├── informer/          # 主程序包
│   ├── __init__.py    # 包初始化文件
│   ├── config.py      # 配置管理
│   ├── database.py    # 数据库操作
│   ├── fetcher.py     # 网页内容获取
│   ├── logger.py      # 日志管理
│   ├── main.py        # 主程序入口
│   ├── monitor.py     # 监控器
│   ├── notifier.py    # 通知管理
├── tests/             # 测试目录
├── README.md          # 说明文档
├── requirements.txt   # 依赖列表
├── setup.py           # 安装脚本
└── docker-compose.yml # Docker Compose配置
```

## 注意事项

1. Cookie 有效期
   - 定期更新 cookies 以确保正常访问
   - cookies 失效会导致监控失败

2. 代理使用
   - 建议在被限制访问时才启用代理
   - 确保代理池稳定可用

3. 系统资源
   - 注意日志文件大小
   - 定期清理数据库历史数据

## 免责声明

本工具仅用于学习和研究目的，请勿用于非法用途。使用本工具所产生的任何后果由使用者自行承担。 