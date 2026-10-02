FROM python:3.11-bookworm

USER root
RUN apt-get update && apt-get install -y --no-install-recommends bash ca-certificates curl git unzip python3 python3-venv build-essential \
    && rm -rf /var/lib/apt/lists/*
RUN useradd --create-home --uid 1001 --shell /bin/bash dev
RUN mkdir -p /workspace && chown dev:dev /workspace
WORKDIR /workspace
USER dev

# Source is mounted at runtime. Credentials and personal data never enter image layers.
CMD ["sleep", "infinity"]
