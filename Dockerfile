FROM python:3.10-slim

WORKDIR /app

# 安装系统依赖 (减少不再需要的库)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件并安装 Python 包
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN pip install --no-cache-dir Flask==2.0.1 Werkzeug==2.0.1 schedule>=1.2.2

# 确保安装了 requests 库（用于 Turnstile 验证）
RUN pip install --no-cache-dir requests

# 复制应用程序代码
COPY . .

# 创建必要的目录
RUN mkdir -p data results

# 时区设置
ENV TZ=Asia/Shanghai

# 设置入口点
CMD ["/usr/local/bin/python", "-m", "informer.main"]