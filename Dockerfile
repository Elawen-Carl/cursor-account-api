# 使用官方 Python 3.12 镜像作为基础镜像
FROM python:3.12-slim

# 创建 sources.list 文件并更改为阿里云的 Debian 镜像源
RUN echo "deb http://mirrors.aliyun.com/debian/ bullseye main" > /etc/apt/sources.list \
    && echo "deb-src http://mirrors.aliyun.com/debian/ bullseye main" >> /etc/apt/sources.list

# 安装必要的依赖
RUN apt-get update && apt-get install -y \
    wget \
    gnupg2 \
    && wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y --fix-missing google-chrome-stable \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /app

# 复制依赖文件
COPY requirements.txt .

# 安装依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目文件
COPY . .

# 设置 Chrome 浏览器的环境变量
ENV CHROME_BIN=/usr/bin/google-chrome

# 暴露应用运行的端口
EXPOSE 8000

# 启动 FastAPI 应用
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000", "--reload"] 