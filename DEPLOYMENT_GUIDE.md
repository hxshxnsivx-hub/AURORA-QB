# Phase 1 Deployment & Demonstration Guide

This guide provides step-by-step instructions for completing the optional Phase 1 tasks:
- **Task 7.7**: Deploy Phase 1 to staging environment
- **Task 7.8**: Demonstrate working authentication and basic CRUD

---

## Task 7.7: Deploy Phase 1 to Staging Environment

### Prerequisites

Before starting deployment, ensure you have:

- [ ] Cloud provider account (AWS, GCP, Azure, or DigitalOcean)
- [ ] Domain name (optional but recommended)
- [ ] SSL certificate (Let's Encrypt recommended)
- [ ] Git repository access
- [ ] Environment variables documented

### Option A: Deploy to AWS (Recommended for Production)

#### Step 1: Set Up AWS Infrastructure

**1.1 Create EC2 Instance**
```bash
# Instance specifications:
- Type: t3.medium (2 vCPU, 4GB RAM minimum)
- OS: Ubuntu 22.04 LTS
- Storage: 30GB SSD
- Security Group: Allow ports 22, 80, 443, 8000, 3000
```

**1.2 Connect to EC2 Instance**
```bash
ssh -i your-key.pem ubuntu@your-ec2-ip
```

**1.3 Install Docker and Docker Compose**
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add user to docker group
sudo usermod -aG docker $USER

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Verify installation
docker --version
docker-compose --version

# Log out and back in for group changes to take effect
exit
```

#### Step 2: Clone Repository and Configure

**2.1 Clone Repository**
```bash
# Reconnect to EC2
ssh -i your-key.pem ubuntu@your-ec2-ip

# Clone repository
git clone https://github.com/your-org/aurora-assess.git
cd aurora-assess
```

**2.2 Create Production Environment Files**
```bash
# Backend environment
cat > backend/.env << EOF
# Database
DATABASE_URL=postgresql://aurora_user:CHANGE_THIS_PASSWORD@postgres:5432/aurora_assess
POSTGRES_USER=aurora_user
POSTGRES_PASSWORD=CHANGE_THIS_PASSWORD
POSTGRES_DB=aurora_assess

# JWT Secret (generate with: openssl rand -hex 32)
JWT_SECRET_KEY=$(openssl rand -hex 32)
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# MinIO/S3
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=CHANGE_THIS_ACCESS_KEY
MINIO_SECRET_KEY=CHANGE_THIS_SECRET_KEY
MINIO_BUCKET_NAME=aurora-assess
MINIO_SECURE=false

# Redis
REDIS_URL=redis://redis:6379/0

# Environment
ENVIRONMENT=staging
LOG_LEVEL=INFO
EOF

# Frontend environment
cat > frontend/.env.local << EOF
NEXT_PUBLIC_API_URL=http://your-ec2-ip:8000
NEXT_PUBLIC_ENVIRONMENT=staging
EOF
```

**2.3 Update Docker Compose for Production**
```bash
# Create production docker-compose override
cat > docker-compose.prod.yml << EOF
version: '3.8'

services:
  postgres:
    restart: always
    volumes:
      - postgres_data_prod:/var/lib/postgresql/data

  redis:
    restart: always
    volumes:
      - redis_data_prod:/data

  minio:
    restart: always
    volumes:
      - minio_data_prod:/data

volumes:
  postgres_data_prod:
  redis_data_prod:
  minio_data_prod:
EOF
```

#### Step 3: Deploy Application

**3.1 Start Services**
```bash
# Start all services
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f
```

**3.2 Run Database Migrations**
```bash
# Access backend container
docker-compose exec backend bash

# Run migrations
cd /app
alembic upgrade head

# Exit container
exit
```

**3.3 Create Admin User**
```bash
# Create a Python script to add admin user
cat > create_admin.py << 'EOF'
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from models.user import User, UserRole
from utils.security import hash_password
import os

async def create_admin():
    DATABASE_URL = os.getenv("DATABASE_URL")
    engine = create_async_engine(DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        # Check if admin exists
        admin = await session.execute(
            "SELECT * FROM users WHERE email = 'admin@aurora-assess.com'"
        )
        if admin.first():
            print("Admin user already exists")
            return
        
        # Create admin user
        admin_user = User(
            email="admin@aurora-assess.com",
            password_hash=hash_password("ChangeThisPassword123!"),
            role=UserRole.ADMIN
        )
        session.add(admin_user)
        await session.commit()
        print("Admin user created successfully")
        print("Email: admin@aurora-assess.com")
        print("Password: ChangeThisPassword123!")

if __name__ == "__main__":
    asyncio.run(create_admin())
EOF

# Copy script to backend container and run
docker cp create_admin.py aurora-assess-backend:/app/
docker-compose exec backend python create_admin.py
```

#### Step 4: Configure Nginx Reverse Proxy (Optional but Recommended)

**4.1 Install Nginx**
```bash
sudo apt install nginx -y
```

**4.2 Configure Nginx**
```bash
sudo nano /etc/nginx/sites-available/aurora-assess
```

**Add this configuration:**
```nginx
server {
    listen 80;
    server_name your-domain.com;  # Replace with your domain or IP

    # Frontend
    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }

    # Backend API
    location /api {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # API Documentation
    location /docs {
        proxy_pass http://localhost:8000;
    }

    location /redoc {
        proxy_pass http://localhost:8000;
    }
}
```

**4.3 Enable Site and Restart Nginx**
```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/aurora-assess /etc/nginx/sites-enabled/

# Test configuration
sudo nginx -t

# Restart Nginx
sudo systemctl restart nginx
```

#### Step 5: Set Up SSL with Let's Encrypt (Optional)

```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx -y

# Obtain SSL certificate
sudo certbot --nginx -d your-domain.com

# Auto-renewal is configured automatically
# Test renewal
sudo certbot renew --dry-run
```

#### Step 6: Verify Deployment

**6.1 Check Services**
```bash
# Check all containers are running
docker-compose ps

# Check logs for errors
docker-compose logs --tail=50

# Test database connection
docker-compose exec postgres psql -U aurora_user -d aurora_assess -c "SELECT COUNT(*) FROM users;"
```

**6.2 Test Endpoints**
```bash
# Health check
curl http://your-ec2-ip:8000/health

# API documentation
curl http://your-ec2-ip:8000/docs

# Frontend
curl http://your-ec2-ip:3000
```

---

### Option B: Deploy to DigitalOcean (Easier, Recommended for Staging)

#### Step 1: Create Droplet

1. Log in to DigitalOcean
2. Click **Create** → **Droplets**
3. Choose:
   - **Image**: Ubuntu 22.04 LTS
   - **Plan**: Basic ($12/month - 2GB RAM, 1 vCPU)
   - **Datacenter**: Choose closest to your location
   - **Authentication**: SSH Key (recommended) or Password
4. Click **Create Droplet**

#### Step 2: Connect and Set Up

```bash
# Connect to droplet
ssh root@your-droplet-ip

# Follow steps from AWS Option A, starting from Step 1.3
```

---

### Option C: Deploy to Heroku (Quickest for Demo)

#### Step 1: Install Heroku CLI

```bash
# Install Heroku CLI
curl https://cli-assets.heroku.com/install.sh | sh

# Login
heroku login
```

#### Step 2: Create Heroku Apps

```bash
# Create backend app
heroku create aurora-assess-backend

# Create frontend app
heroku create aurora-assess-frontend

# Add PostgreSQL
heroku addons:create heroku-postgresql:mini -a aurora-assess-backend

# Add Redis
heroku addons:create heroku-redis:mini -a aurora-assess-backend
```

#### Step 3: Configure and Deploy Backend

```bash
cd backend

# Set environment variables
heroku config:set JWT_SECRET_KEY=$(openssl rand -hex 32) -a aurora-assess-backend
heroku config:set ENVIRONMENT=staging -a aurora-assess-backend

# Create Procfile
cat > Procfile << EOF
web: uvicorn main:app --host 0.0.0.0 --port \$PORT
release: alembic upgrade head
EOF

# Deploy
git add .
git commit -m "Configure for Heroku"
git push heroku main
```

#### Step 4: Configure and Deploy Frontend

```bash
cd ../frontend

# Set environment variables
heroku config:set NEXT_PUBLIC_API_URL=https://aurora-assess-backend.herokuapp.com -a aurora-assess-frontend

# Deploy
git push heroku main
```

---

## Task 7.8: Demonstrate Working Authentication and Basic CRUD

### Demonstration Checklist

Use this checklist to prepare and conduct your demonstration:

#### Pre-Demonstration Setup (30 minutes before)

- [ ] **Verify all services are running**
  ```bash
  docker-compose ps
  # All services should show "Up"
  ```

- [ ] **Check logs for errors**
  ```bash
  docker-compose logs --tail=100 | grep -i error
  # Should show no critical errors
  ```

- [ ] **Create test accounts**
  - Admin: admin@demo.com / DemoPass123!
  - Faculty: faculty@demo.com / DemoPass123!
  - Student: student@demo.com / DemoPass123!

- [ ] **Prepare sample data**
  - 1 Subject: "Computer Science"
  - 2 Units: "Programming Basics", "Data Structures"
  - 3 Topics per unit
  - 2 Concepts per topic

- [ ] **Test all demo flows**
  - Run through each scenario once
  - Note any issues
  - Have backup plan ready

- [ ] **Prepare presentation materials**
  - Architecture diagram
  - Feature list
  - Screenshots (optional)

#### Demonstration Script (30-45 minutes)

### Part 1: Introduction (5 minutes)

**Script:**
```
"Welcome to the AURORA Assess Phase 1 demonstration. Today I'll show you:

1. The authentication system with role-based access control
2. CRUD operations for academic content
3. File storage integration
4. The foundation we've built for Phase 2

Let me start by showing you the architecture..."

[Show architecture diagram or docker-compose ps output]
```

### Part 2: Authentication Demo (10 minutes)

**Scenario 1: User Registration**

1. Open browser to `http://your-url:3000`
2. Click **Register**
3. Enter:
   - Email: `demo-student@example.com`
   - Password: `SecurePass123!`
4. Click **Register**
5. **Point out**: 
   - Automatic login after registration
   - JWT token stored in localStorage
   - Redirect to dashboard
   - Default role is "Student"

**Scenario 2: Role-Based Access Control**

1. Navigate to **Subjects** (should see empty list or read-only view)
2. Try to create a subject (should fail or button not visible)
3. **Point out**: "Students cannot create subjects"
4. Logout
5. Login as Faculty: `faculty@demo.com` / `DemoPass123!`
6. Navigate to **Subjects**
7. **Point out**: "Faculty can now create subjects"

**Scenario 3: Admin Capabilities**

1. Logout
2. Login as Admin: `admin@demo.com` / `DemoPass123!`
3. Navigate to **Users**
4. Show user list
5. Click on the demo student
6. Change role to "Faculty"
7. **Point out**: "Admin can manage all users and roles"

### Part 3: CRUD Operations Demo (15 minutes)

**Scenario 4: Creating Academic Hierarchy**

Login as Faculty and demonstrate:

1. **Create Subject**
   - Click **Subjects** → **Create Subject**
   - Name: "Data Structures"
   - Code: "CS201"
   - Description: "Advanced data structures and algorithms"
   - Click **Create**
   - **Point out**: Subject appears in list

2. **Create Unit**
   - Click on "Data Structures" subject
   - Click **Add Unit**
   - Name: "Arrays and Linked Lists"
   - Order: 1
   - Click **Create**
   - **Point out**: Unit appears under subject

3. **Create Topic**
   - Click on "Arrays and Linked Lists" unit
   - Click **Add Topic**
   - Name: "Dynamic Arrays"
   - Description: "Resizable array implementation"
   - Click **Create**
   - **Point out**: Topic appears under unit

4. **Create Concept**
   - Click on "Dynamic Arrays" topic
   - Click **Add Concept**
   - Name: "Array Resizing"
   - Description: "Doubling strategy for array growth"
   - Importance: 0.8
   - Click **Create**
   - **Point out**: Complete hierarchy created

**Scenario 5: Reading and Filtering**

1. Navigate back to **Subjects**
2. Show list of all subjects
3. Click on a subject to view details
4. Show units filtered by subject
5. Show topics filtered by unit
6. **Point out**: "Hierarchical filtering works correctly"

**Scenario 6: Updating Content**

1. Click **Edit** on a subject
2. Change description
3. Click **Save**
4. **Point out**: "Changes are persisted"

**Scenario 7: Deleting Content**

1. Create a test concept
2. Click **Delete** on the test concept
3. Confirm deletion
4. **Point out**: "Soft delete - can be recovered if needed"

### Part 4: API Documentation Demo (5 minutes)

1. Navigate to `http://your-url:8000/docs`
2. Show Swagger UI
3. Expand **Authentication** endpoints
4. Show request/response schemas
5. Try out an endpoint:
   - Click **GET /api/subjects**
   - Click **Try it out**
   - Click **Execute**
   - Show response
6. **Point out**: "All endpoints are documented with examples"

### Part 5: Technical Deep Dive (5 minutes)

**Show the following in terminal:**

1. **Database Structure**
   ```bash
   docker-compose exec postgres psql -U aurora_user -d aurora_assess
   \dt
   SELECT COUNT(*) FROM users;
   SELECT COUNT(*) FROM subjects;
   \q
   ```

2. **Logs**
   ```bash
   docker-compose logs backend --tail=20
   ```
   **Point out**: Structured JSON logging

3. **File Storage**
   ```bash
   docker-compose exec minio ls /data/aurora-assess/
   ```
   **Point out**: Files stored in MinIO

### Part 6: Testing Demo (3 minutes)

```bash
cd backend

# Show test structure
ls tests/

# Run tests
pytest -v

# Show test results
```

**Point out**:
- 33 unit tests
- 13 property tests
- 8 integration tests
- All passing

### Part 7: Q&A and Next Steps (5 minutes)

**Prepared Answers:**

**Q: "What about security?"**
A: "We have bcrypt password hashing, JWT tokens with expiration, role-based access control, and SQL injection prevention through ORM."

**Q: "How does it scale?"**
A: "Currently designed for 50+ concurrent users. Phase 2 will add Redis queue for async processing and caching for better performance."

**Q: "What's next in Phase 2?"**
A: "Phase 2 adds the intelligence layer: LLM integration, question bank parsing, automated paper generation, and AI-powered grading."

**Q: "Can I try it myself?"**
A: "Yes! Here are the credentials and URL. The user guide is available at /docs."

---

## Post-Demonstration Tasks

### Gather Feedback

Create a feedback form with these questions:

1. Was the authentication system clear and easy to use? (1-5)
2. Were the CRUD operations intuitive? (1-5)
3. What features would you like to see in Phase 2?
4. Any bugs or issues noticed?
5. Overall impression? (1-5)

### Document Issues

Create an issues list:

```markdown
# Phase 1 Demonstration Feedback

## Date: [DATE]
## Attendees: [LIST]

### Positive Feedback
- [Item 1]
- [Item 2]

### Issues Found
- [ ] [Issue 1] - Priority: High/Medium/Low
- [ ] [Issue 2] - Priority: High/Medium/Low

### Feature Requests
- [Request 1]
- [Request 2]

### Action Items
- [ ] [Action 1] - Assigned to: [NAME] - Due: [DATE]
- [ ] [Action 2] - Assigned to: [NAME] - Due: [DATE]
```

---

## Troubleshooting Common Issues

### Issue: Services won't start

**Solution:**
```bash
# Check logs
docker-compose logs

# Restart services
docker-compose down
docker-compose up -d

# Check disk space
df -h
```

### Issue: Database connection fails

**Solution:**
```bash
# Check PostgreSQL is running
docker-compose ps postgres

# Check connection
docker-compose exec postgres psql -U aurora_user -d aurora_assess -c "SELECT 1;"

# Reset database if needed
docker-compose down -v
docker-compose up -d
```

### Issue: Frontend can't connect to backend

**Solution:**
```bash
# Check NEXT_PUBLIC_API_URL in frontend/.env.local
cat frontend/.env.local

# Should match backend URL
# Update if needed and rebuild
docker-compose restart frontend
```

### Issue: Authentication fails

**Solution:**
```bash
# Check JWT_SECRET_KEY is set
docker-compose exec backend env | grep JWT

# Verify user exists
docker-compose exec postgres psql -U aurora_user -d aurora_assess -c "SELECT email, role FROM users;"
```

---

## Rollback Procedure

If deployment fails:

```bash
# Stop all services
docker-compose down

# Restore from backup (if available)
docker-compose exec postgres pg_restore -U aurora_user -d aurora_assess /backup/aurora_assess.dump

# Or start fresh
docker-compose down -v
git checkout main
docker-compose up -d
```

---

## Success Criteria

Mark these as complete after demonstration:

- [ ] All services running without errors
- [ ] Authentication working (register, login, logout)
- [ ] Role-based access control demonstrated
- [ ] CRUD operations working for all entities
- [ ] API documentation accessible
- [ ] Tests passing
- [ ] Positive feedback from stakeholders
- [ ] No critical bugs found
- [ ] Deployment documented
- [ ] Feedback collected

---

## Completion Checklist

After successful deployment and demonstration:

- [ ] Update tasks.md to mark 7.7 and 7.8 as complete
- [ ] Update PHASE1_COMPLETE.md to 100%
- [ ] Document deployment URL and credentials
- [ ] Create backup of production database
- [ ] Set up monitoring (optional)
- [ ] Schedule Phase 2 kickoff meeting
- [ ] Archive demonstration recording (if recorded)
- [ ] Send thank you email to attendees

---

## Next Steps: Phase 2 Preparation

Before starting Phase 2:

1. **Review Phase 1 feedback** - Address any critical issues
2. **Set up LLM API access** - OpenAI/Anthropic account
3. **Prepare test question banks** - Sample PDFs for parsing
4. **Review Phase 2 requirements** - Understand agent architecture
5. **Allocate resources** - Ensure team availability

---

**Estimated Time:**
- Deployment (Option A - AWS): 2-3 hours
- Deployment (Option B - DigitalOcean): 1-2 hours  
- Deployment (Option C - Heroku): 30-60 minutes
- Demonstration preparation: 30 minutes
- Demonstration: 30-45 minutes
- Post-demo tasks: 30 minutes

**Total: 3-5 hours for complete deployment and demonstration**

---

*This guide ensures a smooth deployment and professional demonstration of Phase 1 capabilities.*
