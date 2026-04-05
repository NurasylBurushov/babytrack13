FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONPATH=/app

RUN python3 -c "from router_auth import router; from router_nannies import router; print('✅ imports OK')"

CMD ["python3", "main.py"]
