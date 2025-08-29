# Ticketing System Test Guide

This document outlines the test procedure for validating the ticketing system in the A2G backend. The ticketing system should create tickets for failed guard checks while ensuring non-blocking behavior through timeout protection.

## Test Overview

The ticketing system should:
1. Create tickets when guards fail
2. Include a ticket ID in fallback responses
3. Protect against timeouts during ticket creation
4. Redact PII from ticket contents
5. Complete within a reasonable time frame (< 3 seconds)

## Test Case: Nonsense Query Triggering Fallback

### Request with Nonsensical Content

**Request:**
```bash
curl -X POST "http://localhost:8000/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "purple monkey dishwasher quantum zebra elephant fluctuations",
    "lang": "en"
  }'
```

**Expected Response:**
```json
{
  "mode": "fallback",
  "intent": null,
  "text": "I'm sorry, I couldn't find a reliable answer to your question.",
  "reasons": ["no_citation", "intent_unknown"],
  "ticket_id": "A2G-20250830-3f7b8c9d",
  "confidence": 0.2,
  "processing_time": 2532.45
}
```

**Validation Checks:**
- [ ] Response `mode` is "fallback"
- [ ] `reasons` array contains at least one failure reason
- [ ] `ticket_id` is present and follows the format A2G-YYYYMMDD-XXXXXXXX
- [ ] Total response time is under 3 seconds
- [ ] No PII in the response

### Expected Log Output

The server logs should contain entries similar to:

```
INFO:src.api.ask_routes:No intent matched with high confidence for query
DEBUG:src.rag.guards:Applying guards to RAG fallback answer
DEBUG:src.rag.guards:Citation guard: FAIL - No sources provided
INFO:src.api.ask_routes:Guards failed with reasons: ['no_citation', 'intent_unknown']
INFO:src.api.ask_routes:Creating ticket for failed guard checks
DEBUG:src.api.ask_routes:Attempting to create ticket with timeout protection (2.0s)
INFO:src.api.ask_routes:Created ticket A2G-20250830-3f7b8c9d for failed guard checks
DEBUG:src.api.ask_routes:PII redaction applied to ticket content
INFO:src.api.ask_routes:Returning fallback response with ticket ID
```

## Test Case: Ticket Creation with PII

### Request with Personal Information

**Request:**
```bash
curl -X POST "http://localhost:8000/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "My email is test@example.com and my phone is 555-123-4567. When is the fee deadline?",
    "lang": "en"
  }'
```

**Expected Logs:**
```
INFO:src.api.ask_routes:Creating ticket for failed guard checks
DEBUG:src.api.ask_routes:PII redaction applied to ticket content: "My email is [REDACTED EMAIL] and my phone is [REDACTED PHONE]. When is the fee deadline?"
INFO:src.api.ask_routes:Created ticket A2G-20250830-1a2b3c4d for failed guard checks
```

**Validation Checks:**
- [ ] PII is redacted in the logs
- [ ] Ticket is still created successfully
- [ ] Response contains redacted text

## Test Case: Simulating Ticket Creation Timeout

To test timeout protection, temporarily modify the `create_ticket_if_enabled` function to include a delay:

```python
async def create_ticket_if_enabled(
    contract: AnswerContract, 
    reasons: List[str],
    session: Optional[AsyncSession] = None
) -> Optional[str]:
    try:
        # Set a timeout for ticket creation to ensure non-blocking
        async with asyncio.timeout(2.0):  # 2 second timeout
            # Simulate slow external service
            await asyncio.sleep(3.0)  # This will trigger timeout
            
            # Normal ticket creation code...
    except asyncio.TimeoutError:
        logger.error("Ticket creation timed out after 2 seconds")
        return "TIMEOUT-TICKET"
    except Exception as e:
        logger.error(f"Failed to create ticket: {str(e)}")
        return None
```

**Expected Logs:**
```
INFO:src.api.ask_routes:Guards failed with reasons: ['no_citation']
INFO:src.api.ask_routes:Creating ticket for failed guard checks
DEBUG:src.api.ask_routes:Attempting to create ticket with timeout protection (2.0s)
ERROR:src.api.ask_routes:Ticket creation timed out after 2 seconds
INFO:src.api.ask_routes:Returning fallback response with timeout ticket ID
```

**Expected Response:**
```json
{
  "mode": "fallback",
  "reasons": ["no_citation"],
  "ticket_id": "TIMEOUT-TICKET",
  "processing_time": 2103.45
}
```

**Validation Checks:**
- [ ] System detects the timeout
- [ ] Fallback ticket ID "TIMEOUT-TICKET" is returned
- [ ] Response is still returned within 3 seconds despite the internal delay
- [ ] API call completes successfully despite ticket creation timeout

## Troubleshooting Guide

| Issue | Possible Cause | Resolution |
|-------|----------------|------------|
| Missing ticket_id | Ticket creation disabled | Check A2G_ENABLE_TICKETING environment variable |
| Timeout error in response | Timeout not handled correctly | Verify asyncio.timeout is implemented correctly |
| Response takes >3 seconds | Ticket creation blocking main thread | Ensure timeout protection is working |
| PII not redacted | Redaction function not called | Verify ensure_sensitive_data_protection is called |
| "Internal Server Error" | Exception in ticket creation | Check error handling in create_ticket_if_enabled |
| Ticket database errors | Database connection issues | Check database connectivity and credentials |
| Multiple identical tickets | Duplicate request handling | Implement request deduplication logic |

## Network Error Simulation

To test robustness against network errors during ticket creation:

1. **Database Connection Loss**
   - Temporarily disable the database service
   - Expected: "Failed to create ticket: Database connection error"
   - System should still return a fallback response

2. **External Service Timeout**
   - If using external ticketing system, simulate network delay
   - Expected: Timeout protection should trigger
   - Response should still be returned

3. **Partial Failure**
   - Simulate partial ticket creation (e.g., record created but notification failed)
   - Expected: Ticket ID should still be returned
   - Logs should indicate partial failure

## Performance Tracking

| Test Case | Expected Time | Actual Time | Timeout Protected | Notes |
|-----------|---------------|-------------|-------------------|-------|
| Normal ticket creation | < 1s | | | |
| Simulated slow ticket creation | < 3s | | | |
| Database connection error | < 3s | | | |
| External service timeout | < 3s | | | |
| High load (10 concurrent) | < 5s | | | |
