FROM python:3.10-slim

WORKDIR /app

# 安装系统依赖 (包括 Playwright 运行浏览器所需的依赖)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    # Playwright 依赖项 (通常由 playwright install --with-deps 处理，但预先安装一些常见的可能更好)
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libatspi2.0-0 \
    libx11-6 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    libxtst6 \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件并安装 Python 包
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 安装 Playwright 浏览器和依赖项
# --with-deps 会自动安装缺失的系统依赖项
RUN playwright install --with-deps chromium

# 复制应用程序代码
COPY . .

# 创建必要的目录
RUN mkdir -p data results

# 时区设置
ENV TZ=Asia/Shanghai

# 设置入口点
CMD ["python", "-m", "informer.main"] 