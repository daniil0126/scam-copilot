# Backend plus the web copy of the panel, for a hosted copy (Render and the like). Build context: the repository root.
#   docker build -f backend/Dockerfile -t scamcopilot .
# The PayPal Agent Toolkit (@paypal/mcp) is a Node program, so Node is copied in next to Python.

FROM node:22-slim AS mcp
WORKDIR /mcp
COPY backend/mcp/package.json backend/mcp/package-lock.json ./
RUN npm ci --ignore-scripts --omit=dev

# The panel as a web page, served by the backend under /app/ (backend/app/web.py).
FROM node:22-slim AS web
WORKDIR /w
COPY package.json package-lock.json ./
RUN npm ci --ignore-scripts
COPY tsconfig.json tsconfig.app.json tsconfig.node.json vite.web.config.ts ./
COPY public ./public
COPY src ./src
RUN npm run build:web

FROM python:3.13-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY --from=mcp /usr/local/bin/node /usr/local/bin/node
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
COPY backend/mcp/package.json backend/mcp/package-lock.json ./mcp/
COPY --from=mcp /mcp/node_modules ./mcp/node_modules
COPY --from=web /w/dist-web ./web
RUN useradd --create-home app && chown -R app:app /app
USER app
EXPOSE 8000
# The host sets PORT; 8000 is the local default. The SQLite file is rebuilt from PayPal's last 30 days on a fresh start.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
