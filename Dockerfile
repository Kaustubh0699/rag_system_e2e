# On-prem deployment: Document UI (Flask) exposed on port 80 (HTTP, no TLS for now)
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application and config
COPY config.yaml .
COPY src/ src/

# Runtime dirs (app also creates these if missing)
RUN mkdir -p uploads sessions

# Expose app on port 80 (unsecured HTTP)
EXPOSE 80

ENV PORT=80
ENV FLASK_DEBUG=false

# Run Document UI on 0.0.0.0:80
CMD ["python", "-m", "src.document_ui.app"]
