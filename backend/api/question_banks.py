"""
API endpoints for question bank management.
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from api.dependencies import get_db, get_current_user, require_role
from models.user import User, UserRole
from models.question import QuestionBank, Question, QuestionBankStatus
from models.academic import Subject
from schemas.question_bank import (
    QuestionBankResponse,
    QuestionResponse,
    QuestionUpdate,
    BulkTagUpdate,
    BulkTagResponse
)
from utils.storage import upload_file
from utils.logger import logger
from agents.task_queue import TaskQueue
import os


router = APIRouter(prefix="/question-banks", tags=["question-banks"])


@router.post("/upload", response_model=QuestionBankResponse, status_code=status.HTTP_201_CREATED)
async def upload_question_bank(
    subject_id: UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.FACULTY, UserRole.ADMIN]))
):
    """
    Upload a question bank file for processing.
    
    Supported formats: PDF, DOCX, TXT
    Max file size: 50MB
    """
    # Validate file extension
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in ['.pdf', '.docx', '.txt']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format: {file_ext}. Supported: PDF, DOCX, TXT"
        )
    
    # Validate subject exists
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subject {subject_id} not found"
        )
    
    # Read file content
    file_content = await file.read()
    file_size = len(file_content)
    
    # Validate file size (50MB max)
    if file_size > 50 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size must not exceed 50MB"
        )
    
    try:
        # Upload file to storage
        file_path = await upload_file(
            file_content=file_content,
            file_name=file.filename,
            content_type=file.content_type
        )
        
        # Create question bank record
        bank = QuestionBank(
            subject_id=subject_id,
            faculty_id=current_user.id,
            file_path=file_path,
            file_name=file.filename,
            file_size=file_size,
            status=QuestionBankStatus.UPLOADED
        )
        
        db.add(bank)
        db.commit()
        db.refresh(bank)
        
        # Queue ingestion task
        task_queue = TaskQueue()
        await task_queue.enqueue_task(
            agent_type="ingestion",
            payload={"bank_id": str(bank.id)},
            priority=1
        )
        
        logger.info(f"Question bank uploaded", extra={
            "bank_id": str(bank.id),
            "subject_id": str(subject_id),
            "faculty_id": str(current_user.id),
            "file_name": file.filename,
            "file_size": file_size
        })
        
        return QuestionBankResponse(
            id=bank.id,
            subject_id=bank.subject_id,
            faculty_id=bank.faculty_id,
            file_name=bank.file_name,
            file_size=bank.file_size,
            status=bank.status,
            upload_date=bank.upload_date,
            processing_error=bank.processing_error,
            questions_count=0
        )
        
    except Exception as e:
        logger.error(f"Question bank upload failed", extra={
            "subject_id": str(subject_id),
            "faculty_id": str(current_user.id),
            "error": str(e)
        })
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload question bank: {str(e)}"
        )


@router.get("/", response_model=List[QuestionBankResponse])
async def list_question_banks(
    subject_id: UUID = None,
    status: QuestionBankStatus = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List question banks.
    
    Faculty can see their own banks.
    Admin can see all banks.
    """
    query = db.query(QuestionBank)
    
    # Filter by role
    if current_user.role == UserRole.FACULTY:
        query = query.filter(QuestionBank.faculty_id == current_user.id)
    
    # Filter by subject
    if subject_id:
        query = query.filter(QuestionBank.subject_id == subject_id)
    
    # Filter by status
    if status:
        query = query.filter(QuestionBank.status == status)
    
    banks = query.order_by(QuestionBank.upload_date.desc()).all()
    
    # Add questions count
    results = []
    for bank in banks:
        questions_count = db.query(Question).filter(Question.bank_id == bank.id).count()
        results.append(QuestionBankResponse(
            id=bank.id,
            subject_id=bank.subject_id,
            faculty_id=bank.faculty_id,
            file_name=bank.file_name,
            file_size=bank.file_size,
            status=bank.status,
            upload_date=bank.upload_date,
            processing_error=bank.processing_error,
            questions_count=questions_count
        ))
    
    return results


