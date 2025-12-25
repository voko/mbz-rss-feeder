
# Base stage for installing dependencies
FROM python:3.10-slim AS base
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Builder stage for production dependencies
FROM base AS builder
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Default config and data paths
ENV FEEDS_FILE_PATH=/var/mbz-rss-feeder/feeds.yml
ENV CONFIG_FILE_PATH=/etc/mbz-rss-feeder.yml
ENV CACHE_DIR=/var/mbz-rss-feeder/cache
ENV LOG_FILE=/var/log/mbz-rss-feeder.log
ENV LOG_LEVEL=INFO

RUN mkdir -p /var/mbz-rss-feeder/cache \
    && touch /var/log/mbz-rss-feeder.log \
    && touch /var/mbz-rss-feeder/feeds.yml \
    && touch /etc/mbz-rss-feeder.yml

# Test stage
FROM builder AS test
COPY mzb_rss_service/tests/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python -m pytest"]

# Final production stage
FROM base AS final
COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY mzb_rss_service mzb_rss_service
COPY VERSION .

EXPOSE 8080
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "mzb_rss_service.main:app"]
