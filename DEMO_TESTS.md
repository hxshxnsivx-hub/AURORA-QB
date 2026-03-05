# Demo Tests: Authentication and Basic CRUD

This document provides step-by-step instructions to demonstrate working authentication and basic CRUD operations in AURORA Assess.

## Prerequisites

- System running locally or on staging
- API accessible at `http://localhost:8000` (or staging URL)
- Frontend accessible at `http://localhost:3000` (or staging URL)
- Database initialized with migrations

## Test Suite

### 1. Authentication Tests

#### 1.1 User Registration

**Manual Test:**
1. Navigate to `http://localhost:3000/register`
2. Fill in registration form:
   - Email: `test-student@example.com`
   - Password: `SecurePass123!`
   - Confirm Password: `SecurePass123!`
3. Click "Register"
4. Verify redirect to login page
5. Verify success message displayed

**API Test:**
```bash
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "api-test@example.com",
    "password": "SecurePass123!"
  }'
```

Expected response:
```json
{
  "id": "uuid",
  "email": "api-test@example.com",
  "role": "Student",
  "created_at": "2024-01-15T10:30:00Z"
}
```

#### 1.2 User Login

**Manual Test:**
1. Navigate to `http://localhost:3000/login`
2. Enter credentials:
   - Email: `test-student@example.com`
   - Password: `SecurePass123!`
3. Click "Login"
4. Verify redirect to dashboard
5. Verify user info displayed in header

**API Test:**
```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "api-test@example.com",
    "password": "SecurePass123!"
  }'
```

Expected response:
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer",
  "user": {
    "id": "uuid",
    "email": "api-test@example.com",
    "role": "Student"
  }
}
```

Save the token for subsequent tests:
```bash
export TOKEN="<access_token_from_response>"
```

#### 1.3 Get Current User

**API Test:**
```bash
curl -X GET http://localhost:8000/api/auth/me \
  -H "Authorization: Bearer $TOKEN"
```

Expected response:
```json
{
  "id": "uuid",
  "email": "api-test@example.com",
  "role": "Student",
  "created_at": "2024-01-15T10:30:00Z"
}
```

#### 1.4 Unauthorized Access (403 Test)

**API Test:**
```bash
# Try to access admin endpoint as student
curl -X GET http://localhost:8000/api/users \
  -H "Authorization: Bearer $TOKEN"
```

Expected response:
```json
{
  "detail": "Insufficient permissions"
}
```
Status code: 403

#### 1.5 Logout

**Manual Test:**
1. Click user menu in header
2. Click "Logout"
3. Verify redirect to login page
4. Verify cannot access dashboard without login

### 2. Subject CRUD Tests

#### 2.1 Create Subject (Faculty/Admin only)

First, create a faculty user:
```bash
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "faculty@example.com",
    "password": "FacultyPass123!"
  }'

# Login as faculty
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "faculty@example.com",
    "password": "FacultyPass123!"
  }'

export FACULTY_TOKEN="<access_token>"
```

Promote to faculty (requires admin):
```bash
# You'll need to do this via database or admin panel
# For demo, assume faculty role is assigned
```

Create subject:
```bash
curl -X POST http://localhost:8000/api/subjects \
  -H "Authorization: Bearer $FACULTY_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Computer Science 101",
    "code": "CS101",
    "description": "Introduction to Computer Science"
  }'
```

Expected response:
```json
{
  "id": "uuid",
  "name": "Computer Science 101",
  "code": "CS101",
  "description": "Introduction to Computer Science",
  "created_at": "2024-01-15T10:30:00Z"
}
```

Save subject ID:
```bash
export SUBJECT_ID="<subject_id_from_response>"
```

#### 2.2 Read Subject

**API Test:**
```bash
curl -X GET http://localhost:8000/api/subjects/$SUBJECT_ID \
  -H "Authorization: Bearer $TOKEN"
```

Expected: Same subject data as created

#### 2.3 List Subjects

**API Test:**
```bash
curl -X GET http://localhost:8000/api/subjects \
  -H "Authorization: Bearer $TOKEN"
```

Expected: Array containing the created subject

#### 2.4 Update Subject

**API Test:**
```bash
curl -X PUT http://localhost:8000/api/subjects/$SUBJECT_ID \
  -H "Authorization: Bearer $FACULTY_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Computer Science 101 - Updated",
    "code": "CS101",
    "description": "Introduction to Computer Science - Updated description"
  }'
```

Expected: Updated subject data

#### 2.5 Delete Subject

**API Test:**
```bash
curl -X DELETE http://localhost:8000/api/subjects/$SUBJECT_ID \
  -H "Authorization: Bearer $FACULTY_TOKEN"
```

Expected: 204 No Content or success message

Verify deletion:
```bash
curl -X GET http://localhost:8000/api/subjects/$SUBJECT_ID \
  -H "Authorization: Bearer $TOKEN"
