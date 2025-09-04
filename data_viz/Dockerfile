# Stage 1: Build Environment
FROM python:3.10.12-slim as builder

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl build-essential && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Install Poetry and explicitly add its install directory to the PATH
ENV PATH="/root/.local/bin:$PATH"
RUN curl -sSL https://install.python-poetry.org | python3 -

# We explicitly tell Poetry to create the virtualenv inside the project directory.
ENV POETRY_VIRTUALENVS_IN_PROJECT=true

COPY pyproject.toml poetry.lock ./
COPY src ./src

# We use `poetry install` with `--only main` to install dependencies.
# The project's dependencies are now installed and the project itself is installed.
RUN poetry install --only main


# Stage 2: Production Environment
FROM python:3.10.12-slim

# Set the working directory for the application
WORKDIR /app

# Copy the entire virtual environment from the builder stage.
COPY --from=builder /app/.venv /app/.venv

# Set the PATH to include Poetry's executables for `poetry run`
ENV PATH="/app/.venv/bin:$PATH"

# Set the PYTHONPATH to include your source code
ENV PYTHONPATH=/app/src

# Copy your source code into the container
COPY src ./src

# The command to run the application will be defined in docker-compose.yml