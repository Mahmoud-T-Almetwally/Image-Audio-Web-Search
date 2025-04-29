# simple-front-end/Dockerfile

# Stage 1: Build React App
FROM node:22-alpine AS builder
WORKDIR /app

# Install dependencies
COPY package.json package-lock.json ./
# Use ci for cleaner installs if package-lock.json is reliable
RUN npm ci 

# Copy source code
COPY . .

# Set build-time environment variables if needed (e.g., API URL)
ARG REACT_APP_API_URL=http://localhost:8080/api/v1
ENV VITE_API_BASE_URL=$REACT_APP_API_URL 

# Build the application
RUN npm run build 

# Stage 2: Serve static files with Nginx
FROM nginx:1.27-alpine-slim
WORKDIR /usr/share/nginx/html

# Remove default nginx static assets
RUN rm -rf ./*

# Copy static assets from builder stage
COPY --from=builder /app/dist .

# Copy custom nginx configuration
COPY nginx.conf /etc/nginx/nginx.conf

# Expose port 80
EXPOSE 80

# Start nginx
CMD ["nginx", "-g", "daemon off;"]