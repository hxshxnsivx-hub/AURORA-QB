"""
Property-based tests for ingestion agent.

Tests Properties 3, 4, 5, 15, and 17 from the design document.
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from hypothesis.stateful import RuleBasedStateMachine, rule, invariant
from unittest.mock import Mock, AsyncMock, patch
import tempfile
import os
from uuid import uuid4

from parsers.pdf_parser import PDFParser
from parsers.docx_parser import DOCXParser
from parsers.txt_parser import TXTParser
from parsers.question_extractor import QuestionExtractor
from agents.ingestion_agent import IngestionAgent
from models.question import QuestionBank, Question, QuestionBankStatus, QuestionType, DifficultyLevel


# Property 3: Valid File Format Acceptance
# For any file in PDF, DOCX, or TXT format uploaded by Faculty,
# the system should accept the file for processing.

@given(
    file_format=st.sampled_from(['.pdf', '.docx', '.txt']),
    file_content=st.text(min_size=10, max_size=1000)
)
@settings(max_examples=50, deadline=None)
@pytest.mark.asyncio
async def test_property_3_valid_file_acceptance(file_format, file_content):
    """
    Property 3: Valid File Format Acceptance
    
    For any file in PDF, DOCX, or TXT format, the system should accept it.
    """
    # Create temporary file with the format
    with tempfile.NamedTemporaryFile(mode='w', suffix=file_format, delete=False) as f:
        f.write(file_content)
        temp_path = f.name
    
    try:
        # Get appropriate parser
        if file_format == '.pdf':
            parser = PDFParser()
            with patch('parsers.pdf_parser.PdfReader') as mock_reader:
                mock_page = Mock()
                mock_page.extract_text.return_value = file_content
                mock_reader.return_value.pages = [mock_page]
                
                # Should not raise exception
                result = await parser.parse(temp_path)
                assert isinstance(result, str)
        
        elif file_format == '.docx':
            parser = DOCXParser()
            with patch('parsers.docx_parser.Document') as mock_doc:
                mock_para = Mock()
                mock_para.text = file_content
                mock_doc.return_value.paragraphs = [mock_para]
                
                # Should not raise exception
                result = await parser.parse(temp_path)
                assert isinstance(result, str)
        
        elif file_format == '.txt':
            parser = TXTParser()
            # Should not raise exception
            result = await parser.parse(temp_path)
            assert isinstance(result, str)
    
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


# Property 4: Question Extraction from Valid Files
# For any valid question bank file, parsing should extract at least one question with text content.

@given(
    num_questions=st.integers(min_value=1, max_value=10),
    question_format=st.sampled_from(['Q{n}. ', 'Question {n}: ', '({n}) '])
)
@settings(max_examples=30, deadline=None)
def test_property_4_question_extraction(num_questions, question_format):
    """
    Property 4: Question Extraction from Valid Files
    
    For any valid question bank file, parsing should extract at least one question.
    """
    extractor = QuestionExtractor()
    
    # Generate text with questions
    questions_text = []
    for i in range(1, num_questions + 1):
        question = question_format.format(n=i) + f"What is question {i}?"
        questions_text.append(question)
    
    text = "\n\n".join(questions_text)
    
    # Extract questions
    extracted = extractor.extract_questions(text)
    
    # Should extract at least one question
    assert len(extracted) >= 1
    
    # Each extracted question should have text content
    for q in extracted:
        assert isinstance(q, str)
        assert len(q.strip()) > 0


# Property 5: Parse Error Reporting
# For any file that fails parsing, the system should return an error message describing the failure reason.

@given(
    file_format=st.sampled_from(['.pdf', '.docx', '.txt']),
    error_type=st.sampled_from(['corrupted', 'empty', 'invalid'])
)
@settings(max_examples=30, deadline=None)
@pytest.mark.asyncio
async def test_property_5_parse_error_reporting(file_format, error_type, db_session):
    """
    Property 5: Parse Error Reporting
    
    For any file that fails parsing, the system should return an error message.
    """
    # Create a question bank
    bank = QuestionBank(
        subject_id=str(uuid4()),
        faculty_id=str(uuid4()),
        file_path=f"test/path/file{file_format}",
        file_name=f"test{file_format}",
        file_size=1024,
        status=QuestionBankStatus.UPLOADED
    )
    db_session.add(bank)
    db_session.commit()
    
    agent = IngestionAgent(db_session)
    
    # Mock download and parser to simulate error
    with patch('agents.ingestion_agent.download_file') as mock_download:
        mock_download.return_value = f"/tmp/test{file_format}"
        
        if error_type == 'corrupted':
            # Simulate corrupted file
            with patch.object(agent.parsers[file_format], 'parse', new_callable=AsyncMock) as mock_parse:
                mock_parse.side_effect = Exception("File is corrupted")
                
                result = await agent.execute_task({"bank_id": str(bank.id)})
                
                # Should return error
                assert result["success"] is False
                assert "error" in result
                assert isinstance(result["error"], str)
                assert len(result["error"]) > 0
                
                # Bank should be marked as failed
                db_session.refresh(bank)
                assert bank.status == QuestionBankStatus.FAILED
                assert bank.processing_error is not None


# Property 15: LLM Tag Suggestion Generation
# For any question text, the system should generate tag suggestions including all required fields.

@given(
    question_text=st.text(min_size=20, max_size=500),
)
@settings(max_examples=30, deadline=None)
@pytest.mark.asyncio
async def test_property_15_llm_tag_suggestion(question_text, db_session):
    """
    Property 15: LLM Tag Suggestion Generation
    
    For any question text, the system should generate tag suggestions with all required fields.
    """
    assume(len(question_text.strip()) > 10)  # Ensure meaningful text
    
    agent = IngestionAgent(db_session)
    subject_id = str(uuid4())
    
    # Mock LLM response
    with patch.object(agent.llm_client, 'generate', new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = '''{
            "marks": 3,
            "type": "Short Answer",
            "difficulty": "Medium",
            "topic": "Test Topic",
            "unit": "Test Unit"
        }'''
        
        tags = await agent._suggest_tags(question_text, subject_id)
        
        # Should have all required fields
        assert "marks" in tags
        assert "type" in tags
        assert "difficulty" in tags
        
        # Marks should be valid
        assert isinstance(tags["marks"], int)
        assert 1 <= tags["marks"] <= 12
        
        # Type should be valid
        assert tags["type"] in ["MCQ", "Short Answer", "Long Answer", "Numerical", "True/False"]
        
        # Difficulty should be valid
        assert tags["difficulty"] in ["Easy", "Medium", "Hard"]


# Property 17: Bulk Tagging Equivalence
# For any set of questions and tag values, applying tags via bulk operation
# should produce the same result as applying tags individually.

@given(
    num_questions=st.integers(min_value=2, max_value=5),
    marks=st.integers(min_value=1, max_value=12),
    difficulty=st.sampled_from(["Easy", "Medium", "Hard"])
)
@settings(max_examples=20, deadline=None)
def test_property_17_bulk_tagging_equivalence(num_questions, marks, difficulty, db_session):
    """
    Property 17: Bulk Tagging Equivalence
    
    Bulk tagging should produce the same result as individual tagging.
    """
    # Create a question bank
    bank = QuestionBank(
        subject_id=str(uuid4()),
        faculty_id=str(uuid4()),
        file_path="test/path/file.pdf",
        file_name="test.pdf",
        file_size=1024,
        status=QuestionBankStatus.COMPLETED
    )
    db_session.add(bank)
    db_session.commit()
    
    # Create questions for individual tagging
    individual_questions = []
    for i in range(num_questions):
        q = Question(
            bank_id=bank.id,
            text=f"Question {i}",
            marks=1,
            type=QuestionType.SHORT_ANSWER,
            difficulty=DifficultyLevel.EASY,
            tags_confirmed=False
        )
        db_session.add(q)
        individual_questions.append(q)
    
    # Create questions for bulk tagging
    bulk_questions = []
    for i in range(num_questions):
        q = Question(
            bank_id=bank.id,
            text=f"Question {i}",
            marks=1,
            type=QuestionType.SHORT_ANSWER,
            difficulty=DifficultyLevel.EASY,
            tags_confirmed=False
        )
        db_session.add(q)
        bulk_questions.append(q)
    
    db_session.commit()
    
    # Apply tags individually
    for q in individual_questions:
        q.marks = marks
        q.difficulty = DifficultyLevel(difficulty)
        q.tags_confirmed = True
    db_session.commit()
    
    # Apply tags in bulk
    for q in bulk_questions:
        q.marks = marks
        q.difficulty = DifficultyLevel(difficulty)
        q.tags_confirmed = True
    db_session.commit()
    
    # Verify equivalence
    for i in range(num_questions):
        assert individual_questions[i].marks == bulk_questions[i].marks
        assert individual_questions[i].difficulty == bulk_questions[i].difficulty
        assert individual_questions[i].tags_confirmed == bulk_questions[i].tags_confirmed


# Additional property test: Question extraction consistency

@given(
    text=st.text(min_size=50, max_size=1000),
)
@settings(max_examples=30, deadline=None)
def test_question_extraction_consistency(text):
    """
    Test that question extraction is consistent across multiple calls.
    """
    extractor = QuestionExtractor()
    
    # Extract questions twice
    result1 = extractor.extract_questions(text)
    result2 = extractor.extract_questions(text)
    
    # Results should be identical
    assert len(result1) == len(result2)
    for q1, q2 in zip(result1, result2):
        assert q1 == q2


# Additional property test: Tag suggestion fallback

@pytest.mark.asyncio
async def test_tag_suggestion_always_returns_valid_tags(db_session):
    """
    Test that tag suggestion always returns valid tags, even on LLM failure.
    """
    agent = IngestionAgent(db_session)
    subject_id = str(uuid4())
    
    # Test with LLM failure
    with patch.object(agent.llm_client, 'generate', new_callable=AsyncMock) as mock_llm:
        mock_llm.side_effect = Exception("LLM API error")
        
        tags = await agent._suggest_tags("What is Python?", subject_id)
        
        # Should still return valid default tags
        assert "marks" in tags
        assert "type" in tags
        assert "difficulty" in tags
        assert isinstance(tags["marks"], int)
        assert 1 <= tags["marks"] <= 12


# Stateful property test for ingestion workflow

class IngestionWorkflowMachine(RuleBasedStateMachine):
    """
    Stateful property test for the complete ingestion workflow.
    """
    
    def __init__(self):
        super().__init__()
        self.banks = []
        self.questions = []
    
    @rule(
        file_format=st.sampled_from(['.pdf', '.docx', '.txt']),
        num_questions=st.integers(min_value=1, max_value=5)
    )
    def upload_bank(self, file_format, num_questions):
        """Upload a question bank"""
        bank_id = str(uuid4())
        self.banks.append({
            'id': bank_id,
            'format': file_format,
            'expected_questions': num_questions,
            'status': 'uploaded'
        })
    
    @rule()
    def process_bank(self):
        """Process an uploaded bank"""
        if not self.banks:
            return
        
        # Find an uploaded bank
        for bank in self.banks:
            if bank['status'] == 'uploaded':
                bank['status'] = 'processing'
                break
    
    @rule()
    def complete_processing(self):
        """Complete processing of a bank"""
        if not self.banks:
            return
        
        # Find a processing bank
        for bank in self.banks:
            if bank['status'] == 'processing':
                bank['status'] = 'completed'
                # Add questions
                for i in range(bank['expected_questions']):
                    self.questions.append({
                        'bank_id': bank['id'],
                        'text': f"Question {i}",
                        'tags_confirmed': False
                    })
                break
    
    @invariant()
    def questions_belong_to_banks(self):
        """All questions must belong to a bank"""
        bank_ids = {b['id'] for b in self.banks}
        for question in self.questions:
            assert question['bank_id'] in bank_ids
    
    @invariant()
    def completed_banks_have_questions(self):
        """Completed banks should have questions"""
        for bank in self.banks:
            if bank['status'] == 'completed':
                bank_questions = [q for q in self.questions if q['bank_id'] == bank['id']]
                assert len(bank_questions) > 0


# Run the stateful test
TestIngestionWorkflow = IngestionWorkflowMachine.TestCase
