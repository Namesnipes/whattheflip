# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies that might be needed (e.g., for Pillow)
# RUN apt-get update && apt-get install -y --no-install-recommends some-package && rm -rf /var/lib/apt/lists/*

# Copy the dependencies file to the working directory
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
# Use --no-cache-dir to reduce image size
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the backend application code into the container
COPY . .

# The command to run the application is specified in docker-compose.yml
# But you could add a default command here for running the container directly:
# CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
