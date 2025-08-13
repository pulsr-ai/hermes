FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install poetry

# Copy only the files necessary for installing dependencies
COPY poetry.lock pyproject.toml /app/

# Install dependencies
RUN poetry config virtualenvs.create false && poetry install --only main --no-interaction --no-ansi --no-root

# Fix DNS library conflict if needed
RUN rm -rf /usr/local/lib/python*/site-packages/DNS && \
    pip install --force-reinstall dnspython

# Copy the rest of the application
COPY . /app/

# Create DKIM directory
RUN mkdir -p /app/dkim

# Expose ports
EXPOSE 8000 2525

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]