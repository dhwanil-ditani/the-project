FROM python:3.12-slim

# Set environment variables to prevent Python from writing .pyc files
# and to keep stdout/stderr unbuffered.
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install uv globally
RUN pip install uv

# Set working directory
WORKDIR /app

# Copy dependency files first to leverage Docker cache
COPY pyproject.toml uv.lock ./

# Install dependencies in a frozen environment without dev dependencies
RUN uv sync --frozen --no-dev

# Copy the rest of the application code
COPY src/ ./src/
COPY alembic/ ./alembic/
COPY main.py alembic.ini ./

# Expose port
EXPOSE 8000

# Default command to run the FastAPI application
CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