```

Expected: 404 Not Found

### 3. Unit CRUD Tests

#### 3.1 Create Unit

```bash
# First recreate subject
curl -X POST http://localhost:8000/api/subjects \
  -H "Authorization: Bearer $FACULTY_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Data Structures",
    "code": "CS201",
    "description": "Data Structures and Algorithms"
  }'

export SUBJECT_ID="<new_subject_id>"

# Create unit
curl -X POST http://localhost:8000/api/units \
  -H "Authorization: Bearer $FACULTY_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "subject_id": "'$SUBJECT_ID'",
    "name": "Arrays and Lists",
    "order": 1
  }'
```

Expected response:
```json
{
  "id": "uuid",
  "subject_id": "uuid",
  "name": "Arrays and Lists",
  "order": 1
}
```

#### 3.2 Read, Update, Delete Unit

Follow same pattern as Subject CRUD tests.

### 4. Topic CRUD Tests

```bash
# Create topic
curl -X POST http://localhost:8000/api/topics \
  -H "Authorization: Bearer $FACULTY_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "unit_id": "'$UNIT_ID'",
    "name": "Dynamic Arrays",
    "description": "Resizable array implementation"
  }'
```

### 5. Concept CRUD Tests

```bash
# Create concept
curl -X POST http://localhost:8000/api/concepts \
  -H "Authorization: Bearer $FACULTY_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "topic_id": "'$TOPIC_ID'",
    "name": "Array Resizing",
    "description": "How dynamic arrays grow",
    "importance": 0.8
  }'
```

## Automated Test Script

Save this as `demo_test.sh`:

```bash
#!/bin/bash

API_URL="http://localhost:8000"
BASE_URL="http://localhost:3000"

echo "=== AURORA Assess Demo Tests ==="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Test counter
PASSED=0
FAILED=0

test_api() {
  local name=$1
  local method=$2
  local endpoint=$3
  local data=$4
  local expected_status=$5
  local headers=$6
  
  echo -n "Testing: $name... "
  
  response=$(curl -s -w "\n%{http_code}" -X $method "$API_URL$endpoint" \
    -H "Content-Type: application/json" \
    $headers \
    ${data:+-d "$data"})
  
  status=$(echo "$response" | tail -n1)
  body=$(echo "$response" | head -n-1)
  
  if [ "$status" = "$expected_status" ]; then
    echo -e "${GREEN}PASSED${NC}"
    ((PASSED++))
  else
    echo -e "${RED}FAILED${NC} (Expected $expected_status, got $status)"
    echo "Response: $body"
    ((FAILED++))
  fi
}

# Test 1: Register
echo "1. Authentication Tests"
test_api "Register new user" "POST" "/api/auth/register" \
  '{"email":"demo@test.com","password":"Test123!"}' "200"

# Test 2: Login
response=$(curl -s -X POST "$API_URL/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"demo@test.com","password":"Test123!"}')

TOKEN=$(echo $response | grep -o '"access_token":"[^"]*' | cut -d'"' -f4)

if [ -n "$TOKEN" ]; then
  echo -e "${GREEN}✓${NC} Login successful, token obtained"
  ((PASSED++))
else
  echo -e "${RED}✗${NC} Login failed"
  ((FAILED++))
fi

# Test 3: Get current user
test_api "Get current user" "GET" "/api/auth/me" "" "200" \
  "-H 'Authorization: Bearer $TOKEN'"

# Test 4: Create subject
test_api "Create subject" "POST" "/api/subjects" \
  '{"name":"Test Subject","code":"TEST101","description":"Test"}' "200" \
  "-H 'Authorization: Bearer $TOKEN'"

# Test 5: List subjects
test_api "List subjects" "GET" "/api/subjects" "" "200" \
  "-H 'Authorization: Bearer $TOKEN'"

echo ""
echo "=== Test Summary ==="
echo -e "Passed: ${GREEN}$PASSED${NC}"
echo -e "Failed: ${RED}$FAILED${NC}"
echo "Total: $((PASSED + FAILED))"
```

Run the script:
```bash
chmod +x demo_test.sh
./demo_test.sh
```

## Success Criteria

All tests should pass with:
- ✅ User registration creates new user
- ✅ User login returns valid JWT token
- ✅ Protected endpoints require authentication
- ✅ Role-based access control enforced (403 for unauthorized)
- ✅ CRUD operations work for all entities (Subject, Unit, Topic, Concept)
- ✅ Data persists across requests
- ✅ Validation errors return appropriate messages

## Troubleshooting

### Token expired
Re-login to get a new token

### 401 Unauthorized
Check token is included in Authorization header

### 403 Forbidden
User role doesn't have permission for this endpoint

### 500 Internal Server Error
Check backend logs: `docker-compose logs backend`

### Database connection error
Verify PostgreSQL is running: `docker-compose ps postgres`
