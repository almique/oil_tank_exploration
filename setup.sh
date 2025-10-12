#!/bin/bash

# Oil Tank Monitor Setup Script
echo "🛢️  Setting up Oil Tank Monitor..."

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Create environment file for backend
echo "📝 Creating environment configuration..."

# Create data directories
mkdir -p backend/data/satellite
mkdir -p backend/data/processed

cat > backend/.env << EOF
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
EOF

# Create environment file for frontend
cat > frontend/.env << EOF
REACT_APP_API_URL=http://localhost:8000
EOF

echo "🐳 Starting services with Docker Compose..."
docker-compose up -d postgres redis

echo "⏳ Waiting for database to be ready..."
sleep 10

echo "🗄️  Initializing database..."
docker-compose run --rm backend python init_db.py

echo "🚀 Starting all services..."
docker-compose up -d

echo "✅ Setup complete!"
echo ""
echo "🌐 Application URLs:"
echo "   Frontend: http://localhost:3000"
echo "   Backend API: http://localhost:8000"
echo "   API Documentation: http://localhost:8000/docs"
echo ""
echo "📋 Next steps:"
echo "1. Sign up for free NASA Earthdata account: https://urs.earthdata.nasa.gov/"
echo "2. Sign up for ESA Copernicus account:"
echo "   - Primary: https://dataspace.copernicus.eu/ (new platform)"
echo "   - Alternative: https://scihub.copernicus.eu/ (if available)"
echo "3. Update backend/.env with your credentials"
echo "4. Restart services: docker-compose restart"
echo ""
echo "📖 View logs: docker-compose logs -f"
echo "🛑 Stop services: docker-compose down"
