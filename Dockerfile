# Dockerfile
FROM python:3.9-slim

# working directory
WORKDIR /app

# copy files
COPY . /app

# install dependencies
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 5000

CMD ["python", "app.py"]
