#!/bin/bash

echo "🧪 Testing Oil Tank Monitor setup..."

# Test if required commands exist
echo "📋 Checking prerequisites..."

if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed"
    exit 1
else
    echo "✅ Docker is installed"
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed"
    exit 1
else
    echo "✅ Docker Compose is installed"
fi

# Check if files exist
echo "📁 Checking project files..."

if [ ! -f "docker-compose.yml" ]; then
    echo "❌ docker-compose.yml not found"
    exit 1
else
    echo "✅ docker-compose.yml found"
fi

if [ ! -f "backend/requirements.txt" ]; then
    echo "❌ backend/requirements.txt not found"
    exit 1
else
    echo "✅ backend/requirements.txt found"
fi

if [ ! -f "frontend/package.json" ]; then
    echo "❌ frontend/package.json not found"
    exit 1
else
    echo "✅ frontend/package.json found"
fi

# Test Docker Compose syntax
echo "🐳 Testing Docker Compose configuration..."
if docker-compose config > /dev/null 2>&1; then
    echo "✅ Docker Compose configuration is valid"
else
    echo "❌ Docker Compose configuration has errors"
    docker-compose config
    exit 1
fi

# Check if environment files exist (after running setup)
if [ -f "backend/.env" ]; then
    echo "✅ Backend environment file exists"
else
    echo "⚠️  Backend environment file not found (run ./setup.sh first)"
fi

if [ -f "frontend/.env" ]; then
    echo "✅ Frontend environment file exists"
else
    echo "⚠️  Frontend environment file not found (run ./setup.sh first)"
fi

echo ""
echo "🎉 Setup test completed!"
echo ""
echo "Next steps:"
echo "1. Run ./setup.sh to initialize the application"
echo "2. Or follow MANUAL_SETUP.md for manual setup"
