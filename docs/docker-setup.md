# Docker Setup and Usage Guide

This guide explains how to use Docker to run the ConvoPilot application in development and production environments.

## Prerequisites

- Docker Engine 24.0.0 or later
- Docker Compose v2.20.0 or later
- Git (for cloning the repository)

## Quick Start

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/convopilot.git
   cd convopilot
   ```

2. Create environment files:
   ```bash
   cp backend/.env.example backend/.env
   cp frontend/.env.example frontend/.env
   ```

3. Edit the environment files with your configuration:
   - API keys (OpenAI, Google, Pinecone)
   - Database credentials
   - JWT secret key

4. Start the services:
   ```bash
   docker compose up -d
   ```

5. Access the application:
   - Frontend: http://localhost
   - API: http://localhost:5001

## Docker Services

### Backend Service
- Python Flask application
- Handles API requests and WebSocket connections
- Environment variables in `backend/.env`
- Ports: 5001

### Frontend Service
- React application served by Nginx
- Static files with API proxy configuration
- Environment variables in `frontend/.env`
- Ports: 80

### Database Service
- PostgreSQL 15
- Persistent data storage
- Environment variables:
  - POSTGRES_DB=convopilot
  - POSTGRES_USER=postgres
  - POSTGRES_PASSWORD=${DB_PASSWORD}
- Ports: 5432 (internal only)

### Redis Service
- Redis 7
- Used for caching and session management
- Persistence enabled
- Ports: 6379 (internal only)

## Development Setup

For development, you can use volume mounts to enable hot-reloading:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

This will:
- Mount source code directories
- Enable hot-reloading for frontend
- Use development server for backend
- Expose additional ports for debugging

## Production Deployment

For production:

1. Build optimized images:
   ```bash
   docker compose build --no-cache
   ```

2. Start services:
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
   ```

3. Scale services (if needed):
   ```bash
   docker compose up -d --scale backend=3
   ```

## Data Persistence

Data is persisted using Docker volumes:
- `postgres_data`: Database files
- `redis_data`: Cache and session data

Backup volumes regularly:
```bash
docker run --rm -v convopilot_postgres_data:/source -v /backup:/backup alpine tar czf /backup/postgres-backup.tar.gz -C /source .
```

## Monitoring

View logs:
```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f backend
```

Check service status:
```bash
docker compose ps
```

## Troubleshooting

1. **Database Connection Issues**
   ```bash
   docker compose exec backend flask db upgrade
   ```

2. **Redis Connection Issues**
   ```bash
   docker compose restart redis backend
   ```

3. **Frontend Not Loading**
   ```bash
   docker compose exec frontend nginx -t
   docker compose restart frontend
   ```

## Security Notes

1. Never commit `.env` files
2. Use secrets management in production
3. Regularly update base images
4. Follow least privilege principle
5. Enable Docker security features:
   ```yaml
   security_opt:
     - no-new-privileges:true
   ```

## Cleanup

Remove containers but keep data:
```bash
docker compose down
```

Remove everything including volumes:
```bash
docker compose down -v
```
