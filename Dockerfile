FROM tiangolo/uvicorn-gunicorn-fastapi:python3.10
USER root

# Set the working directory to /app
WORKDIR /app

# Copy the requirements file and install dependencies
COPY ./requirements.txt /app/

# Copy the app code into the container's /app directory
COPY ./app /app

# Installing dependencies
RUN apt update -y && apt upgrade -y
RUN apt install -y python3-pip
RUN #apt install python3-pip
RUN pip --version
RUN pip install --no-cache-dir -r requirements.txt

# Run the Uvicorn server
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
