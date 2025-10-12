# Troubleshooting Guide

## Common Issues and Solutions

### 1. Copernicus Website Not Available

**Problem:** `scihub.copernicus.eu` is not accessible or returns errors.

**Solution:** 
- The application now automatically tries the new Copernicus Data Space platform first
- Use the new platform: https://dataspace.copernicus.eu/
- The old platform (scihub.copernicus.eu) is being phased out
- If both fail, the app will continue working with NASA data only

**What the app does:**
1. First tries: `https://catalogue.dataspace.copernicus.eu/odata/v1`
2. Falls back to: `https://apihub.copernicus.eu/apihub`
3. If both fail: Continues with NASA Earthdata only

### 2. Frontend Module Errors (Layout.tsx)

**Problem:** "Cannot find module" errors in React components.

**Solutions:**

**A. Missing PostCSS Configuration:**
```bash
# The setup script now creates this automatically
# If missing, create frontend/postcss.config.js:
cat > frontend/postcss.config.js << EOF
module.exports = {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
}
EOF
```

**B. Missing Dependencies:**
```bash
cd frontend
npm install
```

**C. Clear Node Modules and Reinstall:**
```bash
cd frontend
rm -rf node_modules package-lock.json
npm install
```

**D. TypeScript Issues:**
```bash
cd frontend
npm install --save-dev @types/react @types/react-dom
```

### 3. Docker Issues

**Problem:** Docker services won't start.

**Solutions:**

**A. Check Docker Status:**
```bash
docker --version
docker-compose --version
docker ps
```

**B. Clean Docker State:**
```bash
docker-compose down -v
docker system prune -f
docker-compose up -d
```

**C. Check Logs:**
```bash
docker-compose logs -f
```

### 4. Database Connection Issues

**Problem:** Backend can't connect to PostgreSQL.

**Solutions:**

**A. Wait for Database:**
```bash
# Database takes time to initialize
docker-compose logs postgres
# Wait until you see "database system is ready to accept connections"
```

**B. Reset Database:**
```bash
docker-compose down -v
docker-compose up -d postgres
sleep 15
docker-compose run --rm backend python init_db.py
```

### 5. Port Already in Use

**Problem:** Ports 3000, 8000, or 5432 are already in use.

**Solutions:**

**A. Find and Kill Process:**
```bash
# Find what's using the port
lsof -i :3000
lsof -i :8000
lsof -i :5432

# Kill the process (replace PID)
kill -9 <PID>
```

**B. Use Different Ports:**
Edit `docker-compose.yml` to use different ports:
```yaml
services:
  frontend:
    ports:
      - "3001:3000"  # Use port 3001 instead
  backend:
    ports:
      - "8001:8000"  # Use port 8001 instead
```

### 6. Permission Errors

**Problem:** Permission denied errors when creating files.

**Solutions:**

```bash
# Fix permissions
sudo chown -R $USER:$USER /Users/anuranjan/Desktop/APPS/oil-tank-monitor
chmod -R 755 /Users/anuranjan/Desktop/APPS/oil-tank-monitor

# Create data directories
mkdir -p backend/data/satellite
mkdir -p backend/data/processed
```

### 7. Environment Variables Not Loading

**Problem:** App can't find environment variables.

**Solutions:**

**A. Check Environment Files Exist:**
```bash
ls -la backend/.env
ls -la frontend/.env
```

**B. Recreate Environment Files:**
```bash
# Run setup script again
./setup.sh

# Or create manually (see MANUAL_SETUP.md)
```

**C. Restart Services:**
```bash
docker-compose restart
```

### 8. Satellite Data Not Loading

**Problem:** No satellite imagery is being fetched.

**Solutions:**

**A. Check Credentials:**
- Verify NASA Earthdata account: https://urs.earthdata.nasa.gov/
- Verify Copernicus account: https://dataspace.copernicus.eu/
- Update `backend/.env` with correct credentials

**B. Check Worker Logs:**
```bash
docker-compose logs worker
```

**C. Manually Trigger Data Fetch:**
```bash
curl -X POST http://localhost:8000/api/process/fetch-imagery
```

### 9. Frontend Won't Load

**Problem:** React app shows blank page or errors.

**Solutions:**

**A. Check Backend Connection:**
```bash
curl http://localhost:8000/health
```

**B. Check Frontend Logs:**
```bash
docker-compose logs frontend
```

**C. Verify Environment:**
```bash
cat frontend/.env
# Should contain: REACT_APP_API_URL=http://localhost:8000
```

**D. Clear Browser Cache:**
- Hard refresh: Ctrl+Shift+R (or Cmd+Shift+R on Mac)
- Open developer tools and disable cache

### 10. API Errors

**Problem:** Backend API returns 500 errors.

**Solutions:**

**A. Check Backend Logs:**
```bash
docker-compose logs backend
```

**B. Check Database Connection:**
```bash
docker-compose exec backend python -c "from database import engine; print('DB OK' if engine else 'DB Error')"
```

**C. Reinitialize Database:**
```bash
docker-compose exec backend python init_db.py
```

## Quick Diagnostic Commands

```bash
# Test everything is working
./test-setup.sh

# Check all services
docker-compose ps

# View all logs
docker-compose logs -f

# Restart everything
docker-compose restart

# Nuclear option - reset everything
docker-compose down -v
docker system prune -f
./setup.sh
```

## Getting Help

1. **Check logs first:** `docker-compose logs -f`
2. **Run diagnostics:** `./test-setup.sh`
3. **Try the nuclear option:** Complete reset (see above)
4. **Check the API docs:** http://localhost:8000/docs
5. **Verify environment files:** Ensure `.env` files are properly configured

## Performance Tips

1. **Allocate more memory to Docker** (at least 4GB recommended)
2. **Close other applications** to free up ports and resources
3. **Use SSD storage** for better database performance
4. **Monitor resource usage:** `docker stats`
