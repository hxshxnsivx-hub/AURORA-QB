"""
Unit tests for ingestion agent and parsers.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from io import BytesIO
import os
import tempfile

from parsers.pdf_parser import PDFParser
from parsers.docx_parser import DOCXParser
from parsers.txt_parser import TXTParser
from parsers.question_extractor import QuestionExtractor
from agents.ingestion_agent import IngestionAgent
from models.question import QuestionBank, Question, QuestionBankStatus, QuestionType, DifficultyLevel


class TestPDFParser:
    """Test PDF parsing functionality"""
    
    @pytest.mark.asyncio
    async def test_parse_valid_pdf(self):
        """Test parsing a valid PDF file"""
        parser = PDFParser()
        
        # Create a temporary PDF file with test content
        with tempfile.NamedTemporaryFile(mode='w', suffix='.pdf', delete=False) as f:
            temp_path = f.name
        
        try:
            # Mock PyPDF2 reader
            with patch('parsers.pdf_parser.PdfReader') as mock_reader:
                mock_page = Mock()
                mock_page.extract_text.return_value = "Question 1: What is Python?\nQuestion 2: Explain OOP."
                mock_reader.return_value.pages = [mock_page]
                
                result = await parser.parse(temp_path)
                
                assert "Question 1" in result
                assert "Question 2" in result
                assert "Python" in result
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
    
    @pytest.mark.asyncio
    async def test_parse_empty_pdf(self):
        """Test parsing an empty PDF"""
        parser = PDFParser()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.pdf', delete=False) as f:
            temp_path = f.name
        
        try:
            with patch('parsers.pdf_parser.PdfReader') as mock_reader:
                mock_page = Mock()
                mock_page.extract_text.return_value = ""
                mock_reader.return_value.pages = [mock_page]
                
                result = await parser.parse(temp_path)
                
                assert result == ""
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
    
    @pytest.mark.asyncio
    async def test_parse_corrupted_pdf(self):
        """Test parsing a corrupted PDF file"""
        parser = PDFParser()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.pdf', delete=False) as f:
            f.write("Not a valid PDF")
            temp_path = f.name
        
        try:
            with patch('parsers.pdf_parser.PdfReader') as mock_reader:
                mock_reader.side_effect = Exception("Invalid PDF")
                
                with pytest.raises(Exception):
                    await parser.parse(temp_path)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)


class TestDOCXParser:
    """Test DOCX parsing functionality"""
    
    @pytest.mark.asyncio
    async def test_parse_valid_docx(self):
        """Test parsing a valid DOCX file"""
        parser = DOCXParser()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.docx', delete=False) as f:
            temp_path = f.name
        
        try:
            with patch('parsers.docx_parser.Document') as mock_doc:
                mock_para1 = Mock()
                mock_para1.text = "Question 1: What is Python?"
                mock_para2 = Mock()
                mock_para2.text = "Question 2: Explain OOP."
                mock_doc.return_value.paragraphs = [mock_para1, mock_para2]
                
                result = await parser.parse(temp_path)
                
                assert "Question 1" in result
                assert "Question 2" in result
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
    
    @pytest.mark.asyncio
    async def test_parse_empty_docx(self):
        """Test parsing an empty DOCX"""
        parser = DOCXParser()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.docx', delete=False) as f:
            temp_path = f.name
        
        try:
            with patch('parsers.docx_parser.Document') as mock_doc:
                mock_doc.return_value.paragraphs = []
                
                result = await parser.parse(temp_path)
                
                assert result == ""
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)


class TestTXTParser:
    """Test TXT parsing functionality"""
    
    @pytest.mark.asyncio
    async def test_parse_valid_txt_utf8(self):
        """Test parsing a valid UTF-8 TXT file"""
        parser = TXTParser()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write("Question 1: What is Python?\nQuestion 2: Explain OOP.")
            temp_path = f.name
        
        try:
            result = await parser.parse(temp_path)
            
            assert "Question 1" in result
            assert "Question 2" in result
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
    
    @pytest.mark.asyncio
    async def test_parse_valid_txt_latin1(self):
        """Test parsing a Latin-1 encoded TXT file"""
        parser = TXTParser()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='latin-1') as f:
            f.write("Question 1: What is Python?")
            temp_path = f.name
        
        try:
            result = await parser.parse(temp_path)
            
            assert "Question 1" in result
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
    
    @pytest.mark.asyncio
    async def test_parse_empty_txt(self):
        """Test parsing an empty TXT file"""
        parser = TXTParser()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            temp_path = f.name
        
        try:
            result = await parser.parse(temp_path)
            
            assert result == ""
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)


class TestQuestionExtractor:
    """Test question extraction logic"""
    
    def test_extract_numbered_questions(self):
        """Test extracting numbered questions (Q1, Q2, etc.)"""
        extractor = QuestionExtractor()
        
        text = """
        Q1. What is Python?
        Python is a programming language.
        
        Q2. Explain OOP.
        OOP stands for Object-Oriented Programming.
        
        Q3. What is a function?
        A function is a reusable block of code.
        """
        
        questions = extractor.extract_questions(text)
        
        assert len(questions) == 3
        assert "What is Python?" in questions[0]
        assert "Explain OOP" in questions[1]
        assert "What is a function?" in questions[2]
    
    def test_extract_question_word_format(self):
        """Test extracting questions with 'Question' keyword"""
        extractor = QuestionExtractor()
        
        text = """
        Question 1: What is Python?
        Python is a programming language.
        
        Question 2: Explain OOP.
        OOP stands for Object-Oriented Programming.
        """
        
        questions = extractor.extract_questions(text)
        
        assert len(questions) == 2
        assert "What is Python?" in questions[0]
        assert "Explain OOP" in questions[1]
    
    def test_extract_parenthesis_format(self):
        """Test extracting questions with (1), (2) format"""
        extractor = QuestionExtractor()
        
        text = """
        (1) What is Python?
        Python is a programming language.
        
        (2) Explain OOP.
        OOP stands for Object-Oriented Programming.
        """
        
        questions = extractor.extract_questions(text)
        
        assert len(questions) == 2
        assert "What is Python?" in questions[0]
        assert "Explain OOP" in questions[1]
    
    def test_extract_no_questions(self):
        """Test text with no recognizable question patterns"""
        extractor = QuestionExtractor()
        
        text = "This is just some random text without any questions."
        
        questions = extractor.extract_questions(text)
        
        # Should return the whole text as one question
        assert len(questions) >= 1
    
    def test_extract_mixed_formats(self):
        """Test extracting questions with mixed formats"""
        extractor = QuestionExtractor()
        
        text = """
        Q1. What is Python?
        
        Question 2: Explain OOP.
        
        (3) What is a function?
        """
        
        questions = extractor.extract_questions(text)
        
        assert len(questions) == 3


class TestIngestionAgent:
    """Test ingestion agent functionality"""
    
    @pytest.mark.asyncio
    async def test_process_valid_bank(self, db_session):
        """Test processing a valid question bank"""
        # Create mock question bank
        bank = QuestionBank(
            subject_id="550e8400-e29b-41d4-a716-446655440000",
            faculty_id="550e8400-e29b-41d4-a716-446655440001",
            file_path="test/path/file.pdf",
            file_name="test.pdf",
            file_size=1024,
            status=QuestionBankStatus.UPLOADED
        )
        db_session.add(bank)
        db_session.commit()
        
        agent = IngestionAgent(db_session)
        
        # Mock dependencies
        with patch('agents.ingestion_agent.download_file') as mock_download, \
             patch.object(agent.parsers['.pdf'], 'parse', new_callable=AsyncMock) as mock_parse, \
             patch.object(agent, '_extract_questions_with_llm', new_callable=AsyncMock) as mock_extract, \
             patch.object(agent, '_suggest_tags', new_callable=AsyncMock) as mock_tags, \
             patch('agents.ingestion_agent.generate_embedding', new_callable=AsyncMock) as mock_embed:
            
            mock_download.return_value = "/tmp/test.pdf"
            mock_parse.return_value = "Q1. What is Python?"
            mock_extract.return_value = ["What is Python?"]
            mock_tags.return_value = {
                "marks": 2,
                "type": "Short Answer",
                "difficulty": "Easy",
                "unit_id": None,
                "topic_id": None
            }
            mock_embed.return_value = [0.1] * 1536
            
            result = await agent.process({"bank_id": str(bank.id)})
            
            assert result["status"] == "completed"
            assert result["questions_extracted"] == 1
            
            # Verify bank status updated
            db_session.refresh(bank)
            assert bank.status == QuestionBankStatus.COMPLETED
    
    @pytest.mark.asyncio
    async def test_process_invalid_bank_id(self, db_session):
        """Test processing with invalid bank ID"""
        agent = IngestionAgent(db_session)
        
        with pytest.raises(ValueError, match="not found"):
            await agent.process({"bank_id": "550e8400-e29b-41d4-a716-446655440099"})
    
    @pytest.mark.asyncio
    async def test_process_missing_bank_id(self, db_session):
        """Test processing without bank ID"""
        agent = IngestionAgent(db_session)
        
        with pytest.raises(ValueError, match="required"):
            await agent.process({})
    
    @pytest.mark.asyncio
    async def test_process_unsupported_format(self, db_session):
        """Test processing unsupported file format"""
        bank = QuestionBank(
            subject_id="550e8400-e29b-41d4-a716-446655440000",
            faculty_id="550e8400-e29b-41d4-a716-446655440001",
            file_path="test/path/file.exe",
            file_name="test.exe",
            file_size=1024,
            status=QuestionBankStatus.UPLOADED
        )
        db_session.add(bank)
        db_session.commit()
        
        agent = IngestionAgent(db_session)
        
        with patch('agents.ingestion_agent.download_file') as mock_download:
            mock_download.return_value = "/tmp/test.exe"
            
            result = await agent.execute_task({"bank_id": str(bank.id)})
            
            assert result["success"] is False
            assert "Unsupported file format" in result["error"]
            
            # Verify bank status updated to failed
            db_session.refresh(bank)
            assert bank.status == QuestionBankStatus.FAILED
    
    @pytest.mark.asyncio
    async def test_llm_question_detection(self, db_session):
        """Test LLM-based question boundary detection"""
        agent = IngestionAgent(db_session)
        
        raw_text = "Some text with questions but no clear markers."
        
        with patch.object(agent.llm_client, 'generate', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = '[{"question": "Q1"}, {"question": "Q2"}]'
            
            questions = await agent._llm_question_detection(raw_text)
            
            assert len(questions) == 2
            assert questions[0] == "Q1"
            assert questions[1] == "Q2"
    
    @pytest.mark.asyncio
    async def test_llm_question_detection_fallback(self, db_session):
        """Test fallback when LLM detection fails"""
        agent = IngestionAgent(db_session)
        
        raw_text = "Q1. What is Python?\nQ2. Explain OOP."
        
        with patch.object(agent.llm_client, 'generate', new_callable=AsyncMock) as mock_llm:
            mock_llm.side_effect = Exception("LLM error")
            
            questions = await agent._llm_question_detection(raw_text)
            
            # Should fallback to pattern-based extraction
            assert len(questions) >= 1
    
    @pytest.mark.asyncio
    async def test_suggest_tags(self, db_session):
        """Test LLM tag suggestion"""
        agent = IngestionAgent(db_session)
        
        question_text = "What is Python? Explain in detail."
        subject_id = "550e8400-e29b-41d4-a716-446655440000"
        
        with patch.object(agent.llm_client, 'generate', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = '{"marks": 5, "type": "Long Answer", "difficulty": "Medium", "topic": "Python Basics", "unit": "Introduction"}'
            
            tags = await agent._suggest_tags(question_text, subject_id)
            
            assert tags["marks"] == 5
            assert tags["type"] == "Long Answer"
            assert tags["difficulty"] == "Medium"
    
    @pytest.mark.asyncio
    async def test_suggest_tags_fallback(self, db_session):
        """Test fallback when tag suggestion fails"""
        agent = IngestionAgent(db_session)
        
        question_text = "What is Python?"
        subject_id = "550e8400-e29b-41d4-a716-446655440000"
        
        with patch.object(agent.llm_client, 'generate', new_callable=AsyncMock) as mock_llm:
            mock_llm.side_effect = Exception("LLM error")
            
            tags = await agent._suggest_tags(question_text, subject_id)
            
            # Should return default tags
            assert tags["marks"] == 1
            assert tags["type"] == "Short Answer"
            assert tags["difficulty"] == "Medium"
    
    @pytest.mark.asyncio
    async def test_extract_questions_with_llm_pattern_success(self, db_session):
        """Test question extraction using pattern matching"""
        agent = IngestionAgent(db_session)
        
        raw_text = "Q1. Question 1\nQ2. Question 2\nQ3. Question 3\nQ4. Question 4"
        
        questions = await agent._extract_questions_with_llm(raw_text)
        
        # Should use pattern-based extraction (>= 3 questions)
        assert len(questions) >= 3
    
    @pytest.mark.asyncio
    async def test_extract_questions_with_llm_fallback(self, db_session):
        """Test question extraction falling back to LLM"""
        agent = IngestionAgent(db_session)
        
        raw_text = "Some text with only one or two questions."
        
        with patch.object(agent, '_llm_question_detection', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = ["Question 1", "Question 2"]
            
            questions = await agent._extract_questions_with_llm(raw_text)
            
            # Should use LLM detection (< 3 questions from pattern)
            mock_llm.assert_called_once()
