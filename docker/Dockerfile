FROM python:3.11-slim

# Install system dependencies
# libnss-mdns: NSS module for mDNS hostname resolution (via getent)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libnss-mdns && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY ../requirements.txt /tmp/
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Create non-root user
RUN useradd -m -s /bin/bash -u 1001 app

# Create directories
RUN mkdir -p /var/log/enphase_collector && \
    mkdir -p /app/data && \
    chown -R app:app /var/log/enphase_collector && \
    chown -R app:app /app

# Copy application files (from parent directory)
COPY --chown=app:app ../src/enphase_collector.py /app/
COPY --chown=app:app ../src/enphase_token.py /app/
COPY --chown=app:app ../src/jaato_advisor.py /app/
COPY --chown=app:app ../src/jaato_agents_config.py /app/
COPY --chown=app:app ../src/external_apis.py /app/

# Copy entrypoint script (from docker directory)
COPY --chown=app:app docker/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Set working directory
WORKDIR /app

# Expose port for health checks if needed
EXPOSE 8080

# Use entrypoint script
ENTRYPOINT ["/app/entrypoint.sh"]

