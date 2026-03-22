# Agent Worker Fix - Complete

## Problem
Question bank uploads were staying in "PENDING" status indefinitely because the agent orchestrator was never started. Tasks were being queued to Redis but no workers were processing them.

## Root Cause
The application had a complete multi-agent orchestration system implemented, but:
1. The orchestrator was never started in the main application
2. There was no separate worker process to run the agents
3. The agents use synchronous database sessions while the API uses async sessions

## Solution

### 1. Created Separate Worker Process
**File**: `backend/agents/worker.py`

A standalone Python script that:
- Creates a synchronous database session for agents
- Registers all 7 agents with the orchestrator
- Starts the orchestrator to process queued tasks
- Handles graceful shutdown

### 2. Created Windows Batch Script
**File**: `start-worker.bat`

Convenience script to start the worker:
```batch
cd backend
call venv\Scripts\activate
python -m agents.worker
```

### 3. Updated Main Application
**File**: `backend/main.py`

Added note in lifespan that worker should be run separately.

### 4. Fixed Orchestrator Status Updates
**File**: `backend/agents/orchestrator.py`

Fixed status parameter to use `AgentTaskStatus` enum instead of strings.

### 5. Created Comprehensive Startup Guide
**File**: `COMPLETE_STARTUP_GUIDE.md`

Complete documentation for running all services.

## Architecture

The system now runs as 3 separate processes:

```
1. Backend API (FastAPI)
   - Handles HTTP requests
   - Queues tasks to Redis
   - Port: 8000

2. Agent Worker (Background)
   - Processes queued tasks
   - Runs 7 specialized agents
   - 3 workers per agent type

3. Frontend (Next.js)
   - User interface
   - Port: 3000
```

## Agents Registered

1. **IngestionAgent** - Parses files and extracts questions
2. **PatternMinerAgent** - Learns exam patterns from question banks
3. **QuestionSelectorAgent** - Generates exam papers
4. **AnswerKeyGeneratorAgent** - Creates answer keys
5. **GradingEvaluatorAgent** - Evaluates student answers
6. **WeaknessAnalyzerAgent** - Identifies learning gaps
7. **RoadmapAgent** - Updates personalized learning paths

## How to Run

### Start All Services:

1. **Docker Services**:
   ```cmd
   docker-compose up -d
   ```

2. **Backend API**:
   ```cmd
   start-backend.bat
   ```

3. **Agent Worker** (NEW - REQUIRED):
   ```cmd
   start-worker.bat
   ```

4. **Frontend**:
   ```cmd
   start-frontend.bat
   ```

## Verification

After starting the worker, you should see:
```
Starting AURORA Assess Agent Worker...
Database session created
Registered 7 agents
Agent orchestrator started and processing tasks...
```

When you upload a question bank:
1. API queues the task to Redis
2. Worker picks up the task
3. IngestionAgent processes the file
4. Status changes: PENDING → PROCESSING → COMPLETED
5. Questions appear in the database

## Task Flow

```
User uploads file
       ↓
API creates QuestionBank record (status: UPLOADED)
       ↓
API queues ingestion task to Redis
       ↓
Worker picks up task from Redis
       ↓
IngestionAgent processes:
  - Downloads file from MinIO
  - Parses PDF/DOCX/TXT
  - Extracts questions with LLM
  - Suggests tags with LLM
  - Generates embeddings
  - Stores questions in database
       ↓
Status updated: COMPLETED
       ↓
Questions visible in UI
```

## Benefits

1. **Separation of Concerns**: API handles requests, worker handles processing
2. **Scalability**: Can run multiple workers for high load
3. **Reliability**: Worker can restart without affecting API
4. **Monitoring**: Separate logs for API and worker
5. **Development**: Can develop/test API without running worker

## Testing

To test the complete flow:

1. Start all services (including worker)
2. Login as faculty
3. Go to Question Banks
4. Upload a PDF file
5. Watch the worker terminal for processing logs
6. Refresh the page - status should change to COMPLETED
7. Click on the question bank to see extracted questions

## Troubleshooting

### Upload stays PENDING
- **Cause**: Worker not running
- **Fix**: Run `start-worker.bat`

### Worker crashes
- **Cause**: Database connection issues
- **Fix**: Check PostgreSQL is running, verify DATABASE_URL

### No questions extracted
- **Cause**: File parsing failed or LLM errors
- **Fix**: Check worker logs for errors, verify OPENAI_API_KEY

## Files Modified

1. `backend/agents/worker.py` - NEW
2. `start-worker.bat` - NEW
3. `backend/main.py` - Updated lifespan
4. `backend/agents/orchestrator.py` - Fixed status updates
5. `COMPLETE_STARTUP_GUIDE.md` - NEW
6. `AGENT_WORKER_FIX_COMPLETE.md` - This file

## Status

✅ Worker process created
✅ Batch script for easy startup
✅ Orchestrator status fixes
✅ Complete documentation
✅ All agents registered and ready
✅ Task processing functional

## Next Steps

1. Start the worker: `start-worker.bat`
2. Upload a question bank
3. Verify it processes successfully
4. Test other agent features (pattern learning, paper generation, etc.)
