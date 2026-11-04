# Node 20 is end-of-life and missed the 2026-10-21 security release.
# 22.23.4 is the patched 22 line. Python and Postgres are unchanged.
FROM node:22.23.4-bookworm

# Set the working directory
WORKDIR /app

# Install pnpm globally
RUN npm install -g pnpm

# Copy package files and install dependencies
COPY package*.json pnpm-lock.yaml ./

# Install dependencies using the checked-in lockfile
RUN pnpm install --frozen-lockfile

# Copy the rest of your application code
COPY . .

# Windows checkout may leave CRLF; strip so `#!/bin/sh` resolves in Linux containers.
RUN sed -i 's/\r$//' /app/start.sh /app/start.prod.sh

RUN chown -R node:node /app && chmod +x /app/start.sh /app/start.prod.sh

## Switch to the non-root user
USER node

EXPOSE 3000

# Start the application
CMD ["./start.sh"]