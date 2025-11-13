FROM python:3.11-slim

WORKDIR /app

# Install build deps required for some cryptography/bcrypt wheels
RUN apt-get update && apt-get install -y build-essential libffi-dev gcc libssl-dev && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p /app/data



EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
