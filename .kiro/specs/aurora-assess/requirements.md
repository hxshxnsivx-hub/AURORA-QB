# Requirements Document: AURORA Assess

## Introduction

AURORA Assess is a multi-agent orchestration system designed to revolutionize exam preparation and evaluation for academic institutions. The system extends the AURORA Learn adaptive learning platform by providing intelligent exam generation, automated evaluation, and personalized learning roadmap updates based on student performance.

The system learns from uploaded question banks to understand exam patterns, generates multiple customized question paper sets, produces comprehensive answer keys, evaluates student submissions using hybrid rule-based and LLM-powered grading, and identifies knowledge gaps to update personalized learning paths.

## Glossary

- **System**: AURORA Assess platform
- **Question_Bank**: A collection of questions uploaded by faculty for a specific subject
- **Resource**: Educational material (notes, slides, PDFs) uploaded to support learning
- **Paper_Set**: A generated exam paper with specific constraints and question selection
- **Answer_Key**: Model answers and grading rubrics for questions in a paper
- **Attempt**: A student's submission of answers for a specific paper
- **Evaluation**: Graded results with scores and feedback for an attempt
- **Knowledge_Graph**: Graph structure representing relationships between subjects, topics, concepts, and questions
- **Concept_Mastery**: Student's proficiency level for a specific concept
- **Roadmap**: Personalized learning path with tasks and resources
- **Agent**: Autonomous component performing specific tasks (ingestion, grading, etc.)
- **Pattern**: Learned distribution of marks, question types, topics, and difficulty from question banks
- **Weakness**: Topic or concept where student performance is below threshold
- **Faculty**: Teachers or instructors who upload content and manage courses
- **Student**: Learner who attempts exams and receives feedback
- **Admin**: System administrator managing users and system configuration

## Requirements

### Requirement 1: User Authentication and Role Management

**User Story:** As a system administrator, I want to manage user accounts with role-based access control, so that students, faculty, and admins have appropriate permissions.

#### Acceptance Criteria

1. THE System SHALL support three user roles: Student, Faculty, and Admin
2. WHEN a user registers, THE System SHALL assign them a default role of Student
3. WHEN an Admin promotes a user, THE System SHALL update their role and permissions immediately
4. THE System SHALL authenticate users using email and password credentials
5. WHEN a user logs in, THE System SHALL create a session token valid for 24 hours
6. THE System SHALL enforce role-based access control on all protected endpoints
7. WHEN an unauthorized user attempts to access a protected resource, THE System SHALL return a 403 Forbidden error

### Requirement 2: Question Bank Upload and Parsing

**User Story:** As a faculty member, I want to upload question banks in various formats, so that the system can learn exam patterns and generate papers.

#### Acceptance Criteria

1. WHEN a Faculty user uploads a file, THE System SHALL accept PDF, DOCX, and TXT formats
2. WHEN a file is uploaded, THE System SHALL validate the file size is under 50MB
3. THE System SHALL parse uploaded files and extract individual questions with their text content
4. WHEN parsing fails, THE System SHALL return a descriptive error message indicating the failure reason
5. THE System SHALL store the original file in S3-compatible storage with a unique identifier
6. WHEN a question bank is uploaded, THE System SHALL associate it with the uploading Faculty user and specified subject
7. THE System SHALL extract metadata from questions including marks allocation and question type hints

### Requirement 3: Resource Upload and Management

**User Story:** As a faculty member, I want to upload educational resources, so that students can access study materials and the system can ground answer generation.

#### Acceptance Criteria

1. WHEN a Faculty user uploads a resource, THE System SHALL accept PDF, DOCX, PPTX, and TXT formats
2. THE System SHALL store resources in S3-compatible storage with metadata (title, subject, unit, topic)
3. WHEN a resource is uploaded, THE System SHALL generate embeddings for semantic search
4. THE System SHALL allow Faculty to link resources to specific topics and concepts
5. WHEN a resource is deleted, THE System SHALL remove it from storage and update all references
6. THE System SHALL allow Students to view and download resources for subjects they are enrolled in

### Requirement 4: Question Tagging and Classification

