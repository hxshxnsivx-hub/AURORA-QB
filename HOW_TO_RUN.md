# How to Run AURORA Assess

Complete guide to get the AURORA Assess system up and running on your local machine.

---

## Prerequisites

Before you begin, ensure you have these installed:

- **Docker Desktop** (includes Docker Compose)
  - Download: https://www.docker.com/products/docker-desktop
  - Version: 20.10+ recommended
  
- **Node.js** (for frontend)
  - Download: https://nodejs.org/
  - Version: 20.0+ required
  
- **Python** (for backend)
  - Download: https://www.python.org/downloads/
  - Version: 3.11+ required

- **Git** (to clone the repository)
  - Download: https://git-scm.com/downloads

---

## Quick Start (5 Minutes)

### Step 1: Start Docker Services

Open a terminal and run:

```bash
docker-compose up -d
```

This starts:
- PostgreSQL database (port 5432)
- Redis message queue (port 6379)
- MinIO file storage (ports 9000, 9001)

Wait 30 seconds for services to initialize.

### Step 2: Set Up Backend

Open a new terminal:

```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On Mac/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file
copy .env.example .env

# Run database migrations
alembic upgrade head

# Start backend server
uvicorn main:app --reload
```

Backend will be available at: **http://localhost:8000**

### Step 3: Set Up Frontend

Open another terminal:

```bash
cd frontend

# Install dependencies
npm install

# Copy environment file
# On Windows:
copy .env.example .env.local
# On Mac/Linux:
cp .env.example .env.local

# Start frontend server
npm run dev
```

Frontend will be available at: **http://localhost:3000**

---

## Detailed Setup Instructions

### 1. Clone the Repository

```bash
git clone <repository-url>
cd aurora-assess
```

### 2. Configure Environment Variables

#### Backend Configuration

Edit `backend/.env` with your settings:

```env
# Database (default values work with docker-compose)
DATABASE_URL=postgresql+asyncpg://aurora_user:aurora_password@localhost:5432/aurora_assess

# Redis (default values work with docker-compose)
REDIS_URL=redis://localhost:6379/0

# MinIO/S3 (default values work with docker-compose)
S3_ENDPOINT=http://localhost:9000
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=minioadmin
S3_BUCKET_NAME=aurora-assess

# JWT Secret (IMPORTANT: Change this!)
SECRET_KEY=your-secret-key-change-this-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# LLM API Keys (Get from OpenAI/Anthropic)
OPENAI_API_KEY=your-openai-api-key-here
ANTHROPIC_API_KEY=your-anthropic-api-key-here
LLM_MODEL=gpt-4
EMBEDDING_MODEL=text-embedding-3-small

# Application
ENVIRONMENT=development
LOG_LEVEL=INFO
CORS_ORIGINS=http://localhost:3000
```

#### Frontend Configuration

Edit `frontend/.env.local`:

```env
# API URL (should match backend)
NEXT_PUBLIC_API_URL=http://localhost:8000

# Application
NEXT_PUBLIC_APP_NAME=AURORA Assess
NEXT_PUBLIC_APP_VERSION=0.1.0
```

### 3. Initialize the Database

```bash
cd backend

# Activate virtual environment
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Mac/Linux

# Run migrations
alembic upgrade head

# (Optional) Create admin user
python -c "
from utils.security import hash_password
print('Admin password hash:', hash_password('admin123'))
"
```

### 4. Verify Services

Check that all Docker services are running:

```bash
docker-compose ps
```

You should see:
- `aurora-assess-db` (PostgreSQL) - Up
- `aurora-assess-redis` (Redis) - Up
- `aurora-assess-minio` (MinIO) - Up

---

## Accessing the Application

Once everything is running:

### Frontend (User Interface)
- URL: **http://localhost:3000**
- Default login: Create an account via registration

### Backend API
- URL: **http://localhost:8000**
- API Docs (Swagger): **http://localhost:8000/docs**
- API Docs (ReDoc): **http://localhost:8000/redoc**

### MinIO Console (File Storage)
- URL: **http://localhost:9001**
- Username: `minioadmin`
- Password: `minioadmin`

---

## Creating Your First User

### Option 1: Via Frontend (Recommended)

1. Go to http://localhost:3000
2. Click "Register"
3. Fill in:
   - Email: your-email@example.com
   - Password: SecurePassword123!
4. Click "Register"
5. You'll be automatically logged in

### Option 2: Via API

```bash
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "SecurePassword123!"
  }'
```

### Option 3: Create Admin User via Database

```bash
# Connect to PostgreSQL
docker-compose exec postgres psql -U aurora_user -d aurora_assess

# Insert admin user (password: admin123)
INSERT INTO users (email, password_hash, role, created_at, updated_at)
VALUES (
  'admin@aurora.com',
  '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYqVr/1jrYK',
  'admin',
  NOW(),
  NOW()
);

# Exit
\q
```

