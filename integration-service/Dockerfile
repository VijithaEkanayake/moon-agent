# Use the official Python image
FROM python:3.9-slim

# Set the working directory
WORKDIR /app

RUN apt-get update && apt-get install -y libpq-dev gcc

COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Expose the port
EXPOSE 8080

# Run the service
CMD ["python", "integration_service.py"]
