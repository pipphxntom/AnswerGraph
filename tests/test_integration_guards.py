"""
Integration tests for the guard system with both rule-based and RAG answers.
"""
import pytest
import asyncio
from typing import Dict, Any, List
from unittest.mock import patch, MagicMock, AsyncMock

from src.schemas.answer import AnswerContract, SourceRef, GuardDecision
from src.rag.guards import apply_guards
from src.answers.rules_path import answer_from_rules
from src.rag.composer import compose_rag_answer


class MockSession:
    """Mock AsyncSession for testing."""
    
    def __init__(self):
        self.execute_results = {}
    
    def set_execute_results(self, key, value):
        self.execute_results[key] = value
    
    async def execute(self, statement):
        """Return mock results based on the statement."""
        # In a real test, you would parse the statement to determine what to return
        return MagicMock(scalars=lambda: MagicMock(all=lambda: self.execute_results.get("all", [])))


@pytest.fixture
def mock_session():
    """Create a mock database session."""
    return MockSession()


@pytest.fixture
def rule_answer_contract():
    """Create a sample rule-based answer contract."""
    return AnswerContract(
        mode="rules",
        intent="fee_deadline",
        answer="The fee deadline for BTech is October 31, 2023.",
        fields={"deadline": "October 31, 2023", "program": "BTech"},
        sources=[
            SourceRef(
                url="https://example.edu/policies/fees",
                page=5,
                title="Fee Policy 2023",
                updated_at="2023-08-15",
                policy_id="fee-2023"
            )
        ],
        evidence_texts=[
            "All BTech students must pay their fees by October 31, 2023.",
            "Late payment will incur a penalty of 5% per week."
        ],
        ctx={"program": "BTech"}
    )


@pytest.fixture
def rag_answer_contract():
    """Create a sample RAG answer contract."""
    return AnswerContract(
        mode="rag",
        intent="freeform",
        answer="The scholarship application deadline is September 15, 2023 for all students.",
        fields={},
        sources=[
            SourceRef(
                url="https://example.edu/policies/scholarships",
                page=12,
                title="Scholarship Guide 2023",
                updated_at="2023-07-20",
                policy_id="schol-2023"
            )
        ],
        evidence_texts=[
            "The scholarship application deadline for all undergraduate students is September 15, 2023.",
            "Applications must be submitted online through the student portal."
        ],
        ctx={}
    )


@pytest.fixture
def rag_answer_uncited():
    """Create a RAG answer contract without proper citation."""
    return AnswerContract(
        mode="rag",
        intent="freeform",
        answer="The scholarship application deadline is September 15, 2023 for all students.",
        fields={},
        sources=[],  # Empty sources list
        evidence_texts=[
            "The scholarship application deadline for all undergraduate students is September 15, 2023.",
            "Applications must be submitted online through the student portal."
        ],
        ctx={}
    )


@pytest.fixture
def rag_answer_numeric_mismatch():
    """Create a RAG answer contract with numeric inconsistencies."""
    return AnswerContract(
        mode="rag",
        intent="freeform",
        answer="The scholarship application deadline is October 20, 2023 for all students.",  # Different date
        fields={},
        sources=[
            SourceRef(
                url="https://example.edu/policies/scholarships",
                page=12,
                title="Scholarship Guide 2023",
                updated_at="2023-07-20",
                policy_id="schol-2023"
            )
        ],
        evidence_texts=[
            "The scholarship application deadline for all undergraduate students is September 15, 2023.",
            "Applications must be submitted online through the student portal."
        ],
        ctx={}
    )


@pytest.mark.asyncio
async def test_rule_answer_passes_guards():
    """Test that a valid rule-based answer passes all guards."""
    # Arrange
    contract = rule_answer_contract()
    
    # Act
    decision = apply_guards(
        contract=contract,
        newest_policy_date="2023-08-15",
        lang_ok=True
    )
    
    # Assert
    assert decision.ok is True
    assert len(decision.reasons) == 0
    assert decision.confidence > 0.9


@pytest.mark.asyncio
async def test_rag_answer_passes_guards():
    """Test that a valid RAG answer passes all guards."""
    # Arrange
    contract = rag_answer_contract()
    
    # Act
    decision = apply_guards(
        contract=contract,
        newest_policy_date="2023-07-20",
        lang_ok=True
    )
    
    # Assert
    assert decision.ok is True
    assert len(decision.reasons) == 0
    assert decision.confidence > 0.9


@pytest.mark.asyncio
async def test_uncited_answer_fails_guards():
    """Test that an uncited answer fails the citation guard."""
    # Arrange
    contract = rag_answer_uncited()
    
    # Act
    decision = apply_guards(
        contract=contract,
        newest_policy_date="2023-07-20",
        lang_ok=True
    )
    
    # Assert
    assert decision.ok is False
    assert "no_citation" in decision.reasons
    assert decision.confidence < 0.9


@pytest.mark.asyncio
async def test_numeric_mismatch_fails_guards():
    """Test that an answer with numeric inconsistencies fails the numeric guard."""
    # Arrange
    contract = rag_answer_numeric_mismatch()
    
    # Act
    decision = apply_guards(
        contract=contract,
        newest_policy_date="2023-07-20",
        lang_ok=True
    )
    
    # Assert
    assert decision.ok is False
    assert "numeric_mismatch" in decision.reasons
    assert decision.confidence < 0.9


@pytest.mark.asyncio
async def test_stale_source_fails_guards():
    """Test that an answer with stale sources fails the staleness guard."""
    # Arrange
    contract = rag_answer_contract()
    old_date = "2022-01-01"  # More than a year old
    
    # Act
    decision = apply_guards(
        contract=contract,
        newest_policy_date=old_date,
        lang_ok=True,
        max_age_days=180  # 6 months max age
    )
    
    # Assert
    assert decision.ok is False
    assert "stale_source" in decision.reasons
    assert decision.confidence < 0.9


@pytest.mark.asyncio
async def test_integrated_ask_endpoint():
    """Test the integrated /ask endpoint with the new guard pipeline."""
    # This would be a more comprehensive test that would:
    # 1. Mock the dependencies
    # 2. Call the /ask endpoint with different queries
    # 3. Verify the responses based on different guard outcomes
    
    # For now, this is a placeholder for the integration test
    pass