**User Story:** As a faculty member, I want to tag questions with metadata, so that the system can generate targeted exam papers.

#### Acceptance Criteria

1. THE System SHALL support manual tagging of questions with unit, topic, marks, type, and difficulty
2. WHEN a question bank is uploaded, THE System SHALL suggest tags using LLM-based analysis
3. THE System SHALL support question types: MCQ, Short Answer, Long Answer, Numerical, True/False
4. THE System SHALL support difficulty levels: Easy, Medium, Hard
5. WHEN Faculty reviews suggested tags, THE System SHALL allow editing and confirmation
6. THE System SHALL store all tags in a structured format linked to the question
7. THE System SHALL allow bulk tagging operations for multiple questions simultaneously

### Requirement 5: Exam Pattern Learning

**User Story:** As a system, I want to learn exam patterns from uploaded question banks, so that generated papers follow realistic distributions.

#### Acceptance Criteria

1. WHEN a question bank is marked as complete, THE System SHALL analyze mark distribution patterns
2. THE System SHALL calculate frequency distributions for question types across the bank
3. THE System SHALL identify topic coverage patterns and their relative weights
4. THE System SHALL compute difficulty distribution across marks categories
5. THE System SHALL store learned patterns as a Pattern object associated with the subject
6. WHEN multiple question banks exist for a subject, THE System SHALL aggregate patterns across all banks
7. THE System SHALL allow Faculty to view and adjust learned patterns manually

### Requirement 6: Exam Paper Generation with Constraints

**User Story:** As a faculty member, I want to generate multiple exam paper sets with specific constraints, so that I can create varied assessments following exam patterns.

#### Acceptance Criteria

1. THE System SHALL provide a UI for Faculty to specify: total marks, number of sets, mark distribution, question type distribution, topic coverage, and difficulty mix
2. WHEN Faculty submits generation request, THE System SHALL validate that constraints are satisfiable given available questions
3. THE System SHALL generate N paper sets where each set respects all specified constraints
4. THE System SHALL ensure minimal question overlap between generated sets
5. THE System SHALL apply learned patterns to guide question selection when constraints allow flexibility
6. WHEN generation completes, THE System SHALL return paper IDs and preview links for all generated sets
7. IF constraints cannot be satisfied, THE System SHALL return an error with specific constraint violations

### Requirement 7: Answer Key Generation

**User Story:** As a faculty member, I want the system to generate answer keys for exam papers, so that grading can be automated and consistent.

#### Acceptance Criteria

1. WHEN a paper is generated, THE System SHALL create answer keys for all questions in the paper
2. THE System SHALL generate rule-based answer keys for MCQ and True/False questions
3. THE System SHALL use LLM-based generation for Short Answer and Long Answer model answers
4. THE System SHALL ground LLM-generated answers in uploaded resources when available
5. THE System SHALL include grading rubrics specifying point allocation for answer components
6. THE System SHALL allow Faculty to review and edit generated answer keys before publishing
7. THE System SHALL store answer keys separately from papers to prevent student access

### Requirement 8: Student Exam Attempt and Submission

**User Story:** As a student, I want to attempt exam papers and submit my answers, so that I can practice and receive feedback.

#### Acceptance Criteria

1. WHEN a Student selects a paper, THE System SHALL display all questions in order with answer input fields
2. THE System SHALL support text input for Short Answer and Long Answer questions
3. THE System SHALL support single-choice selection for MCQ questions
4. THE System SHALL allow Students to save progress and resume attempts later
5. WHEN a Student submits an attempt, THE System SHALL validate all required questions are answered
6. THE System SHALL record submission timestamp and associate answers with the Student and Paper
7. THE System SHALL prevent Students from viewing answer keys before submission

### Requirement 9: Automated Answer Evaluation

**User Story:** As a student, I want my answers to be evaluated automatically, so that I receive immediate feedback on my performance.

#### Acceptance Criteria

