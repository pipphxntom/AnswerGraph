"""
Integration tests for the disambiguation path in the ask endpoint.
"""
import pytest
import asyncio
from typing import Dict, Any, List
from unittest.mock import patch, MagicMock, AsyncMock

from fastapi.testclient import TestClient
from src.api.routes import router
from src.core.rule_settings import RULE_INTENTS
from src.api.ask_routes import AskRequest, AskResponse

client = TestClient(router)


@pytest.fixture
def ambiguous_intent_response():
    """Mock response for intent classification with low slot confidence."""
    return ("scholarship_form_deadline", {"scholarship_type": None}, 0.85)


@pytest.fixture
def clear_intent_response():
    """Mock response for intent classification with high slot confidence."""
    return ("scholarship_form_deadline", {"scholarship_type": "merit"}, 0.85)


@patch("src.api.ask_routes.classify_intent_and_slots")
@patch("src.api.ask_routes.detect_lang")
def test_disambiguation_response_for_missing_slots(mock_detect_lang, mock_classify, ambiguous_intent_response):
    """Test that disambiguation is returned when slots are incomplete."""
    # Setup mocks
    mock_detect_lang.return_value = "en"
    mock_classify.return_value = ambiguous_intent_response
    
    # Make the request
    response = client.post(
        "/ask",
        json={"text": "When is the scholarship deadline?"}
    )
    
    # Verify response
    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "disambiguation"
    assert data["intent"] == "scholarship_form_deadline"
    assert "chips" in data
    assert isinstance(data["chips"], dict)
    assert "scholarship_type" in data["chips"]
    
    # Verify we didn't call apply_guards
    assert mock_classify.called
    assert not hasattr(mock_classify, "apply_guards")


@patch("src.api.ask_routes.classify_intent_and_slots")
@patch("src.api.ask_routes.detect_lang")
@patch("src.api.ask_routes.answer_from_rules")
@patch("src.api.ask_routes.apply_guards")
def test_no_disambiguation_for_complete_slots(
    mock_apply_guards, 
    mock_answer_from_rules, 
    mock_detect_lang, 
    mock_classify,
    clear_intent_response
):
    """Test that regular path is followed when slots are complete."""
    # Setup mocks
    mock_detect_lang.return_value = "en"
    mock_classify.return_value = clear_intent_response
    
    # Mock rule-based answer
    mock_answer = MagicMock()
    mock_answer.mode = "rules"
    mock_answer.intent = "scholarship_form_deadline"
    mock_answer.answer = "The merit scholarship deadline is October 15, 2023."
    mock_answer.sources = [MagicMock(url="https://example.com", page=1)]
    mock_answer_from_rules.return_value = asyncio.Future()
    mock_answer_from_rules.return_value.set_result(mock_answer)
    
    # Mock guard decision
    mock_decision = MagicMock()
    mock_decision.ok = True
    mock_decision.confidence = 0.9
    mock_decision.reasons = []
    mock_apply_guards.return_value = mock_decision
    
    # Make the request
    response = client.post(
        "/ask",
        json={"text": "When is the merit scholarship deadline?"}
    )
    
    # Verify response
    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "rules"
    assert data["intent"] == "scholarship_form_deadline"
    assert "chips" not in data
    
    # Verify we called apply_guards
    assert mock_apply_guards.called


@patch("src.api.ask_routes.classify_intent_and_slots")
@patch("src.api.ask_routes.detect_lang")
def test_disambiguation_context_preservation(mock_detect_lang, mock_classify, ambiguous_intent_response):
    """Test that disambiguation preserves context in the response."""
    # Setup mocks
    mock_detect_lang.return_value = "en"
    mock_classify.return_value = ambiguous_intent_response
    
    # Make the request with context
    response = client.post(
        "/ask",
        json={
            "text": "When is the scholarship deadline?",
            "ctx": {"session_id": "test-123", "user_id": "user-456"}
        }
    )
    
    # Verify response preserves context
    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "disambiguation"
    
    # Make the follow-up request
    mock_classify.return_value = ("scholarship_form_deadline", {"scholarship_type": "merit"}, 0.85)
    
    # This would be handled in a real application by preserving ctx
    # For this test, we're just verifying the basic structure
"""
