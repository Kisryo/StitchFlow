# StitchFlow V2 - Deployment Guide

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Environment Setup](#environment-setup)
3. [Docker Deployment](#docker-deployment)
4. [Manual Deployment](#manual-deployment)
5. [Database Setup](#database-setup)
6. [Production Considerations](#production-considerations)
7. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required
- **Docker** (20.10+) and **Docker Compose** (2.0+)
- **Z.AI GLM API Key** - Get from [https://api.ilmu.ai](https://api.ilmu.ai) 

### Optional
- **Google Cloud Project** - For Sheets and Gmail integration
- **PostgreSQL** (13+) - For production database
- **Node.js** (18+) - For frontend development

---

## Environment Setup

### 1. Clone Repository
```bash
git clone <repository-url>
cd stitchflow-v2
```

### 2. Configure Environment Variables

#### Backend Configuration
```bash
cd backend
cp .env.example .env
```

Edit `.env` and set required values:
```env
# REQUIRED: Z.AI GLM API Key
ZHIPU_API_KEY=your_actual_api_key_here

# REQUIRED: Database URL
DATABASE_URL=sqlite:///./stitchflow.db  # For development
# DATABASE_URL=postgresql://user:pass@host:5432/stitchflow  # For production

# REQUIRED: Secret key (generate new one for production)
SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
```

#### Optional: Google APIs
If using Google Sheets or Gmail integration:
1. Create a Google Cloud Project
2. Enable Google Sheets API and Gmail API
3. Create OAuth2 credentials
4. Download credentials JSON files
5. Place in `backend/credentials/` directory
6. Update `.env`:
```env
GOOGLE_SHEETS_CREDENTIALS_FILE=./credentials/google_sheets_credentials.json
GMAIL_CREDENTIALS_FILE=./credentials/gmail_credentials.json
ENABLE_GOOGLE_SHEETS=True
ENABLE_GMAIL=True
```

---

## Docker Deployment

### Quick Start (Recommended)

```bash
# 1. Set environment variables
export ZHIPU_API_KEY=your_api_key_here

# 2. Start services
docker-compose up -d

# 3. Check status
docker-compose ps

# 4. View logs
docker-compose logs -f backend

# 5. Access application
# Backend API: http://localhost:8000
# API Docs: http://localhost:8000/docs
# Frontend: http://localhost:3000 (if enabled)
```

### Docker Commands

```bash
# Start services
docker-compose up -d

# Stop services
docker-compose down

# Restart services
docker-compose restart

# View logs
docker-compose logs -f [service_name]

# Rebuild containers
docker-compose build --no-cache

# Remove all data (WARNING: deletes database)
docker-compose down -v
```

### Docker Compose Configuration

The `docker-compose.yml` includes:
- **Backend**: FastAPI application on port 8000
- **Frontend**: React application on port 3000 (optional)
- **Volumes**: Persistent storage for uploads and database
- **Health checks**: Automatic service monitoring

---

## Manual Deployment

### Backend Deployment

#### 1. Install Dependencies
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: .\venv\Scripts\activate
pip install -r requirements.txt
```

#### 2. Set Up Database
```bash
# Run migrations
alembic upgrade head

# Seed policy rules (optional)
python seed_policy_rules.py
```

#### 3. Start Server
```bash
# Development
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Production (with Gunicorn)
gunicorn main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### Frontend Deployment

#### 1. Install Dependencies
```bash
cd frontend
npm install
```

#### 2. Build for Production
```bash
npm run build
```

#### 3. Serve with Nginx
```bash
# Copy build files to nginx
cp -r dist/* /var/www/stitchflow/

# Configure nginx (see frontend/nginx.conf)
sudo systemctl restart nginx
```

---

## Database Setup

### SQLite (Development)
```bash
# Automatic - no setup required
# Database file created at: backend/stitchflow.db
```

### PostgreSQL (Production)

#### 1. Install PostgreSQL
```bash
# Ubuntu/Debian
sudo apt-get install postgresql postgresql-contrib

# macOS
brew install postgresql
```

#### 2. Create Database
```bash
sudo -u postgres psql
```

```sql
CREATE DATABASE stitchflow;
CREATE USER stitchflow_user WITH PASSWORD 'secure_password';
GRANT ALL PRIVILEGES ON DATABASE stitchflow TO stitchflow_user;
\q
```

#### 3. Update Environment
```env
DATABASE_URL=postgresql://stitchflow_user:secure_password@localhost:5432/stitchflow
```

#### 4. Run Migrations
```bash
cd backend
alembic upgrade head
```

---

## Production Considerations

### Security

#### 1. Environment Variables
- **Never commit `.env` files** to version control
- Use **secrets management** (AWS Secrets Manager, HashiCorp Vault, etc.)
- **Rotate API keys** regularly
- Use **strong SECRET_KEY** (32+ characters)

#### 2. HTTPS/SSL
```bash
# Use reverse proxy (nginx, Caddy, Traefik)
# Example nginx config:
server {
    listen 443 ssl http2;
    server_name api.stitchflow.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

#### 3. Rate Limiting
```env
RATE_LIMIT_ENABLED=True
RATE_LIMIT_PER_MINUTE=60
```

### Performance

#### 1. Database Optimization
```sql
-- Add indexes for frequently queried fields
CREATE INDEX idx_workflows_state ON workflows(state);
CREATE INDEX idx_workflows_created_at ON workflows(created_at);
CREATE INDEX idx_audit_log_workflow_id ON audit_log(workflow_id);
```

#### 2. Caching
- Use **Redis** for session storage
- Cache GLM responses for identical inputs
- Enable **CDN** for frontend assets

#### 3. Scaling
```yaml
# docker-compose.yml - scale backend
services:
  backend:
    deploy:
      replicas: 4
      resources:
        limits:
          cpus: '2'
          memory: 2G
```

### Monitoring

#### 1. Health Checks
```bash
# Backend health
curl http://localhost:8000/health

# Docker health status
docker-compose ps
```

#### 2. Logging
```python
# Configure structured logging
LOG_LEVEL=INFO
LOG_FORMAT=json  # For log aggregation tools
```

#### 3. Metrics
- Use **Prometheus** + **Grafana** for metrics
- Monitor:
  - API response times
  - GLM API latency
  - Database query performance
  - Error rates
  - Workflow completion rates

### Backup

#### 1. Database Backup
```bash
# PostgreSQL
pg_dump -U stitchflow_user stitchflow > backup_$(date +%Y%m%d).sql

# SQLite
cp stitchflow.db backup_$(date +%Y%m%d).db
```

#### 2. File Storage Backup
```bash
# Backup uploads directory
tar -czf uploads_backup_$(date +%Y%m%d).tar.gz backend/uploads/
```

#### 3. Automated Backups
```bash
# Cron job (daily at 2 AM)
0 2 * * * /path/to/backup_script.sh
```

---

## Troubleshooting

### Common Issues

#### 1. Database Connection Error
```
Error: connection to server at "localhost", port 5432 failed
```
**Solution**:
- Check DATABASE_URL in `.env`
- Verify PostgreSQL is running: `sudo systemctl status postgresql`
- For SQLite, ensure directory is writable

#### 2. GLM API Error
```
Error: 401 Unauthorized - Invalid API key
```
**Solution**:
- Verify ZHIPU_API_KEY in `.env`
- Check API key is valid at provider dashboard
- Ensure GLM_BASE_URL is correct

#### 3. File Upload Error
```
Error: File size exceeds maximum allowed size
```
**Solution**:
- Increase MAX_FILE_SIZE_MB in `.env`
- Check disk space: `df -h`
- Verify UPLOAD_DIR exists and is writable

#### 4. Docker Container Won't Start
```bash
# Check logs
docker-compose logs backend

# Common fixes:
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

#### 5. Port Already in Use
```
Error: bind: address already in use
```
**Solution**:
```bash
# Find process using port
lsof -i :8000  # Linux/Mac
netstat -ano | findstr :8000  # Windows

# Kill process or change port in docker-compose.yml
```

### Debug Mode

Enable detailed logging:
```env
DEBUG=True
LOG_LEVEL=DEBUG
```

View detailed logs:
```bash
# Docker
docker-compose logs -f --tail=100 backend

# Manual
tail -f backend/logs/stitchflow.log
```

### Getting Help

1. Check logs: `docker-compose logs -f`
2. Review API docs: `http://localhost:8000/docs`
3. Check health endpoint: `http://localhost:8000/health`
4. Review environment variables: `docker-compose config`

---

## Quick Reference

### Environment Variables
| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| ZHIPU_API_KEY | Yes | - | Z.AI GLM API key |
| DATABASE_URL | Yes | sqlite:///./stitchflow.db | Database connection string |
| SECRET_KEY | Yes | - | Application secret key |
| GLM_MODEL | No | ilmu-glm-5.1 | GLM model to use |
| MAX_FILE_SIZE_MB | No | 50 | Maximum upload size |
| LOG_LEVEL | No | INFO | Logging level |

### Ports
- **8000**: Backend API
- **3000**: Frontend (if enabled)
- **5432**: PostgreSQL (if used)

### Directories
- `backend/uploads/`: Uploaded documents
- `backend/logs/`: Application logs
- `backend/alembic/`: Database migrations
- `backend/credentials/`: Google API credentials

---

## Next Steps

1. ✅ Set up environment variables
2. ✅ Start services with Docker Compose
3. ✅ Access API docs at http://localhost:8000/docs
4. ✅ Test with sample document upload
5. ✅ Configure Google APIs (optional)
6. ✅ Set up monitoring and backups
7. ✅ Deploy to production

For more information, see:
- [API Documentation](http://localhost:8000/docs)
- [Testing Guide](backend/TESTING_GUIDE.md)
- [Interactive Testing](backend/INTERACTIVE_TESTING.md)
- [Quick Start](backend/QUICK_START.md)
