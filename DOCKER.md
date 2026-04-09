# Docker Setup Guide

This project includes Docker configuration for easy isolation, portability, and resource management.

## Quick Start

### 1. Build and Run

```bash
# Build the Docker image
docker-compose build

# Start all services (app + Neo4j)
docker-compose up
```

### 2. Run Analysis

```bash
# Run a single analysis command
docker-compose exec app python main.py --targets data/targets.csv --output data/results.json

# Run with Neo4j export
docker-compose exec app python main.py --targets data/targets.csv --neo4j

# Clear and reload Neo4j database
docker-compose exec app python main.py --targets data/targets.csv --neo4j --clear-db

# Run tests
docker-compose exec app pytest tests/ -v

# Interactive shell
docker-compose exec app bash
```

### 3. Stop and Cleanup

```bash
# Stop all containers (keeps data)
docker-compose down

# Stop and remove volumes (clears memory/data)
docker-compose down -v

# Remove everything including images
docker-compose down -v --rmi all
```

## Configuration

### Environment Variables

Create or update `.env` file:

```env
OPENCORPORATES_API_TOKEN=your_token_here
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_secure_password
```

### Container Settings

Edit `docker-compose.yml` to adjust:

- **Memory limits**: Add `deploy.resources.limits.memory` under each service
- **CPU limits**: Add `deploy.resources.limits.cpus`
- **Neo4j heap**: Modify `NEO4J_server_memory_heap_max_size`
- **Volume mounts**: Change paths for data directories

Example with resource limits:

```yaml
services:
  app:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          cpus: '1'
          memory: 2G
```

## Common Tasks

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f app
docker-compose logs -f neo4j

# Last 100 lines
docker-compose logs --tail=100
```

### Inspect Data

```bash
# List containers
docker-compose ps

# View container disk usage
docker system df

# Access Neo4j Browser
# Open browser to: http://localhost:7474
# Default credentials: neo4j / (your NEO4J_PASSWORD)
```

### Performance Tuning

**For large datasets (10,000+ companies):**

```bash
# Increase available memory
docker-compose exec neo4j neo4j-admin set-default-admin neo4j <new-password>
```

Update in `docker-compose.yml`:
```yaml
environment:
  - NEO4J_server_memory_heap_max_size=4g
  - NEO4J_server_memory_pagecache_size=2g
```

Then restart:
```bash
docker-compose restart neo4j
```

**For CPU-bound analysis:**

Add to docker-compose.yml app service:
```yaml
deploy:
  resources:
    limits:
      cpus: '4'
```

## Troubleshooting

### Container fails to start

```bash
# Check logs
docker-compose logs app

# Rebuild without cache
docker-compose build --no-cache

# Start in foreground to see errors
docker-compose up --no-build
```

### Neo4j connection errors

```bash
# Check Neo4j is running
docker-compose ps

# Wait for Neo4j to be ready (can take 30s)
docker-compose exec neo4j cypher-shell -u neo4j -p <password> "RETURN 1"

# Verify connectivity from app
docker-compose exec app python -c "from neo4j import GraphDatabase; print('OK')"
```

### Out of memory errors

```bash
# Check memory usage
docker stats

# Reduce Neo4j heap in docker-compose.yml, then:
docker-compose restart neo4j
```

### Clear everything and start fresh

```bash
docker-compose down -v --rmi all
docker system prune
docker-compose build
docker-compose up
```

## Production Deployment

For production use:

1. **Use `.env.production`** with secure credentials
2. **Add resource limits** to prevent memory exhaustion
3. **Enable persistent volumes** for Neo4j data
4. **Use named volumes** instead of bind mounts
5. **Run on Docker Swarm or Kubernetes** for orchestration
6. **Enable logging driver** (json-file, splunk, etc.)

Example production setup:

```bash
# Use production environment
cp .env.production .env
docker-compose -f docker-compose.yml up -d
```

## File Structure in Container

```
/app/
├── main.py
├── config.py
├── requirements.txt
├── analysis/
├── ingestion/
├── export/
├── data/          # Mounted from ./data
├── tests/
└── .env           # Mounted from ./.env (read-only)
```

Data directories are mounted as volumes, so changes persist between container restarts.
