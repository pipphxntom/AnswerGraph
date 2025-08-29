# A2G Backend Validation Runbook

This runbook provides a step-by-step guide to validate the A2G backend implementation. Each step includes exact commands to execute, expected response formats, and pass criteria.

## Table of Contents

1. [Bring Up Services](#1-bring-up-services)
2. [Seed and Index Data](#2-seed-and-index-data)
3. [Health Check](#3-health-check)
4. [Rules Path Validation](#4-rules-path-validation)
5. [RAG Path Validation](#5-rag-path-validation)
6. [Disambiguation Flow](#6-disambiguation-flow)
7. [Guard Failure Cases](#7-guard-failure-cases)
8. [Admin Live Update](#8-admin-live-update)
9. [Stats and Rate Limits](#9-stats-and-rate-limits)
10. [Gold Test Execution](#10-gold-test-execution)

## 1. Bring Up Services

### Start Docker Compose

```bash
cd /path/to/a2g
docker-compose up -d
```

### Verify Containers

```bash
docker-compose ps
```

**Expected Output:**
```
NAME                COMMAND                  SERVICE             STATUS              PORTS
a2g-api             "uvicorn src.main:ap…"   api                 running             0.0.0.0:8000->8000/tcp
a2g-db              "docker-entrypoint.s…"   db                  running             0.0.0.0:5432->5432/tcp
a2g-redis           "docker-entrypoint.s…"   redis               running             0.0.0.0:6379->6379/tcp
a2g-vector-db       "/opt/milvus/bin/mil…"   vector-db           running             0.0.0.0:19530->19530/tcp
```

**Pass Criteria:**
- All containers show "running" status
- No error messages in logs (`docker-compose logs`)
- API container available at http://localhost:8000

## 2. Seed and Index Data

### Seed Database from CSV

```bash
docker-compose exec api python src/scripts/seed_from_csv.py --file /data/FAQ_seed.csv
```

**Expected Output:**
```
Seeding database from CSV file...
Processed 60 rows
Created 5 intents
Created 12 fee_deadline entries
Created 12 scholarship_form_deadline entries
Created 12 timetable_release entries
Created 12 hostel_fee_due entries
Created 12 exam_form_deadline entries
Database seeding completed successfully
```

### Create Embeddings and Index

```bash
docker-compose exec api python src/scripts/embed_index.py
```

**Expected Output:**
```
Creating embeddings for 60 documents...
Indexing embeddings in vector database...
Creating 5 intent classifiers...
Optimization: Creating cross-encoder reranker...
Indexing completed successfully
```

**Pass Criteria:**
- No errors during seeding or indexing
- Database contains all 60 entries
- Vector store contains embeddings for all documents

## 3. Health Check

### API Health Check

```bash
curl -X GET "http://localhost:8000/health"
```

**Expected Response:**
```json
{
  "status": "ok",
  "version": "1.0.0",
  "uptime": 123.45,
  "timestamp": "2025-08-30T12:34:56.789Z"
}
```

### Database Connectivity Check

```bash
curl -X GET "http://localhost:8000/policies?limit=1"
```

**Expected Response:**
```json
[
  {
    "id": "1",
    "title": "Fee Policy 2023",
    "category": "fees",
    "status": "active",
    "effective_from": "2023-08-15",
    "created_at": "2023-08-15T00:00:00"
  }
]
```

**Pass Criteria:**
- Health endpoint returns status "ok"
- API can connect to the database and return policy data
- Response time under 200ms

## 4. Rules Path Validation

### Test fee_deadline Intent

```bash
curl -X POST "http://localhost:8000/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "When is the fee deadline for BTech semester 1 at Main campus?",
    "lang": "en"
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
  "processing_time": 56.78
}
```

### Test scholarship_form_deadline Intent

```bash
curl -X POST "http://localhost:8000/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "What is the deadline for merit scholarship forms for City campus?",
    "lang": "en"
  }'
```

**Expected Response:**
```json
{
  "mode": "rules",
  "intent": "scholarship_form_deadline",
  "answer": "The merit scholarship form submission deadline for City campus is September 30, 2023.",
  "sources": [
    {
      "url": "https://college.edu/notices/2023-07-20_scholarships.pdf",
      "page": 1,
      "title": "Scholarship Policy 2023",
      "updated_at": "2023-07-20"
    }
  ],
  "confidence": 0.92,
  "processing_time": 61.23
}
```

### Test timetable_release Intent

```bash
curl -X POST "http://localhost:8000/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "When will the BSc semester 5 timetable be released for Main campus?",
    "lang": "en"
  }'
```

**Expected Response:**
```json
{
  "mode": "rules",
  "intent": "timetable_release",
  "answer": "The timetable for BSc semester 5 at Main campus will be released on August 25, 2023.",
  "sources": [
    {
      "url": "https://college.edu/notices/2023-08-10_timetables.pdf",
      "page": 3,
      "title": "Academic Calendar 2023",
      "updated_at": "2023-08-10"
    }
  ],
  "confidence": 0.94,
  "processing_time": 58.67
}
```

### Test hostel_fee_due Intent

```bash
curl -X POST "http://localhost:8000/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "What is the last date to pay hostel fees for Main campus?",
    "lang": "en"
  }'
```

**Expected Response:**
```json
{
  "mode": "rules",
  "intent": "hostel_fee_due",
  "answer": "The hostel fee payment deadline for Main campus is September 15, 2023.",
  "sources": [
    {
      "url": "https://college.edu/notices/2023-08-05_hostel_fees.pdf",
      "page": 2,
      "title": "Hostel Fee Policy 2023",
      "updated_at": "2023-08-05"
    }
  ],
  "confidence": 0.91,
  "processing_time": 59.45
}
```

### Test exam_form_deadline Intent

```bash
curl -X POST "http://localhost:8000/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "When is the last date to submit exam forms for BTech semester 3?",
    "lang": "en"
  }'
```

**Expected Response:**
```json
{
  "mode": "rules",
  "intent": "exam_form_deadline",
  "answer": "The exam form submission deadline for BTech semester 3 is November 10, 2023.",
  "sources": [
    {
      "url": "https://college.edu/notices/2023-09-01_exam_schedule.pdf",
      "page": 1,
      "title": "Examination Policy 2023",
      "updated_at": "2023-09-01"
    }
  ],
  "confidence": 0.93,
  "processing_time": 62.34
}
```

**Pass Criteria:**
- All 5 intents return "rules" mode responses
- Answers include correct information from the database
- Source citations are present and accurate
- Processing time < 200ms for all queries
- Response matches expected format (source URL, page, fields)

## 5. RAG Path Validation

### Test RAG with Variant Phrasing

```bash
curl -X POST "http://localhost:8000/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "btec 1st semstr fee last date?",
    "lang": "en"
  }'
```

**Expected Response:**
```json
{
  "mode": "rag",
  "intent": "fee_deadline",
  "answer": "The fee deadline for BTech semester 1 is October 15, 2023.",
  "sources": [
    {
      "url": "https://college.edu/notices/2023-08-15_fee_deadlines.pdf",
      "page": 2,
      "title": "Fee Policy 2023",
      "updated_at": "2023-08-15"
    }
  ],
  "confidence": 0.87,
  "processing_time": 142.56
}
```

### Test RAG with Hinglish

```bash
curl -X POST "http://localhost:8000/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "main campus ka hostel fee kab tak bharna hai?",
    "lang": "hi-en"
  }'
```

**Expected Response:**
```json
{
  "mode": "rag",
  "intent": "hostel_fee_due",
  "answer": "The hostel fee payment deadline for Main campus is September 15, 2023.",
  "sources": [
    {
      "url": "https://college.edu/notices/2023-08-05_hostel_fees.pdf",
      "page": 2,
      "title": "Hostel Fee Policy 2023",
      "updated_at": "2023-08-05"
    }
  ],
  "confidence": 0.85,
  "processing_time": 178.91
}
```

### Test RAG with Misspelled Words

```bash
curl -X POST "http://localhost:8000/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "skolarship deedline for cty campuss?",
    "lang": "en"
  }'
```

**Expected Response:**
```json
{
  "mode": "rag",
  "intent": "scholarship_form_deadline",
  "answer": "The scholarship form submission deadline for City campus is September 30, 2023.",
  "sources": [
    {
      "url": "https://college.edu/notices/2023-07-20_scholarships.pdf",
      "page": 1,
      "title": "Scholarship Policy 2023",
      "updated_at": "2023-07-20"
    }
  ],
  "confidence": 0.82,
  "processing_time": 156.78
}
```

### Test RAG with Incomplete Information

```bash
curl -X POST "http://localhost:8000/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "exam form deadline?",
    "lang": "en"
  }'
```

**Expected Response:**
```json
{
  "mode": "disambiguation",
  "intent": "exam_form_deadline",
  "text": "Could you please provide more details? Which program and semester are you asking about?",
  "confidence": 0.75,
  "chips": {
    "program": ["BTech", "BBA", "BSc"],
    "semester": [1, 3, 5]
  }
}
```

### Test RAG with Hindi

```bash
curl -X POST "http://localhost:8000/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "BSc semester 5 ka timetable kab release hoga?",
    "lang": "hi"
  }'
```

**Expected Response:**
```json
{
  "mode": "rag",
  "intent": "timetable_release",
  "answer": "The timetable for BSc semester 5 will be released on August 25, 2023.",
  "sources": [
    {
      "url": "https://college.edu/notices/2023-08-10_timetables.pdf",
      "page": 3,
      "title": "Academic Calendar 2023",
      "updated_at": "2023-08-10"
    }
  ],
  "confidence": 0.83,
  "processing_time": 187.45
}
```

**Pass Criteria:**
- RAG successfully handles variant phrasings, typos, and transliterated queries
- All responses include proper citations
- Language detection and normalization works correctly
- Processing time < 500ms for RAG responses
- Confidence scores are appropriate for query quality

## 6. Disambiguation Flow

### Initial Query with Missing Slots

```bash
curl -X POST "http://localhost:8000/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "When is the fee deadline?",
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

### Follow-up with Context

```bash
curl -X POST "http://localhost:8000/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "For BTech first semester",
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
  "text": "Which campus are you asking about?",
  "confidence": 0.82,
  "processing_time": 48.32,
  "chips": {
    "campus": ["Main", "City", "Hostel"]
  }
}
```

### Final Resolution

```bash
curl -X POST "http://localhost:8000/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Main campus",
    "lang": "en",
    "ctx": {
      "session_id": "test-123",
      "intent": "fee_deadline",
      "program": "BTech",
      "semester": 1
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
  "processing_time": 56.78
}
```

**Pass Criteria:**
- System correctly identifies missing slots and requests disambiguation
- Context is preserved between turns
- Chips are provided for easy selection of values
- Final response is provided once all required slots are filled

## 7. Guard Failure Cases

### No Citation Example

```bash
curl -X POST "http://localhost:8000/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "What is the fee for the swimming pool?",
    "lang": "en"
  }'
```

**Expected Response:**
```json
{
  "mode": "fallback",
  "intent": "freeform",
  "text": "I'm sorry, I couldn't find a reliable answer to your question.",
  "reasons": ["no_citation"],
  "ticket_id": "A2G-20250830-3f7b8c9d",
  "confidence": 0.2,
  "processing_time": 178.45
}
```

### Numeric Mismatch Example

```bash
curl -X POST "http://localhost:8000/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Tell me more about the BTech fee for semester 1 with the exact amount",
    "lang": "en"
  }'
```

**Expected Response:**
```json
{
  "mode": "fallback",
  "intent": "fee_deadline",
  "text": "I'm sorry, I couldn't find a reliable answer with the exact amount information.",
  "reasons": ["numeric_mismatch"],
  "ticket_id": "A2G-20250830-9e8d7c6b",
  "confidence": 0.3,
  "processing_time": 201.67
}
```

### Language Not Supported

```bash
curl -X POST "http://localhost:8000/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Quand est la date limite pour les frais?",
    "lang": "fr"
  }'
```

**Expected Response:**
```json
{
  "mode": "fallback",
  "intent": null,
  "text": "I'm sorry, I don't support this language yet. Please ask in English, Hindi, or Hinglish.",
  "reasons": ["lang_mismatch"],
  "confidence": 0.1,
  "processing_time": 33.21
}
```

**Pass Criteria:**
- Guard failures return "fallback" mode
- Specific failure reasons are provided
- Ticket IDs are generated when appropriate
- System doesn't provide unverified information

## 8. Admin Live Update

### Add New Policy Entry

```bash
curl -X POST "http://localhost:8000/admin/policies" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer admin-token" \
  -d '{
    "title": "Updated Fee Policy 2023",
    "category": "fees",
    "effective_from": "2023-09-01",
    "details": "Updated fee schedule for all programs",
    "status": "active"
  }'
```

**Expected Response:**
```json
{
  "id": "fee-2023-update",
  "title": "Updated Fee Policy 2023",
  "category": "fees",
  "effective_from": "2023-09-01",
  "status": "active",
  "created_at": "2025-08-30T14:25:36.123Z"
}
```

### Add Source Document

```bash
curl -X POST "http://localhost:8000/admin/sources" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer admin-token" \
  -d '{
    "url": "https://college.edu/notices/2023-09-01_updated_fees.pdf",
    "title": "Updated Fee Schedule 2023",
    "policy_id": "fee-2023-update",
    "page_count": 3
  }'
```

**Expected Response:**
```json
{
  "id": "source-2023-fees-update",
  "url": "https://college.edu/notices/2023-09-01_updated_fees.pdf",
  "title": "Updated Fee Schedule 2023",
  "policy_id": "fee-2023-update",
  "page_count": 3,
  "created_at": "2025-08-30T14:26:42.567Z"
}
```

### Add Procedure with Updated Deadline

```bash
curl -X POST "http://localhost:8000/admin/procedures" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer admin-token" \
  -d '{
    "policy_id": "fee-2023-update",
    "type": "fee_payment",
    "details": "BTech semester 1 Main campus",
    "deadline": "2023-10-30"
  }'
```

**Expected Response:**
```json
{
  "id": "proc-2023-fee-btech-update",
  "policy_id": "fee-2023-update",
  "type": "fee_payment",
  "details": "BTech semester 1 Main campus",
  "deadline": "2023-10-30",
  "created_at": "2025-08-30T14:27:58.901Z"
}
```

### Verify Updated Information

```bash
curl -X POST "http://localhost:8000/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "When is the fee deadline for BTech semester 1 at Main campus?",
    "lang": "en"
  }'
```

**Expected Response:**
```json
{
  "mode": "rules",
  "intent": "fee_deadline",
  "answer": "The fee deadline for BTech semester 1 at Main campus is October 30, 2023.",
  "sources": [
    {
      "url": "https://college.edu/notices/2023-09-01_updated_fees.pdf",
      "page": 1,
      "title": "Updated Fee Schedule 2023",
      "updated_at": "2023-09-01"
    }
  ],
  "confidence": 0.95,
  "processing_time": 58.12
}
```

**Pass Criteria:**
- Admin endpoints require authentication
- New policy, source, and procedure are correctly added
- System returns the updated information in responses
- Source citation reflects the new document

## 9. Stats and Rate Limits

### Check API Stats

```bash
curl -X GET "http://localhost:8000/stats" \
  -H "Authorization: Bearer admin-token"
```

**Expected Response:**
```json
{
  "total_requests": 25,
  "rule_based_responses": 15,
  "rag_responses": 5,
  "intent_distribution": {
    "fee_deadline": 8,
    "scholarship_form_deadline": 5,
    "timetable_release": 4,
    "hostel_fee_due": 4,
    "exam_form_deadline": 4
  },
  "avg_response_time": 87.56
}
```

### Test Rate Limiting

```bash
# Run 20 requests in rapid succession
for i in {1..20}; do
  curl -X POST "http://localhost:8000/ask" \
    -H "Content-Type: application/json" \
    -d '{
      "text": "fee deadline btech",
      "lang": "en"
    }'
done
```

**Expected Behavior:**
- First ~10 requests succeed
- Subsequent requests receive rate limit error:
```json
{
  "error": "Too many requests",
  "detail": "Rate limit exceeded. Please try again later.",
  "status_code": 429
}
```

**Pass Criteria:**
- Stats endpoint shows correct request counts
- Intent distribution is tracked properly
- Rate limiting kicks in after threshold is exceeded
- System recovers after rate limit window expires

## 10. Gold Test Execution

### Run Gold Test Suite

```bash
docker-compose exec api python src/scripts/run_gold_tests.py --csv /data/Gold_tests.csv
```

**Expected Output:**
```
Running gold test suite with 200 test cases...

Intent Classification Results:
- Accuracy: 94.5%
- Precision: 93.2%
- Recall: 94.7%
- F1 Score: 93.9%

Slot Extraction Results:
- Field Correctness Rate (FCR): 87.3%
- Program Accuracy: 92.1%
- Semester Accuracy: 89.5%
- Campus Accuracy: 85.6%

Citation Results:
- Citation Rate: 97.5%
- Correct Citation Rate: 95.3%

Performance Metrics:
- Average Response Time: 123.7 ms
- p95 Response Time: 187.2 ms
- p99 Response Time: 231.8 ms

Tests Summary:
- Total Tests: 200
- Passed: 187
- Failed: 13
- Success Rate: 93.5%

OVERALL RESULT: PASS (meets all quality gates)
```

### Verify Quality Gates

```bash
docker-compose exec api python src/scripts/check_quality_gates.py
```

**Expected Output:**
```
Checking quality gates...

1. Citation Rate: 97.5% (PASS - threshold: ≥85%)
2. Field Correctness Rate: 87.3% (PASS - threshold: ≥85%)
3. p95 Response Time: 187.2 ms (PASS - threshold: ≤2000ms)
4. Uncited Answers: 0 (PASS - threshold: 0)

All quality gates PASSED!
System is ready for deployment.
```

**Pass Criteria:**
- Gold test success rate > 90%
- All quality gates are passed
- Citation Rate ≥ 85%
- Field Correctness Rate (FCR) ≥ 85%
- p95 Response Time ≤ 2000ms
- Zero uncited answers

## Summary

This validation runbook provides a comprehensive sequence to validate the A2G backend implementation. By following these steps, you can ensure that:

1. The system correctly handles all five supported intents
2. Both rules and RAG paths work as expected
3. The guard system prevents uncited or inconsistent responses
4. Disambiguation flow properly handles missing slots
5. Admin updates are reflected in responses
6. Performance meets the required thresholds

If all steps pass, the system is considered validated and ready for deployment.
