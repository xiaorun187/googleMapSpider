# 使用官方 Python 3.10.11 镜像作为基础镜像
FROM python:3.10.11-slim

# 设置工作目录
WORKDIR /app

# 复制项目文件到容器
COPY . /app

# 升级 pip
RUN python -m pip install --upgrade pip

# 安装系统依赖（使用正确的包名 libglib2.0-0）
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    gnupg \
    unzip \
    curl \
    libxss1 \
    fonts-liberation \
    libnspr4 \
    libnss3 \
    libasound2 \
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxi6 \
    libxrandr2 \
    libxrender1 \
    libxtst6 \
    xdg-utils \
    libstdc++6 \
    libgcc-s1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# 下载并安装 Chrome 134.0.6998.165（linux64）
RUN wget -O /tmp/chrome-linux64.zip https://storage.googleapis.com/chrome-for-testing-public/134.0.6998.165/linux64/chrome-linux64.zip \
    && unzip /tmp/chrome-linux64.zip -d /opt/ \
    && rm /tmp/chrome-linux64.zip \
    && ln -s /opt/chrome-linux64/chrome /usr/bin/google-chrome \
    && google-chrome --version || { echo "Chrome failed to run"; exit 1; }

# 安装 ChromeDriver 134.0.6998.165（linux64）
RUN wget -O /tmp/chromedriver-linux64.zip https://storage.googleapis.com/chrome-for-testing-public/134.0.6998.165/linux64/chromedriver-linux64.zip \
    && unzip /tmp/chromedriver-linux64.zip -d /usr/local/bin/ \
    && mv /usr/local/bin/chromedriver-linux64/chromedriver /usr/local/bin/chromedriver \
    && rm -rf /usr/local/bin/chromedriver-linux64 \
    && rm /tmp/chromedriver-linux64.zip \
    && chmod +x /usr/local/bin/chromedriver \
    && ls -l /usr/local/bin/chromedriver || { echo "ChromeDriver not found"; exit 1; } \
    && /usr/local/bin/chromedriver --version || { echo "ChromeDriver failed to run"; exit 1; }

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 设置环境变量，避免 Chrome 崩溃
ENV CHROME_BIN=/usr/bin/google-chrome
ENV CHROMEDRIVER_PATH=/usr/local/bin/chromedriver

# 暴露 Flask 端口
EXPOSE 5000

# 运行 Flask 应用
CMD ["python", "google_maps_extractor.py"]