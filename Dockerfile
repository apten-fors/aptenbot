FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY utils/ /app/utils/
COPY managers/ /app/managers/
COPY clients/ /app/clients/
COPY handlers/ /app/handlers/
COPY main.py /app/main.py
COPY config.py /app/config.py

CMD ["python", "bot.py"]
