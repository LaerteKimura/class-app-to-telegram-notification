FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    playwright install chromium --with-deps

COPY *.py .

ENV CLASSAPP_DATA=/data

CMD ["python", "main.py", "watch"]
