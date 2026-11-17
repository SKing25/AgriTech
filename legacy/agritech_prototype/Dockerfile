FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    APIMETEO_BASE_URL="https://api.open-meteo.com/v1/forecast" \
    APIMETEO_TIMEOUT_S="5" \
    VALVULAS_TIMEOUT_S="3" \
    VALVULAS_MAX_RETRIES="3"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY tests/ ./tests/
COPY GLOSSARY.md .

RUN python3 -m unittest discover -v -s tests

EXPOSE 8000

CMD ["python3", "-m", "unittest", "discover", "-v", "-s", "tests"]
