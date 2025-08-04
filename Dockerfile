# Use a lightweight official Python image as the base
FROM python:3.9-slim-bullseye

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install -r requirements.txt

# Update package lists, install curl, and clean up apt cache to keep image small
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Copy the rest of your application code into the container
COPY . .

# Expose the port your Flask app will run on (e.g., 5000)
EXPOSE 5000
