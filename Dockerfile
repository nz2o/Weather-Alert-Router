FROM python:3.14.3-slim
WORKDIR /app

# Use prebuilt binary wheels (psycopg[binary], psycopg-binary) so build tools are not required.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app

COPY app/docker-entrypoint.sh /app/app/docker-entrypoint.sh
RUN chmod +x /app/app/docker-entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["sh", "/app/app/docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
