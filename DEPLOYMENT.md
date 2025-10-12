# Oil Tank Monitor - Deployment Guide

## Quick Start

1. **Run the setup script:**
   ```bash
   cd /Users/anuranjan/Desktop/APPS/oil-tank-monitor
   ./setup.sh
   ```

2. **Access the application:**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Documentation: http://localhost:8000/docs

## Manual Setup

### Prerequisites

- Docker and Docker Compose
- NASA Earthdata account (free): https://urs.earthdata.nasa.gov/
- ESA Copernicus account (free): https://scihub.copernicus.eu/

### Step-by-Step Setup

1. **Clone and navigate to the project:**
   ```bash
   cd /Users/anuranjan/Desktop/APPS/oil-tank-monitor
   ```

2. **Configure environment variables:**
   ```bash
   # Backend configuration
   cp backend/.env.example backend/.env
   # Edit backend/.env with your NASA and Copernicus credentials
   
   # Frontend configuration
   echo "REACT_APP_API_URL=http://localhost:8000" > frontend/.env
   ```

3. **Start the services:**
   ```bash
   docker-compose up -d
   ```

4. **Initialize the database:**
   ```bash
   docker-compose exec backend python init_db.py
   ```

## Production Deployment

### Environment Variables

Update the following for production:

```bash
# Backend (.env)
DEBUG=False
SECRET_KEY=your-secure-secret-key
DATABASE_URL=postgresql://user:password@host:port/database
REDIS_URL=redis://host:port

# Frontend (.env)
REACT_APP_API_URL=https://your-api-domain.com
```

### Docker Compose Production

```yaml
# docker-compose.prod.yml
version: '3.8'
services:
  backend:
    build: ./backend
    environment:
      - DEBUG=False
    volumes:
      - ./data:/app/data
    restart: unless-stopped

  frontend:
    build: ./frontend
    ports:
      - "80:3000"
    restart: unless-stopped

  postgres:
    image: postgis/postgis:15-3.3
    environment:
      POSTGRES_DB: oil_tank_monitor
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    restart: unless-stopped
```

### SSL/HTTPS Setup

Use a reverse proxy like Nginx or Traefik:

```nginx
# nginx.conf
server {
    listen 443 ssl;
    server_name your-domain.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    
    location /api/ {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## Monitoring and Maintenance

### Health Checks

- Backend health: `curl http://localhost:8000/health`
- Database connection: Check logs with `docker-compose logs postgres`
- Redis connection: Check logs with `docker-compose logs redis`

### Logs

```bash
# View all logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f backend
docker-compose logs -f frontend
docker-compose logs -f worker
```

### Backup

```bash
# Database backup
docker-compose exec postgres pg_dump -U postgres oil_tank_monitor > backup.sql

# Restore database
docker-compose exec -T postgres psql -U postgres oil_tank_monitor < backup.sql
```

### Scaling

```bash
# Scale workers
docker-compose up -d --scale worker=3

# Scale backend
docker-compose up -d --scale backend=2
```

## Troubleshooting

### Common Issues

1. **Database connection errors:**
   - Check if PostgreSQL is running: `docker-compose ps postgres`
   - Verify connection string in `.env`

2. **Satellite data not loading:**
   - Verify NASA/Copernicus credentials in `.env`
   - Check worker logs: `docker-compose logs worker`

3. **Frontend not loading:**
   - Check if backend is accessible: `curl http://localhost:8000/health`
   - Verify REACT_APP_API_URL in frontend/.env

4. **Permission errors:**
   - Ensure data directories are writable: `chmod -R 755 data/`

### Performance Optimization

1. **Database optimization:**
   - Add indexes for frequently queried columns
   - Use connection pooling
   - Regular VACUUM and ANALYZE

2. **Redis optimization:**
   - Configure memory limits
   - Use appropriate eviction policies

3. **Worker optimization:**
   - Adjust CELERY_WORKER_CONCURRENCY
   - Monitor task queue length

## API Usage Examples

### Get all sites
```bash
curl http://localhost:8000/api/sites
```

### Get site analysis
```bash
curl http://localhost:8000/api/sites/1/analysis
```

### Trigger satellite data processing
```bash
curl -X POST http://localhost:8000/api/process/satellite-data \
  -H "Content-Type: application/json" \
  -d '{"site_id": 1}'
```

### Fetch latest imagery
```bash
curl -X POST http://localhost:8000/api/process/fetch-imagery \
  -H "Content-Type: application/json" \
  -d '{"site_id": 1}'
```

## Development

### Local Development Setup

1. **Backend development:**
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   uvicorn main:app --reload
   ```

2. **Frontend development:**
   ```bash
   cd frontend
   npm install
   npm start
   ```

3. **Database migrations:**
   ```bash
   cd backend
   alembic revision --autogenerate -m "Description"
   alembic upgrade head
   ```

### Testing

```bash
# Backend tests
cd backend
python -m pytest

# Frontend tests
cd frontend
npm test
```

## Support

For issues and questions:
1. Check the logs first
2. Review this deployment guide
3. Check the API documentation at http://localhost:8000/docs
4. Ensure all credentials are correctly configured
