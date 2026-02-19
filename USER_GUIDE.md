# AURORA Assess User Guide

## Table of Contents

1. [Getting Started](#getting-started)
2. [For Students](#for-students)
3. [For Faculty](#for-faculty)
4. [For Administrators](#for-administrators)
5. [Common Tasks](#common-tasks)
6. [Troubleshooting](#troubleshooting)

---

## Getting Started

### Accessing the System

1. Open your web browser and navigate to: `http://localhost:3000`
2. You'll see the AURORA Assess homepage

### Creating an Account

1. Click **Register** in the top right corner
2. Enter your email address
3. Create a password (minimum 8 characters)
4. Confirm your password
5. Click **Register**
6. You'll be automatically logged in and redirected to your dashboard

### Logging In

1. Click **Login** in the top right corner
2. Enter your email and password
3. Click **Sign in**
4. You'll be redirected to your dashboard

### User Roles

AURORA Assess has three user roles:

- **Student**: Can attempt exams, view performance, and access resources
- **Faculty**: Can create content, generate papers, and review grading
- **Admin**: Can manage users and system configuration

New accounts are created as **Student** by default. Contact an administrator to upgrade your role.

---

## For Students

### Dashboard Overview

Your dashboard shows:
- Number of exam attempts
- Overall performance score
- Available subjects
- Recommended resources

### Taking an Exam

1. Navigate to **Subjects** from the sidebar
2. Select a subject
3. Click on an available exam paper
4. Click **Start Attempt**
5. Answer all questions
6. Click **Submit** when finished

**Note**: You can save your progress and resume later by clicking **Save Progress**.

### Viewing Results

1. Go to **My Attempts** from the sidebar
2. Click on a completed attempt
3. View your:
   - Total score
   - Per-question feedback
   - Topic-wise performance
   - Identified weaknesses

### Tracking Performance

1. Navigate to **Performance** from the sidebar
2. View your:
   - Overall score trends
   - Topic-wise strengths and weaknesses
   - Recommended study materials
   - Learning roadmap tasks

### Accessing Resources

1. Go to **Subjects** from the sidebar
2. Select a subject
3. Click **Resources** tab
4. Browse or search for study materials
5. Click to download or view

---

## For Faculty

### Dashboard Overview

Your dashboard shows:
- Number of question banks
- Generated papers
- Student performance overview
- System statistics

### Creating Course Structure

#### 1. Create a Subject

1. Navigate to **Subjects** from the sidebar
2. Click **Create Subject**
3. Enter:
   - Subject name (e.g., "Data Structures")
   - Subject code (e.g., "CS201")
   - Description (optional)
4. Click **Create**

#### 2. Create Units

1. Select your subject
2. Click **Add Unit**
3. Enter:
   - Unit name (e.g., "Arrays and Linked Lists")
   - Order number (e.g., 1, 2, 3...)
4. Click **Create**

#### 3. Create Topics

1. Select a unit
2. Click **Add Topic**
3. Enter:
   - Topic name (e.g., "Dynamic Arrays")
   - Description (optional)
4. Click **Create**

#### 4. Create Concepts

1. Select a topic
2. Click **Add Concept**
3. Enter:
   - Concept name (e.g., "Array Indexing")
   - Description (optional)
   - Importance (0.0 to 1.0)
4. Click **Create**

### Uploading Question Banks

1. Navigate to **Question Banks** from the sidebar
2. Click **Upload Question Bank**
3. Select a subject
4. Choose a file (PDF, DOCX, or TXT)
5. Click **Upload**
6. Wait for processing to complete
7. Review and confirm AI-suggested tags

**Supported Formats**:
- PDF (.pdf)
- Word Document (.docx)
- Plain Text (.txt)

**File Size Limit**: 50MB

### Uploading Resources

1. Navigate to **Subjects** from the sidebar
2. Select a subject
3. Click **Resources** tab
4. Click **Upload Resource**
5. Enter:
   - Title
   - Select file
   - Link to topics (optional)
6. Click **Upload**

### Generating Exam Papers

1. Navigate to **Papers** from the sidebar
2. Click **Generate Papers**
3. Configure constraints:
   - Total marks
   - Number of sets
   - Mark distribution (1, 2, 3, 5, 10, 12 marks)
   - Question type distribution
   - Topic coverage
   - Difficulty mix
4. Click **Generate**
5. Wait for generation to complete
6. Review generated papers
7. Download or publish

### Reviewing Student Submissions

1. Navigate to **Papers** from the sidebar
2. Select a paper
3. Click **View Submissions**
4. Select a student submission
5. Review:
   - Student answers
   - Automated scores
   - AI-generated feedback
6. Override scores if needed
7. Add additional feedback
8. Click **Save Changes**

### Viewing Analytics

1. Navigate to **Analytics** from the sidebar
2. View:
   - Class performance overview
   - Topic-wise difficulty analysis
   - Question effectiveness metrics
   - Student progress trends

---

## For Administrators

### Dashboard Overview

Your dashboard shows:
- Total users by role
- System health metrics
- Recent activity
- Storage usage

### Managing Users

#### Viewing Users

1. Navigate to **Users** from the sidebar
2. View list of all users
3. Filter by role or search by email

#### Changing User Roles

1. Go to **Users**
2. Click on a user
3. Click **Change Role**
4. Select new role:
   - Student
   - Faculty
   - Admin
5. Click **Update**

**Note**: Be careful when assigning Admin role!

#### Deleting Users

1. Go to **Users**
2. Click on a user
3. Click **Delete User**
4. Confirm deletion

**Warning**: This action cannot be undone!

### System Monitoring

1. Navigate to **System** from the sidebar
2. View:
   - API health status
   - Database connection status
   - Storage usage
   - Agent task queues
   - Error logs

### Viewing Logs

1. Navigate to **System** > **Logs**
2. Filter by:
   - Log level (INFO, WARNING, ERROR)
   - Date range
   - User
   - Event type
3. Search for specific events
4. Export logs if needed

---

## Common Tasks

### Changing Your Password

1. Click your email in the top right
2. Select **Profile**
3. Click **Change Password**
4. Enter current password
5. Enter new password
6. Confirm new password
7. Click **Update**

### Logging Out

1. Click your email in the top right
2. Click **Logout**

### Getting Help

- **Documentation**: Click **Help** in the sidebar
- **Support**: Email support@aurora-assess.example.com
- **Report Bug**: Use the feedback form in **Help** > **Report Issue**

---

## Troubleshooting

### Cannot Log In

**Problem**: "Incorrect email or password" error

**Solutions**:
1. Check your email is spelled correctly
2. Ensure Caps Lock is off
3. Try resetting your password
4. Contact an administrator if issue persists

### File Upload Fails

**Problem**: File upload returns an error

**Solutions**:
1. Check file size is under 50MB
2. Ensure file format is supported (PDF, DOCX, TXT, PPTX)
3. Try a different file
4. Check your internet connection
5. Contact support if issue persists

### Cannot Access a Feature

**Problem**: "Insufficient permissions" or 403 error

**Solutions**:
1. Check your user role in the top right
2. Verify you have the required role for this feature:
   - Students: Exams, Performance, Resources
   - Faculty: All Student features + Question Banks, Papers, Analytics
   - Admin: All features + User Management, System Settings
3. Contact an administrator to upgrade your role if needed

### Page Not Loading

**Problem**: Page shows loading spinner indefinitely

**Solutions**:
1. Refresh the page (F5 or Ctrl+R)
2. Clear your browser cache
3. Try a different browser
4. Check your internet connection
5. Contact support if issue persists

### Exam Submission Failed

**Problem**: Cannot submit exam answers

**Solutions**:
1. Ensure all required questions are answered
2. Check your internet connection
3. Try saving progress first
4. Refresh the page and resume
5. Contact support immediately if issue persists

---

## Keyboard Shortcuts

- **Ctrl + K**: Quick search
- **Ctrl + /**: Open help
- **Esc**: Close modal/dialog
- **Tab**: Navigate form fields

---

## Best Practices

### For Students

- Save your progress frequently during exams
- Review feedback carefully to understand mistakes
- Focus on identified weaknesses
- Complete roadmap tasks regularly

### For Faculty

- Tag questions accurately for better paper generation
- Review AI-generated answer keys before publishing
- Provide detailed feedback on student submissions
- Monitor class performance trends

### For Administrators

- Regularly review system logs
- Monitor storage usage
- Back up data regularly
- Keep user roles up to date

---

## Support

Need help? Contact us:

- **Email**: support@aurora-assess.example.com
- **Documentation**: http://localhost:3000/docs
- **GitHub**: [Repository URL]

---

**Version**: 0.1.0  
**Last Updated**: 2024
