"""
Unit tests for the rules-based answer module.
"""
import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import MagicMock, AsyncMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from src.answers.rules_path import (
    answer_from_rules, 
    NoAnswer,
    handle_fee_deadline,
    handle_scholarship_deadline,
    handle_timetable_release,
    handle_hostel_fee,
    handle_exam_deadline
)


# Test data
mock_fee_row = MagicMock()
mock_fee_row.title = "Academic Fee Policy"
mock_fee_row.effective_from = datetime.now() - timedelta(days=30)
mock_fee_row.details = "Fee details for B.Tech program page 5"
mock_fee_row.deadline = datetime.now() + timedelta(days=15)
mock_fee_row.url = "https://example.com/policies/fee_policy.pdf"
mock_fee_row.source_title = "Fee Structure 2025"
mock_fee_row.page_count = 10

mock_scholarship_row = MagicMock()
mock_scholarship_row.title = "Scholarship Policy"
mock_scholarship_row.effective_from = datetime.now() - timedelta(days=45)
mock_scholarship_row.details = "Merit scholarship details page 8"
mock_scholarship_row.deadline = datetime.now() + timedelta(days=30)
mock_scholarship_row.url = "https://example.com/policies/scholarship_policy.pdf"
mock_scholarship_row.source_title = "Scholarship Guidelines 2025"
mock_scholarship_row.page_count = 15

mock_timetable_row = MagicMock()
mock_timetable_row.title = "Academic Calendar"
mock_timetable_row.effective_from = datetime.now() - timedelta(days=60)
mock_timetable_row.details = "Timetable release for B.Tech program page 3"
mock_timetable_row.release_date = datetime.now() + timedelta(days=7)
mock_timetable_row.url = "https://example.com/policies/academic_calendar.pdf"
mock_timetable_row.source_title = "Academic Calendar 2025"
mock_timetable_row.page_count = 20

mock_hostel_row = MagicMock()
mock_hostel_row.title = "Hostel Policy"
mock_hostel_row.effective_from = datetime.now() - timedelta(days=90)
mock_hostel_row.details = "Hostel fee details for North Block page 12"
mock_hostel_row.deadline = datetime.now() + timedelta(days=45)
mock_hostel_row.url = "https://example.com/policies/hostel_policy.pdf"
mock_hostel_row.source_title = "Hostel Regulations 2025"
mock_hostel_row.page_count = 25

mock_exam_row = MagicMock()
mock_exam_row.title = "Examination Policy"
mock_exam_row.effective_from = datetime.now() - timedelta(days=15)
mock_exam_row.details = "Final exam form details for B.Tech program semester 4 page 7"
mock_exam_row.deadline = datetime.now() + timedelta(days=10)
mock_exam_row.url = "https://example.com/policies/exam_policy.pdf"
mock_exam_row.source_title = "Examination Guidelines 2025"
mock_exam_row.page_count = 18


@pytest.fixture
def mock_session():
    """Create a mock database session."""
    session = AsyncMock(spec=AsyncSession)
    
    # Configure execute to return different mock results based on query content
    async def mock_execute(query):
        query_str = str(query)
        
        result = MagicMock()
        
        if "Policy.category == 'fees'" in query_str:
            result.fetchone.return_value = mock_fee_row
        elif "Policy.category == 'scholarship'" in query_str:
            result.fetchone.return_value = mock_scholarship_row
        elif "Procedure.type == 'timetable'" in query_str:
            result.fetchone.return_value = mock_timetable_row
        elif "Policy.category == 'hostel'" in query_str:
            result.fetchone.return_value = mock_hostel_row
        elif "Policy.category == 'examination'" in query_str:
            result.fetchone.return_value = mock_exam_row
        else:
            result.fetchone.return_value = None
            
        return result
    
    session.execute.side_effect = mock_execute
    return session


@pytest.mark.asyncio
async def test_fee_deadline(mock_session):
    """Test fee deadline handler."""
    slots = {"program": "B.Tech", "semester": "4"}
    result = await handle_fee_deadline(slots, mock_session)
    
    # Check response structure
    assert result.answer is not None
    assert "B.Tech" in result.answer
    assert "semester 4" in result.answer
    assert "deadline" in result.fields
    assert result.fields["program"] == "B.Tech"
    assert result.fields["semester"] == "4"
    assert result.source["url"] == mock_fee_row.url
    assert result.source["title"] == mock_fee_row.source_title
    
    # Verify the session was used correctly
    mock_session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_fee_deadline_missing_program(mock_session):
    """Test fee deadline handler with missing program."""
    slots = {"semester": "4"}
    
    with pytest.raises(NoAnswer):
        await handle_fee_deadline(slots, mock_session)


@pytest.mark.asyncio
async def test_scholarship_deadline(mock_session):
    """Test scholarship deadline handler."""
    slots = {"scholarship_type": "Merit"}
    result = await handle_scholarship_deadline(slots, mock_session)
    
    # Check response structure
    assert result.answer is not None
    assert "Merit" in result.answer
    assert "scholarship_type" in result.fields
    assert result.fields["scholarship_type"] == "Merit"
    assert result.source["url"] == mock_scholarship_row.url


@pytest.mark.asyncio
async def test_timetable_release(mock_session):
    """Test timetable release handler."""
    slots = {"program": "B.Tech", "semester": "3"}
    result = await handle_timetable_release(slots, mock_session)
    
    # Check response structure
    assert result.answer is not None
    assert "B.Tech" in result.answer
    assert "semester 3" in result.answer
    assert "release_date" in result.fields
    assert result.source["url"] == mock_timetable_row.url


@pytest.mark.asyncio
async def test_hostel_fee(mock_session):
    """Test hostel fee handler."""
    slots = {"hostel_name": "North Block"}
    result = await handle_hostel_fee(slots, mock_session)
    
    # Check response structure
    assert result.answer is not None
    assert "North Block" in result.answer
    assert "deadline" in result.fields
    assert result.fields["hostel_name"] == "North Block"
    assert result.source["url"] == mock_hostel_row.url
    assert result.source["page"] == 12  # Extracted from details


@pytest.mark.asyncio
async def test_exam_deadline(mock_session):
    """Test exam form deadline handler."""
    slots = {"exam_type": "Final", "program": "B.Tech", "semester": "4"}
    result = await handle_exam_deadline(slots, mock_session)
    
    # Check response structure
    assert result.answer is not None
    assert "Final" in result.answer
    assert "B.Tech" in result.answer
    assert "semester 4" in result.answer
    assert "deadline" in result.fields
    assert result.fields["exam_type"] == "Final"
    assert result.source["url"] == mock_exam_row.url


@pytest.mark.asyncio
async def test_answer_from_rules_router(mock_session):
    """Test the main answer_from_rules router function."""
    # Test valid intent routing
    intent = "fee_deadline"
    slots = {"program": "B.Tech", "semester": "4"}
    
    with patch("src.answers.rules_path.handle_fee_deadline") as mock_handler:
        mock_handler.return_value = "Mock Answer"
        result = await answer_from_rules(intent, slots, mock_session)
        mock_handler.assert_called_once_with(slots, mock_session)
    
    # Test invalid intent
    with pytest.raises(NoAnswer):
        await answer_from_rules("invalid_intent", slots, mock_session)


if __name__ == "__main__":
    asyncio.run(pytest.main(["-xvs", __file__]))
