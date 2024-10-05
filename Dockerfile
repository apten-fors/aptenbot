FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY main.py .
COPY config.py .
COPY utils/ .
COPY managers/ .
COPY clients/ .
COPY handlers/ .

CMD ["python", "main.py"]