@router.get("/{bank_id}", response_model=QuestionBankResponse)
async def get_question_bank(
    bank_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get question bank details"""
    bank = db.query(QuestionBank).filter(QuestionBank.id == bank_id).first()
    
    if not bank:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Question bank {bank_id} not found"
        )
    
    # Check permissions
    if current_user.role == UserRole.FACULTY and bank.faculty_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to access this question bank"
        )
    
    questions_count = db.query(Question).filter(Question.bank_id == bank_id).count()
    
    return QuestionBankResponse(
        id=bank.id,
        subject_id=bank.subject_id,
        faculty_id=bank.faculty_id,
        file_name=bank.file_name,
        file_size=bank.file_size,
        status=bank.status,
        upload_date=bank.upload_date,
        processing_error=bank.processing_error,
        questions_count=questions_count
    )


@router.get("/{bank_id}/questions", response_model=List[QuestionResponse])
async def list_questions(
    bank_id: UUID,
    tags_confirmed: bool = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List questions from a question bank.
    
    Optionally filter by tags_confirmed status.
    """
    # Verify bank exists and user has access
    bank = db.query(QuestionBank).filter(QuestionBank.id == bank_id).first()
    
    if not bank:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Question bank {bank_id} not found"
        )
    
    if current_user.role == UserRole.FACULTY and bank.faculty_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to access this question bank"
        )
    
    # Query questions
    query = db.query(Question).filter(Question.bank_id == bank_id)
    
    if tags_confirmed is not None:
        query = query.filter(Question.tags_confirmed == tags_confirmed)
    
    questions = query.order_by(Question.created_at).all()
    
    return [QuestionResponse.from_orm(q) for q in questions]


@router.patch("/{bank_id}/questions/{question_id}", response_model=QuestionResponse)
async def update_question_tags(
    bank_id: UUID,
    question_id: UUID,
    update_data: QuestionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.FACULTY, UserRole.ADMIN]))
):
    """
    Update question tags.
    
    Faculty can update tags for their own question banks.
    """
    # Verify bank and question exist
    bank = db.query(QuestionBank).filter(QuestionBank.id == bank_id).first()
    
    if not bank:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Question bank {bank_id} not found"
        )
    
    if current_user.role == UserRole.FACULTY and bank.faculty_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to modify this question bank"
        )
    
    question = db.query(Question).filter(
        Question.id == question_id,
        Question.bank_id == bank_id
    ).first()
    
    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Question {question_id} not found in bank {bank_id}"
        )
    
    # Update fields
    update_dict = update_data.dict(exclude_unset=True)
    for field, value in update_dict.items():
        setattr(question, field, value)
    
    db.commit()
    db.refresh(question)
    
    logger.info(f"Question tags updated", extra={
        "question_id": str(question_id),
        "bank_id": str(bank_id),
        "faculty_id": str(current_user.id),
        "updates": update_dict
    })
    
    return QuestionResponse.from_orm(question)


@router.post("/{bank_id}/questions/bulk-tag", response_model=BulkTagResponse)
async def bulk_tag_questions(
    bank_id: UUID,
    bulk_update: BulkTagUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.FACULTY, UserRole.ADMIN]))
):
    """
    Bulk update tags for multiple questions.
    
    Useful for tagging multiple questions with the same unit/topic.
    """
    # Verify bank exists and user has access
    bank = db.query(QuestionBank).filter(QuestionBank.id == bank_id).first()
    
    if not bank:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Question bank {bank_id} not found"
        )
    
    if current_user.role == UserRole.FACULTY and bank.faculty_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to modify this question bank"
        )
    
    # Update questions
    updated_count = 0
    failed_count = 0
    failed_ids = []
    
    update_dict = bulk_update.dict(exclude={'question_ids'}, exclude_unset=True)
    
    for question_id in bulk_update.question_ids:
        try:
            question = db.query(Question).filter(
                Question.id == question_id,
                Question.bank_id == bank_id
            ).first()
            
            if not question:
                failed_count += 1
                failed_ids.append(question_id)
                continue
            
            # Update fields
            for field, value in update_dict.items():
                setattr(question, field, value)
            
            updated_count += 1
            
        except Exception as e:
            logger.error(f"Failed to update question", extra={
                "question_id": str(question_id),
                "error": str(e)
            })
            failed_count += 1
            failed_ids.append(question_id)
    
    db.commit()
    
    logger.info(f"Bulk tag update completed", extra={
        "bank_id": str(bank_id),
        "faculty_id": str(current_user.id),
        "updated_count": updated_count,
        "failed_count": failed_count
    })
    
    return BulkTagResponse(
        updated_count=updated_count,
        failed_count=failed_count,
        failed_ids=failed_ids
    )


@router.delete("/{bank_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_question_bank(
    bank_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.FACULTY, UserRole.ADMIN]))
):
    """
    Delete a question bank and all its questions.
    
    Faculty can delete their own banks.
    Admin can delete any bank.
    """
    bank = db.query(QuestionBank).filter(QuestionBank.id == bank_id).first()
    
    if not bank:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Question bank {bank_id} not found"
        )
    
    if current_user.role == UserRole.FACULTY and bank.faculty_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to delete this question bank"
        )
    
    # Delete from database (cascade will delete questions)
    db.delete(bank)
    db.commit()
    
    logger.info(f"Question bank deleted", extra={
        "bank_id": str(bank_id),
        "faculty_id": str(current_user.id)
    })
    
    return None
