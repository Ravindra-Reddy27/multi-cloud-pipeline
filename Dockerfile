FROM python:3.9-slim

WORKDIR /app

# Copy requirements and install
COPY src/bridge/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/bridge/main.py .

# Run the application
CMD ["python", "main.py"]