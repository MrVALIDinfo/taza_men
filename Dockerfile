FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONIOENCODING=utf-8 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DATA_DIR=/app/data

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY bot ./bot
COPY webapp ./webapp
COPY assets ./assets

# База и фото жителей: на хостинге подключите сюда постоянный диск (volume)
RUN mkdir -p /app/data/photos

EXPOSE 8080
CMD ["python", "-m", "bot"]
