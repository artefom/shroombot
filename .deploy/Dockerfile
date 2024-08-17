FROM python:3.11-slim-bookworm

WORKDIR /app

# Install the required dependencies for TDLib
RUN apt-get update && apt-get install -y \
    build-essential \
    libssl3 \
    libssl-dev \
    zlib1g-dev \
    clang \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install --no-input "poetry==1.8.2"

# Install packages in a cache-friendly way
COPY poetry.lock pyproject.toml ./

RUN POETRY_VIRTUALENVS_CREATE=false poetry install --no-root

# Copy package source code
COPY ./shroombot ./shroombot

# Install package
RUN pip install --no-deps .

# Run application
# Use entrypoint and 'cmd' so that SIGTERM and other signals are propagated.
#
# When using entrypoint script use 'exec <command>' to propagate signals
ENTRYPOINT [ "shroombot" ]
CMD ["mapping.bin"]
