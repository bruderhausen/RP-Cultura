FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PORT=8080 REFRESH_SECONDS=300 HISTORY_DAYS=7
EXPOSE 8080
CMD ["python","server/app.py"]
