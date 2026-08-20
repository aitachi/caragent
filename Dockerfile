FROM python:3.12-slim

RUN pip install --no-cache-dir requests

COPY . /app
WORKDIR /workspace

ENV MINIAGENT_WORKDIR=/workspace
ENV PYTHONPATH=/app

# API key 必须运行时 -e MINIAGENT_API_KEY=... 传入，绝不写进镜像
ENTRYPOINT ["python", "-m", "miniagent"]
