FROM python:3.11-slim

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 创建必要的目录
RUN mkdir -p data results

# 时区设置
ENV TZ=Asia/Shanghai

# 设置入口点
CMD ["python", "-m", "informer.main"] 