"""
End-to-end API tests for the ask endpoint.
"""
import pytest
import asyncio
from typing import Dict, Any, List
from unittest.mock import patch, MagicMock, AsyncMock

from fastapi.testclient import TestClient
from src.api.routes import router
from src.schemas.answer import AnswerContract, SourceRef, GuardDecision

client = TestClient(router)


@pytest.fixture
def mock_rule_answer():
    """Create a mock rule-based answer."""
    answer = MagicMock()
    answer.mode = "rules"
    answer.intent = "fee_deadline"
    answer.answer = "The fee deadline for BTech is October 31, 2023."
    answer.sources = [
        SourceRef(
            url="https://example.edu/policies/fees",
            page=5,
            title="Fee Policy 2023",
            updated_at="2023-08-15",
            policy_id="fee-2023"
        )
    ]
    answer.evidence_texts = [
        "All BTech students must pay their fees by October 31, 2023.",
        "Late payment will incur a penalty of 5% per week."
    ]
    return answer


@pytest.fixture
def mock_rag_answer():
    """Create a mock RAG-based answer."""
    answer = MagicMock()
    answer.mode = "rag"
    answer.intent = "freeform"
    answer.answer = "The MBA program has a total of 4 semesters spread over 2 years."
    answer.sources = [
        SourceRef(
            url="https://example.edu/programs/mba",
            page=3,
            title="MBA Program Structure",
            updated_at="2023-07-10",
            policy_id="mba-structure-2023"
        )
    ]
    answer.evidence_texts = [
        "The MBA program at our university is a 2-year program with 4 semesters.",
        "Each semester consists of 5-6 courses with a total of 20 credits."
    ]
    return answer


@pytest.fixture
def mock_guard_success():
    """Create a mock successful guard decision."""
    decision = MagicMock()
    decision.ok = True
    decision.confidence = 0.95
    decision.reasons = []
    return decision


@pytest.fixture
def mock_guard_failure():
    """Create a mock failed guard decision."""
    decision = MagicMock()
    decision.ok = False
    decision.confidence = 0.4
    decision.reasons = ["no_citation"]
    return decision


@patch("src.api.ask_routes.classify_intent_and_slots")
@patch("src.api.ask_routes.detect_lang")
@patch("src.api.ask_routes.answer_from_rules")
@patch("src.api.ask_routes.apply_guards")
def test_successful_rule_based_answer(
    mock_apply_guards, 
    mock_answer_from_rules, 
    mock_detect_lang, 
    mock_classify,
    mock_rule_answer,
    mock_guard_success
):
    """Test a successful rule-based answer flow."""
    # Setup mocks
    mock_detect_lang.return_value = "en"
    mock_classify.return_value = ("fee_deadline", {"program": "BTech"}, 0.9)
    
    mock_answer_from_rules.return_value = asyncio.Future()
    mock_answer_from_rules.return_value.set_result(mock_rule_answer)
    
    mock_apply_guards.return_value = mock_guard_success
    
    # Make the request
    response = client.post(
        "/ask",
        json={"text": "What is the fee deadline for BTech?"}
    )
    
    # Verify response
    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "rules"
    assert data["intent"] == "fee_deadline"
    assert data["answer"] == mock_rule_answer.answer
    assert len(data["sources"]) == 1
    assert data["sources"][0]["url"] == "https://example.edu/policies/fees"
    assert data["sources"][0]["page"] == 5
    
    # Verify guards were applied
    assert mock_apply_guards.called


@patch("src.api.ask_routes.classify_intent_and_slots")
@patch("src.api.ask_routes.detect_lang")
@patch("src.api.ask_routes.retrieve_documents")
@patch("src.api.ask_routes.rerank_documents")
@patch("src.api.ask_routes.cross_encode_rerank")
@patch("src.api.ask_routes.compose_rag_answer")
@patch("src.api.ask_routes.apply_guards")
def test_successful_rag_based_answer(
    mock_apply_guards,
    mock_compose_rag_answer,
    mock_cross_encode,
    mock_rerank,
    mock_retrieve,
    mock_detect_lang,
    mock_classify,
    mock_rag_answer,
    mock_guard_success
):
    """Test a successful RAG-based answer flow."""
    # Setup mocks
    mock_detect_lang.return_value = "en"
    mock_classify.return_value = ("freeform", {}, 0.9)
    
    # Mock retrieval and reranking
    mock_retrieve.return_value = asyncio.Future()
    mock_retrieve.return_value.set_result([{"id": 1, "content": "Test content"}])
    
    mock_rerank.return_value = [{"id": 1, "content": "Test content", "score": 0.9}]
    mock_cross_encode.return_value = [{"id": 1, "content": "Test content", "score": 0.95}]
    
    # Mock RAG answer
    mock_compose_rag_answer.return_value = asyncio.Future()
    mock_compose_rag_answer.return_value.set_result(mock_rag_answer)
    
    mock_apply_guards.return_value = mock_guard_success
    
    # Make the request
    response = client.post(
        "/ask",
        json={"text": "How many semesters are there in MBA?"}
    )
    
    # Verify response
    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "rag"
    assert data["intent"] == "freeform"
    assert data["answer"] == mock_rag_answer.answer
    assert len(data["sources"]) == 1
    
    # Verify the full RAG pipeline was executed
    assert mock_retrieve.called
    assert mock_rerank.called
    assert mock_cross_encode.called
    assert mock_compose_rag_answer.called
    assert mock_apply_guards.called


@patch("src.api.ask_routes.classify_intent_and_slots")
@patch("src.api.ask_routes.detect_lang")
@patch("src.api.ask_routes.answer_from_rules")
@patch("src.api.ask_routes.apply_guards")
@patch("src.api.ask_routes.create_ticket_if_enabled")
def test_failed_guard_creates_ticket(
    mock_create_ticket,
    mock_apply_guards,
    mock_answer_from_rules,
    mock_detect_lang,
    mock_classify,
    mock_rule_answer,
    mock_guard_failure
):
    """Test that a failed guard check creates a ticket and returns fallback."""
    # Setup mocks
    mock_detect_lang.return_value = "en"
    mock_classify.return_value = ("fee_deadline", {"program": "BTech"}, 0.9)
    
    mock_answer_from_rules.return_value = asyncio.Future()
    mock_answer_from_rules.return_value.set_result(mock_rule_answer)
    
    mock_apply_guards.return_value = mock_guard_failure
    
    # Mock ticket creation
    mock_create_ticket.return_value = asyncio.Future()
    mock_create_ticket.return_value.set_result("TICKET-123")
    
    # Make the request
    response = client.post(
        "/ask",
        json={"text": "What is the fee deadline for BTech?"}
    )
    
    # Verify response
    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "fallback"
    assert "reasons" in data
    assert data["reasons"] == ["no_citation"]
    assert data["ticket_id"] == "TICKET-123"
    
    # Verify ticket was created
    assert mock_create_ticket.called
    

@patch("src.api.ask_routes.classify_intent_and_slots")
@patch("src.api.ask_routes.detect_lang")
def test_unsupported_language(mock_detect_lang, mock_classify):
    """Test that an unsupported language returns a fallback."""
    # Setup mocks
    mock_detect_lang.return_value = "fr"  # French, not supported
    
    # Make the request
    response = client.post(
        "/ask",
        json={"text": "Quand est la date limite pour les frais?"}
    )
    
    # Verify response
    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "fallback"
    assert "reasons" in data
    assert "lang_mismatch" in data["reasons"]
"""
