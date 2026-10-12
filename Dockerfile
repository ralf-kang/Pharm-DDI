FROM python:3.11-alpine

WORKDIR /app

RUN apk add --no-cache git curl tzdata

ENV TZ=Asia/Seoul
ENV PORT=3003
ENV HOST=0.0.0.0
ENV PYTHONUNBUFFERED=1

COPY . /app

EXPOSE 3003

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://127.0.0.1:3003/api/stats || exit 1

CMD ["python3", "server.py"]
