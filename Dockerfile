# 使用轻量级的 Python 3.10 镜像
FROM python:3.10-slim

# 设置工作目录
WORKDIR /app

# 设置时区为墨尔本
ENV TZ=Australia/Melbourne
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 先复制依赖文件并安装，利用 Docker 缓存加速构建
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目的所有代码和资源
COPY . .

# 运行主程序
CMD ["python", "src/main.py"]