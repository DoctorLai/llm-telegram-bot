FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot.py localization.py config.yaml LICENSE ./
COPY lang/ ./lang/

USER 10001:10001
CMD ["python", "bot.py"]