1. WHEN a Student submits an attempt, THE System SHALL initiate automated evaluation
2. THE System SHALL use rule-based exact matching for MCQ and True/False questions
3. THE System SHALL use LLM-based semantic evaluation for Short Answer and Long Answer questions
4. THE System SHALL compare student answers against answer keys and rubrics
5. THE System SHALL assign scores for each question based on rubric criteria
6. THE System SHALL generate feedback explaining score allocation and identifying errors
7. WHEN evaluation completes, THE System SHALL store results and notify the Student

### Requirement 10: Performance Analysis and Weakness Detection

**User Story:** As a student, I want to see my performance analysis, so that I can identify topics where I need improvement.

#### Acceptance Criteria

1. WHEN an evaluation completes, THE System SHALL compute topic-wise performance scores
2. THE System SHALL identify topics where Student score is below 60% as weaknesses
3. THE System SHALL aggregate performance across multiple attempts for trend analysis
4. THE System SHALL compute concept-level mastery scores using the Knowledge Graph
5. THE System SHALL rank weaknesses by severity based on score gaps and concept importance
6. THE System SHALL display performance reports with visualizations of topic scores
7. THE System SHALL recommend specific resources for each identified weakness

### Requirement 11: Knowledge Graph Construction and Queries

**User Story:** As a system, I want to maintain a knowledge graph of concepts and relationships, so that I can provide intelligent recommendations and analysis.

#### Acceptance Criteria

1. THE System SHALL represent subjects, units, topics, and concepts as graph nodes
2. THE System SHALL represent questions and resources as nodes linked to topics
3. THE System SHALL represent prerequisite relationships between concepts as directed edges
4. THE System SHALL represent student mastery levels as edges between Student nodes and Concept nodes
5. THE System SHALL support queries to find all questions covering specific concepts
6. THE System SHALL support queries to find prerequisite concepts for a given concept
7. THE System SHALL support queries to identify weak concepts and their related strong prerequisites

### Requirement 12: Learning Roadmap Integration

**User Story:** As a student, I want my learning roadmap updated based on exam performance, so that I receive personalized study recommendations.

#### Acceptance Criteria

1. WHEN weaknesses are identified, THE System SHALL generate roadmap update requests
2. THE System SHALL expose an API endpoint to send weakness data to AURORA Learn
3. THE System SHALL format roadmap updates with concept IDs, mastery scores, and recommended resources
4. WHEN AURORA Learn acknowledges updates, THE System SHALL mark roadmap sync as complete
5. THE System SHALL receive updated roadmap tasks from AURORA Learn via webhook
6. THE System SHALL display updated roadmap tasks in the Student dashboard
7. THE System SHALL track completion of roadmap tasks and update concept mastery accordingly

### Requirement 13: Faculty Grading Override and Review

**User Story:** As a faculty member, I want to review and override automated grading, so that I can ensure fairness and accuracy.

#### Acceptance Criteria

1. THE System SHALL allow Faculty to view all student attempts and automated evaluations
2. WHEN Faculty views an evaluation, THE System SHALL display student answer, model answer, and assigned score
3. THE System SHALL allow Faculty to modify scores and feedback for any question
4. WHEN Faculty overrides a score, THE System SHALL recalculate total score and update performance analysis
5. THE System SHALL log all grading overrides with Faculty ID and timestamp
6. THE System SHALL notify Students when Faculty modifies their evaluation
7. THE System SHALL display override history for transparency and audit purposes

### Requirement 14: Multi-Agent Orchestration

**User Story:** As a system architect, I want agents to coordinate through a clear orchestration pattern, so that the system is maintainable and extensible.

#### Acceptance Criteria

1. THE System SHALL implement seven specialized agents: Ingestion, Pattern Miner, Question Selector, Answer Key Generator, Grading Evaluator, Weakness Analyzer, and Roadmap
2. WHEN an agent completes a task, THE System SHALL publish an event to notify dependent agents
3. THE System SHALL use a message queue for asynchronous agent communication
4. THE System SHALL implement retry logic for failed agent tasks with exponential backoff
5. THE System SHALL log all agent activities with timestamps and input/output data
6. THE System SHALL provide a monitoring dashboard showing agent status and task queues
7. WHEN an agent fails repeatedly, THE System SHALL alert administrators and halt dependent tasks

### Requirement 15: System Observability and Logging

