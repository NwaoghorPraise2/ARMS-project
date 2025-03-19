FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY strategy_selector.py .
COPY taxonomy.py .

CMD ["python", "strategy_selector.py"]
