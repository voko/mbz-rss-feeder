
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
# persistence directory/volume is mounted to /var/mbz-rss-feeder
ENV FEEDS_FILE_PATH=/var/mbz-rss-feeder/feeds.yml
ENV CONFIG_FILE_PATH=/var/mbz-rss-feeder/etc/mbz-rss-feeder.yml
ENV CACHE_DIR=/var/mbz-rss-feeder/cache
ENV LOG_FILE=/var/mbz-rss-feeder/log/mbz-rss-feeder.log
ENV LOG_LEVEL=INFO
ENV MBZ_LOG_LEVEL=WARNING

RUN mkdir -p /var/mbz-rss-feeder/cache /var/mbz-rss-feeder/log /var/mbz-rss-feeder/etc \
    && touch /var/mbz-rss-feeder/log/mbz-rss-feeder.log \
    && touch /var/mbz-rss-feeder/feeds.yml \
    && touch /var/mbz-rss-feeder/etc/mbz-rss-feeder.yml

# Test stage
FROM builder AS test
COPY mbz_rss_service/tests/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python -m pytest"]

# Final production stage
FROM base AS final
COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY mbz_rss_service mbz_rss_service
COPY VERSION .

EXPOSE 8080
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "mbz_rss_service.main:app"]
