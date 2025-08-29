# A2G Backend Validation Runbook

This document outlines the steps to validate the standardized AnswerContract → apply_guards → Respond/Fallback pipeline implemented in the A2G FastAPI backend.

## Prerequisites

- Python 3.8+
- Virtual environment with required dependencies installed (see `requirements.txt`)
- Access to test database

## Setup

1. Clone the repository
2. Install dependencies: 
   ```
   pip install -r requirements.txt
   ```
3. Set up environment variables:
   ```
   export A2G_DB_URL="postgresql+asyncpg://username:password@localhost:5432/a2g_test"
   export A2G_ENABLE_TICKETING=true
   ```

## Validation Tests

### 1. Validate Call Graph

Run the following commands to validate the call graph is correct:

```bash
# Run test to verify both Rules and RAG paths use apply_guards
python -m pytest tests/test_integration_guards.py -v

# Run test to verify disambiguation path
python -m pytest tests/test_disambiguation.py -v

# Run end-to-end tests
python -m pytest tests/test_api_e2e.py -v
```

### 2. Validate Contract Conformance

Check that AnswerContract is consistently used:

```bash
# Run the server in one terminal
uvicorn src.main:app --reload

# In another terminal, test the /ask endpoint with rules-based query
curl -X POST "http://localhost:8000/ask" \
    -H "Content-Type: application/json" \
    -d '{"text": "What is the fee deadline for BTech?"}'

# Test with RAG-based query
curl -X POST "http://localhost:8000/ask" \
    -H "Content-Type: application/json" \
    -d '{"text": "How many semesters are there in MBA?"}'

# Test with a query that should trigger disambiguation
curl -X POST "http://localhost:8000/ask" \
    -H "Content-Type: application/json" \
    -d '{"text": "When is the scholarship deadline?"}'
```

Verify in each case that:
- Success responses have mode="rules" or "rag" and include answer, sources, and updated_date
- Disambiguation responses have mode="disambiguation" and include chips
- Fallback responses have mode="fallback" and include reasons and ticket_id

### 3. Validate Guards Enforcement

Test each guard:

```bash
# Test citation guard
curl -X POST "http://localhost:8000/ask" \
    -H "Content-Type: application/json" \
    -d '{"text": "What happens if a citation is missing?"}'

# Test numeric consistency guard
curl -X POST "http://localhost:8000/ask" \
    -H "Content-Type: application/json" \
    -d '{"text": "What is the percentage of attendance required?"}'

# Test staleness guard (need to have a stale policy in the test DB)
curl -X POST "http://localhost:8000/ask" \
    -H "Content-Type: application/json" \
    -d '{"text": "Tell me about the old scholarship policy from 2010"}'

# Test language guard with unsupported language
curl -X POST "http://localhost:8000/ask" \
    -H "Content-Type: application/json" \
    -d '{"text": "¿Cuándo es la fecha límite para las tarifas?", "lang": "es"}'
```

### 4. Validate Rules Evidence

Test empty evidence handling:

```bash
# Query a rule that requires evidence from a non-existent source
curl -X POST "http://localhost:8000/ask" \
    -H "Content-Type: application/json" \
    -d '{"text": "What is the fee deadline for a program that doesn't exist?"}'
```

Verify that:
- The answer includes a fallback evidence text rather than an empty list
- The guard fallback mechanism works properly

### 5. Validate Ticketing

```bash
# Trigger a guard failure to create a ticket
curl -X POST "http://localhost:8000/ask" \
    -H "Content-Type: application/json" \
    -d '{"text": "Tell me something that will fail citation check"}'
```

Verify that:
- A ticket_id is returned in the response
- The ticket creation logs show up in the server output
- The timeout mechanism works by adding a sleep in the ticket creation function

### 6. Validate PII Redaction

```bash
# Try a query that might include PII in the response
curl -X POST "http://localhost:8000/ask" \
    -H "Content-Type: application/json" \
    -d '{"text": "What is the contact email for admissions?"}'
```

Verify that:
- Any email addresses in the response are redacted
- PII redaction is applied consistently in both Rules and RAG paths

## Advanced Validation

### Manual Testing Matrix

| Test Case | Expected Behavior |
|-----------|-------------------|
| Rules path with all guards passing | Returns mode="rules" with answer and sources |
| Rules path with guard failures | Returns mode="fallback" with reasons and ticket_id |
| RAG path with all guards passing | Returns mode="rag" with answer and sources |
| RAG path with guard failures | Returns mode="fallback" with reasons and ticket_id |
| Disambiguation needed | Returns mode="disambiguation" with chips |
| Follow-up after disambiguation | Correctly processes with provided context |
| Unsupported language | Returns mode="fallback" with "lang_mismatch" reason |
| Empty query | Returns 400 error with validation message |
| Error during processing | Returns 500 error with appropriate message |

### Performance Testing

For each test scenario, measure and record:
- Response time
- Memory usage
- Database query count

Compare against baseline to ensure no performance regressions.

## Troubleshooting

### Common Issues

1. **Guards not being applied**: Check if `apply_guards` is called in both rules and RAG paths

2. **Missing evidence texts**: Verify that `fetch_clause_text` is handling empty results properly 

3. **PII not being redacted**: Ensure `ensure_sensitive_data_protection` is called in all answer paths

4. **Ticket creation failing**: Check database permissions and connection

5. **Guards always failing**: Verify that newest_policy_date is being extracted correctly
