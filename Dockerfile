# CSQAQ Glove Quant Scenario API
# Build: docker build -t csqaq-scenario .
# Run:   docker run -p 8000:8000 -e CSQAQ_API_TOKEN=<token> csqaq-scenario

FROM python:3.10-slim

WORKDIR /app

# Install system dependencies required by numerical Python packages.
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy the project and install Python dependencies.
COPY pyproject.toml ./
COPY src ./src
COPY config ./config
COPY frontend ./frontend
COPY run_scenario_server.py ./

RUN pip install --no-cache-dir -e .

# Do not declare VOLUMEs; runtime state is ephemeral or injected via env vars.
EXPOSE 8000

ENV CSQAQ_HOST=0.0.0.0
ENV CSQAQ_PORT=8000
ENV CSQAQ_CACHE_PATH=/tmp/csqaq_cache
ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "uvicorn", "run_scenario_server:app", "--host", "0.0.0.0", "--port", "8000"]
