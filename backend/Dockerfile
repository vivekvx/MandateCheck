FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    fastapi==0.139.0 \
    "uvicorn[standard]"==0.50.2 \
    sqlalchemy==2.0.51 \
    alembic==1.18.5 \
    psycopg2-binary==2.9.12 \
    pydantic==2.13.4 \
    slowapi==0.1.10

COPY . .

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
