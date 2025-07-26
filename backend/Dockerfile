# Use a slim Python 3.11 base image
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements file into the working directory
COPY requirements.txt ./

# Install Python dependencies from requirements.txt
# --no-cache-dir: Prevents pip from storing cached downloads, reducing image size
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application code into the working directory
COPY . .

# Command to run the application using uvicorn
# Changed from ["uvicorn", ...] to ["python", "-m", "uvicorn", ...]
# This ensures that uvicorn is executed as a Python module,
# which is more reliable and avoids potential PATH issues.
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
