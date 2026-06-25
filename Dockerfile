FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    nmap \
    iproute2 \
    iputils-ping \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir requests python-nmap

COPY scanner.py .

CMD ["python", "-u", "scanner.py"]
