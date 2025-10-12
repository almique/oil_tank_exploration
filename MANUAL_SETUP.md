# Manual Setup Guide

If you prefer to set up the application manually instead of using the automated setup script, follow these steps:

## 1. Create Backend Environment File

Create `backend/.env` with the following content:

```bash
# Database
DATABASE_URL=postgresql://postgres:postgres@postgres:5432/oil_tank_monitor

# Redis
REDIS_URL=redis://redis:6379

# NASA Earthdata credentials (sign up at https://urs.earthdata.nasa.gov/)
NASA_USERNAME=your_nasa_username
NASA_PASSWORD=your_nasa_password

# ESA Copernicus credentials (optional - alternative: https://dataspace.copernicus.eu/)
# Note: If scihub.copernicus.eu is not available, you can use the new Copernicus Data Space
COPERNICUS_USERNAME=your_copernicus_username
COPERNICUS_PASSWORD=your_copernicus_password

# API Keys (optional)
AIS_API_KEY=optional_ais_api_key
WEATHER_API_KEY=optional_weather_api_key

# Application settings
DEBUG=True
LOG_LEVEL=INFO
MAX_WORKERS=4
SECRET_KEY=your-secret-key-change-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Data directories
DATA_DIR=./data
SATELLITE_DATA_DIR=./data/satellite
PROCESSED_DATA_DIR=./data/processed
```

## 2. Create Frontend Environment File

Create `frontend/.env` with the following content:

```bash
REACT_APP_API_URL=http://localhost:8000
```

## 3. Create Data Directories

```bash
mkdir -p backend/data/satellite
mkdir -p backend/data/processed
```

## 4. Start Services

```bash
# Start database and Redis first
docker-compose up -d postgres redis

# Wait for database to be ready (about 10 seconds)
sleep 10

# Initialize database with sample data
docker-compose run --rm backend python init_db.py

# Start all services
docker-compose up -d
```

## 5. Access the Application

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Documentation: http://localhost:8000/docs

## 6. Configure Satellite Data Access (Optional but Recommended)

To enable satellite imagery fetching:

1. **Sign up for NASA Earthdata account (free):**
   - Go to: https://urs.earthdata.nasa.gov/
   - Create account and get username/password
   - Update `NASA_USERNAME` and `NASA_PASSWORD` in `backend/.env`

2. **Sign up for ESA Copernicus account (free):**
   - Primary option: https://dataspace.copernicus.eu/ (new platform)
   - Alternative: https://scihub.copernicus.eu/ (if available)
   - Create account and get username/password
   - Update `COPERNICUS_USERNAME` and `COPERNICUS_PASSWORD` in `backend/.env`

3. **Restart services to apply changes:**
   ```bash
   docker-compose restart
   ```

## Troubleshooting

If you encounter issues:

1. **Check if all services are running:**
   ```bash
   docker-compose ps
   ```

2. **View logs:**
   ```bash
   docker-compose logs -f
   ```

3. **Reset everything:**
   ```bash
   docker-compose down -v
   docker-compose up -d
   ```

4. **Reinitialize database:**
   ```bash
   docker-compose exec backend python init_db.py
   ```
