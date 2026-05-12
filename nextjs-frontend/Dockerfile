FROM node:20-bookworm

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

RUN chown -R node:node /app && chmod +x /app/start.sh /app/start.prod.sh

## Switch to the non-root user
USER node

EXPOSE 3000

# Start the application
CMD ["./start.sh"]