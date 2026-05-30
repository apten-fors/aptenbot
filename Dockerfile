FROM python:3.14-slim

# uv: fast, reproducible installs from uv.lock
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

# Install dependencies first (cached layer), prod-only (no dev/test group).
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY utils/ /app/utils/
COPY managers/ /app/managers/
COPY clients/ /app/clients/
COPY middlewares/ /app/middlewares/
COPY routers/ /app/routers/
COPY models/ /app/models/
COPY states/ /app/states/
COPY services/ /app/services/
COPY bot.py /app/bot.py
COPY config.py /app/config.py
COPY providers.py /app/providers.py

CMD ["uv", "run", "--frozen", "--no-dev", "python", "bot.py"]