---

## Running Tests

### Backend Tests

```bash
cd backend

# Activate virtual environment
venv\Scripts\activate  # Windows

# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_auth.py

# Run property-based tests only
pytest -m property

# Run with coverage
pytest --cov=. --cov-report=html
```

### Frontend Tests (if available)

```bash
cd frontend

# Run tests
npm test

# Run with coverage
npm test -- --coverage
```

---

## Common Commands

### Docker Services

```bash
# Start services
docker-compose up -d

# Stop services
docker-compose down

# View logs
docker-compose logs -f

# Restart a specific service
docker-compose restart postgres

# Remove all data (WARNING: Deletes database!)
docker-compose down -v
```

### Backend

```bash
cd backend

# Start server
uvicorn main:app --reload

# Start on different port
uvicorn main:app --reload --port 8001

# Run migrations
alembic upgrade head

# Create new migration
alembic revision --autogenerate -m "description"

# Format code
black .

# Lint code
flake8
```

### Frontend

```bash
cd frontend

# Start development server
npm run dev

# Build for production
npm run build

# Start production server
npm start

# Lint code
npm run lint

# Format code
npx prettier --write .
```

---

## Troubleshooting

### Issue: Docker services won't start

**Solution:**
```bash
# Check if ports are already in use
netstat -ano | findstr :5432  # Windows
lsof -i :5432  # Mac/Linux

# Stop conflicting services or change ports in docker-compose.yml
```

### Issue: Backend can't connect to database

**Solution:**
```bash
# Check PostgreSQL is running
docker-compose ps postgres

# Test connection
docker-compose exec postgres psql -U aurora_user -d aurora_assess -c "SELECT 1;"

# Check DATABASE_URL in backend/.env matches docker-compose.yml
```

### Issue: Frontend can't connect to backend

**Solution:**
```bash
# Verify backend is running
curl http://localhost:8000/health

# Check NEXT_PUBLIC_API_URL in frontend/.env.local
# Should be: http://localhost:8000

# Restart frontend
cd frontend
npm run dev
```

### Issue: "Module not found" errors

**Solution:**
```bash
# Backend
cd backend
pip install -r requirements.txt

# Frontend
cd frontend
rm -rf node_modules package-lock.json
npm install
```

### Issue: Database migration errors

**Solution:**
```bash
cd backend

# Reset database (WARNING: Deletes all data!)
docker-compose down -v
docker-compose up -d
sleep 10
alembic upgrade head
```

### Issue: Permission denied on Windows

**Solution:**
```bash
# Run terminal as Administrator
# Or adjust Docker Desktop settings:
# Settings > Resources > File Sharing > Add project folder
```

---

## Development Workflow

### Making Changes

1. **Backend changes:**
   - Edit files in `backend/`
   - Server auto-reloads (if using `--reload`)
   - Run tests: `pytest`

2. **Frontend changes:**
   - Edit files in `frontend/`
   - Browser auto-refreshes
   - Check console for errors

3. **Database changes:**
   - Edit models in `backend/models/`
   - Create migration: `alembic revision --autogenerate -m "description"`
   - Apply migration: `alembic upgrade head`

### Testing Your Changes

```bash
# Backend
cd backend
pytest -v

# Frontend
cd frontend
npm run lint
npm run build  # Check for build errors
```

---

## Stopping the Application

### Stop Backend
Press `Ctrl+C` in the backend terminal

### Stop Frontend
Press `Ctrl+C` in the frontend terminal

### Stop Docker Services
```bash
docker-compose down
```

### Stop Everything and Clean Up
```bash
# Stop and remove containers, networks, volumes
docker-compose down -v

# Deactivate Python virtual environment
deactivate
```

---

## Next Steps

Once you have the application running:

1. **Explore the API**: Visit http://localhost:8000/docs
2. **Read the User Guide**: See `USER_GUIDE.md`
3. **Check the Documentation**: See `README.md` for architecture details
4. **Review the Spec**: See `.kiro/specs/aurora-assess/` for requirements and design

---

## Getting Help

- **API Documentation**: http://localhost:8000/docs
- **Project README**: `README.md`
- **User Guide**: `USER_GUIDE.md`
- **Deployment Guide**: `DEPLOYMENT_GUIDE.md`
- **Contributing Guide**: `CONTRIBUTING.md`

---

## System Requirements

### Minimum
- CPU: 2 cores
- RAM: 4GB
- Disk: 10GB free space
- OS: Windows 10+, macOS 10.15+, Ubuntu 20.04+

### Recommended
- CPU: 4 cores
- RAM: 8GB
- Disk: 20GB free space
- SSD storage

---

**You're all set! The AURORA Assess system should now be running on your machine.**
