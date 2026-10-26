# Render Free runs this single image. The public server requires Supabase
# credentials at startup; local SQLite and Meterless files are not durable here.
FROM node:24-bookworm-slim

# Debian Bookworm supplies Python 3.11. The Meterless bridge uses Node's
# built-in TypeScript type transform and has no npm dependencies.
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 ca-certificates \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LENS_HOST=0.0.0.0 \
    LENS_PUBLIC_MODE=1

WORKDIR /app
COPY app.py accounts.py lens_core.py lens_investigator.py ./
COPY web/ ./web/
COPY examples/ ./examples/
COPY zetaris/ ./zetaris/
COPY meterless/ ./meterless/

# The official Node image includes an unprivileged `node` user.
USER node

EXPOSE 10000
CMD ["python3", "app.py"]
