# AURORA Assess

Multi-agent orchestration system for intelligent exam generation, automated evaluation, and personalized learning recommendations.

## Overview

AURORA Assess extends the AURORA Learn adaptive learning platform by providing:
- Intelligent exam paper generation from question banks
- Automated evaluation using hybrid rule-based and LLM-powered grading
- Performance analysis and weakness detection
- Personalized learning roadmap updates

## Architecture

- **Frontend**: Next.js 14 with TypeScript, Tailwind CSS, and shadcn/ui
- **Backend**: FastAPI with Python 3.11+
- **Database**: PostgreSQL 15+ with pgvector extension
- **Storage**: MinIO (S3-compatible)
- **Message Queue**: Redis
- **LLM Integration**: OpenAI GPT-4 / Anthropic Claude

## Prerequisites

- Docker and Docker Compose
- Node.js 20+ (for local frontend development)
- Python 3.11+ (for local backend development)

## Quick Start

### 1. Clone the repository

```bash
git clone <repository-url>
cd aurora-assess
```

### 2. Set up environment variables

```bash
# Backend
cp backend/.env.example backend/.env
# Edit backend/.env with your configuration

# Frontend
cp frontend/.env.example frontend/.env.local
# Edit frontend/.env.local with your configuration
```

### 3. Start services with Docker Compose

```bash
docker-compose up -d
```

This will start:
- PostgreSQL with pgvector (port 5432)
- Redis (port 6379)
- MinIO (ports 9000, 9001)

### 4. Run backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

Backend will be available at http://localhost:8000

### 5. Run frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend will be available at http://localhost:3000

## Project Structure

```
aurora-assess/
├── frontend/              # Next.js frontend application
│   ├── app/              # App router pages
│   ├── components/       # React components
│   └── lib/              # Utilities and helpers
├── backend/              # FastAPI backend application
│   ├── agents/           # Multi-agent system
│   ├── api/              # API endpoints
│   ├── models/           # Database models
│   ├── services/         # Business logic
│   └── utils/            # Utilities
├── .kiro/                # Kiro specifications
│   └── specs/
│       └── aurora-assess/
│           ├── requirements.md
│           ├── design.md
│           └── tasks.md
└── docker-compose.yml    # Docker services configuration
```

## Development

### Backend Development

```bash
cd backend

# Run tests
pytest

# Run with auto-reload
uvicorn main:app --reload

# Format code
black .

# Lint code
flake8
```

### Frontend Development

```bash
cd frontend

# Run development server
npm run dev

# Build for production
npm run build

# Run linter
npm run lint

# Format code
npx prettier --write .
```

## API Documentation

Once the backend is running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Testing

### Property-Based Testing

The system uses property-based testing to verify 85 correctness properties:

```bash
# Run all tests
pytest

# Run property tests only
pytest -m property

# Run with verbose output
pytest -v
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development guidelines.

## License

[Your License Here]

## Support

For issues and questions, please open an issue on GitHub.
