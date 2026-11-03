# Only the guest contains Playwright. Host API credentials never enter this image.
FROM mcr.microsoft.com/playwright/python:v1.61.0-noble
RUN python -m pip install --no-cache-dir playwright==1.61.0 \
 && groupadd -g 10001 cua && useradd -u 10001 -g 10001 -m -d /home/cua cua
WORKDIR /app
COPY wolf_cua /app/wolf_cua
ENV PYTHONPATH=/app HOME=/home/cua
USER 10001:10001
CMD ["python", "-u", "-m", "wolf_cua.worker"]
