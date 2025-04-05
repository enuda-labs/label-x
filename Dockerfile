FROM python:3.10-slim
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY requirements.txt .

RUN pip install --upgrade pip
RUN pip install -r requirements.txt
RUN pip install honcho


COPY . .

EXPOSE 8080

CMD ["sh", "-c", "honcho start web worker"]