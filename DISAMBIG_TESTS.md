# Disambiguation Flow Test Guide

This document outlines the test procedure for validating the disambiguation flow in the A2G system. The tests verify that the system correctly identifies missing slots, requests clarification, and properly handles follow-up responses.

## Test Overview

The disambiguation flow should:
1. Identify when a query is missing required slots
2. Respond with mode "disambiguation" and appropriate chips
3. Skip guard application during disambiguation
4. Process follow-up responses with context
5. Apply guards on the final answer

## Test Case: fee_deadline Intent

### Step 1: Initial Query with Missing Slots

**Request:**
```bash
curl -X POST "http://localhost:8000/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "fee deadline?",
    "lang": "en",
    "ctx": {"session_id": "test-123"}
  }'
```

**Expected Response:**
```json
{
  "mode": "disambiguation",
  "intent": "fee_deadline",
  "text": "Could you please provide more details?",
  "confidence": 0.75,
  "processing_time": 45.67,
  "chips": {
    "program": ["BTech", "BBA", "BSc"],
    "semester": [1, 3, 5],
    "campus": ["Main", "City", "Hostel"]
  }
}
```

**Validation Checks:**
- [ ] Response `mode` is "disambiguation"
- [ ] `intent` is correctly identified as "fee_deadline"
- [ ] `chips` object contains all required slots (program, semester, campus)
- [ ] Each chip has appropriate options
- [ ] Guard checks are skipped (verify in logs: "Skipping guards for disambiguation response")
- [ ] `ctx` from request is preserved in the backend state

### Step 2: Follow-up with Missing Slot Information

**Request:**
```bash
curl -X POST "http://localhost:8000/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "BTech semester 1 Main campus",
    "lang": "en",
    "ctx": {
      "session_id": "test-123",
      "intent": "fee_deadline"
    }
  }'
```

**Expected Response:**
```json
{
  "mode": "rules",
  "intent": "fee_deadline",
  "answer": "The fee deadline for BTech semester 1 at Main campus is October 15, 2023.",
  "sources": [
    {
      "url": "https://college.edu/notices/2023-08-15_fee_deadlines.pdf",
      "page": 2,
      "title": "Fee Policy 2023",
      "updated_at": "2023-08-15"
    }
  ],
  "confidence": 0.95,
  "processing_time": 56.78,
  "updated_date": "2023-08-15"
}
```

**Validation Checks:**
- [ ] Response `mode` is "rules"
- [ ] `intent` matches the preserved intent from Step 1
- [ ] `answer` contains all slots provided (BTech, semester 1, Main campus)
- [ ] `sources` array contains at least one citation with URL and page
- [ ] Guards are applied (verify in logs: "Applying guards to answer contract")
- [ ] Processing time is reasonable (<200ms)

## Alternative Test: Partial Slot Provision

### Step 1: Initial Query with Missing Slots

Same as above.

### Step 2: Provide Only One Missing Slot

**Request:**
```bash
curl -X POST "http://localhost:8000/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "BTech",
    "lang": "en",
    "ctx": {
      "session_id": "test-123",
      "intent": "fee_deadline"
    }
  }'
```

**Expected Response:**
```json
{
  "mode": "disambiguation",
  "intent": "fee_deadline",
  "text": "Which semester and campus are you asking about?",
  "confidence": 0.82,
  "processing_time": 48.32,
  "chips": {
    "semester": [1, 3, 5],
    "campus": ["Main", "City", "Hostel"]
  }
}
```

**Validation Checks:**
- [ ] Response `mode` is still "disambiguation"
- [ ] System correctly identifies remaining missing slots
- [ ] `chips` only shows the remaining required slots
- [ ] Provided slot (program="BTech") is stored in context
- [ ] Guard checks are still skipped

## Test Sequence Variations

Test the disambiguation flow with each of the five supported intents:

1. **fee_deadline**
   - Required slots: program, semester, campus

2. **scholarship_form_deadline**
   - Required slots: campus
   - Optional: scholarship_type

3. **timetable_release**
   - Required slots: program, semester, campus

4. **hostel_fee_due**
   - Required slots: campus

5. **exam_form_deadline**
   - Required slots: program, semester

For each intent, test:
- Single-turn resolution (provide all slots at once)
- Multi-turn resolution (provide slots one by one)
- Out-of-order slot provision

## Implementation Verification

To verify that guards are skipped during disambiguation and applied on final answers, check the logs for the following patterns:

### Disambiguation Mode (Guards Skipped):
```
DEBUG:src.api.ask_routes:Intent requires disambiguation, skipping guards
DEBUG:src.api.ask_routes:Missing required slots: ['program', 'semester', 'campus']
DEBUG:src.api.ask_routes:Returning disambiguation response with chips
```

### Final Answer (Guards Applied):
```
INFO:src.api.ask_routes:All required slots present for intent 'fee_deadline'
DEBUG:src.rag.guards:Applying guards to answer contract
DEBUG:src.rag.guards:Citation guard: PASS
DEBUG:src.rag.guards:Numeric consistency guard: PASS
INFO:src.api.ask_routes:Guards passed, returning answer
```

## Troubleshooting

| Issue | Possible Cause | Resolution |
|-------|----------------|------------|
| Missing chips | Intent classifier not recognizing intent | Check intent classification confidence |
| Wrong slots in chips | Intent-slot mapping outdated | Update slot definitions for intent |
| Context not preserved | Session handling issue | Verify ctx is passed in follow-up request |
| Guards applied during disambiguation | Logic error in guard skipping | Check conditional in apply_guards call |
| Guards skipped for final answer | Context not indicating final resolution | Verify all slots are present check |
