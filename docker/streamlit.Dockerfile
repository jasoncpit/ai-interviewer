FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src

WORKDIR /app

COPY pyproject.toml README.md /app/
COPY src /app/src

RUN pip install --upgrade pip \
    && pip install --no-cache-dir .

COPY . /app

EXPOSE 8501

CMD ["streamlit", "run", "src/streamlit_app.py", "--server.port", "8501", "--server.address", "0.0.0.0"]