**User Story:** As a system administrator, I want comprehensive logging and monitoring, so that I can debug issues and ensure system health.

#### Acceptance Criteria

1. THE System SHALL log all API requests with timestamp, user ID, endpoint, and response status
2. THE System SHALL log all agent executions with input parameters, output results, and execution time
3. THE System SHALL log all LLM API calls with prompt, response, token count, and latency
4. THE System SHALL provide structured logs in JSON format for easy parsing
5. THE System SHALL expose health check endpoints for all services
6. THE System SHALL track and expose metrics: request rate, error rate, agent queue depth, LLM token usage
7. THE System SHALL retain logs for 90 days and provide search and filtering capabilities

### Requirement 16: File Storage and Retrieval

**User Story:** As a system, I want reliable file storage for question banks and resources, so that content is durable and accessible.

#### Acceptance Criteria

1. THE System SHALL store all uploaded files in S3-compatible object storage
2. WHEN a file is uploaded, THE System SHALL generate a unique identifier and store metadata in the database
3. THE System SHALL generate pre-signed URLs for secure file downloads with 1-hour expiration
4. THE System SHALL implement file versioning to track changes to question banks
5. WHEN a file is deleted, THE System SHALL perform soft deletion and retain the file for 30 days
6. THE System SHALL validate file integrity using checksums after upload
7. THE System SHALL implement access control ensuring users can only access authorized files

### Requirement 17: Semantic Search for Resources

**User Story:** As a student, I want to search for relevant resources using natural language, so that I can find study materials efficiently.

#### Acceptance Criteria

1. WHEN a resource is uploaded, THE System SHALL generate vector embeddings using an embedding model
2. THE System SHALL store embeddings in pgvector for efficient similarity search
3. WHEN a Student submits a search query, THE System SHALL generate query embeddings
4. THE System SHALL perform vector similarity search and return top 10 most relevant resources
5. THE System SHALL rank results by combining semantic similarity and metadata relevance
6. THE System SHALL filter results based on Student's enrolled subjects
7. THE System SHALL highlight matching excerpts in search results

### Requirement 18: Exam Configuration Validation

**User Story:** As a faculty member, I want the system to validate my exam configuration, so that I know if paper generation is feasible before waiting.

#### Acceptance Criteria

1. WHEN Faculty enters exam constraints, THE System SHALL validate in real-time
2. THE System SHALL check if sufficient questions exist for each mark category
3. THE System SHALL check if sufficient questions exist for each question type
4. THE System SHALL check if topic coverage constraints can be satisfied
5. THE System SHALL check if difficulty distribution constraints can be satisfied
6. WHEN constraints are invalid, THE System SHALL display specific error messages indicating which constraints conflict
7. THE System SHALL suggest constraint adjustments to make generation feasible

### Requirement 19: Batch Paper Generation

**User Story:** As a faculty member, I want to generate multiple paper sets in a single request, so that I can create varied assessments efficiently.

#### Acceptance Criteria

1. THE System SHALL support generating up to 10 paper sets in a single request
2. WHEN generating multiple sets, THE System SHALL maximize question diversity across sets
3. THE System SHALL process generation requests asynchronously and provide a job ID
4. THE System SHALL allow Faculty to poll generation status using the job ID
5. WHEN generation completes, THE System SHALL notify Faculty via email with download links
6. THE System SHALL ensure each generated set is independently valid against all constraints
7. THE System SHALL provide a summary report showing constraint satisfaction for each set

### Requirement 20: Student Performance Dashboard

**User Story:** As a student, I want a dashboard showing my performance trends, so that I can track my progress over time.

#### Acceptance Criteria

1. THE System SHALL display a dashboard with overall score trends across attempts
2. THE System SHALL display topic-wise performance with color-coded strength indicators
3. THE System SHALL display a list of identified weaknesses with severity rankings
4. THE System SHALL display recommended resources for each weakness
5. THE System SHALL display upcoming roadmap tasks from AURORA Learn integration
6. THE System SHALL display historical attempt scores with date and paper information
7. THE System SHALL allow Students to filter dashboard data by subject and date range
