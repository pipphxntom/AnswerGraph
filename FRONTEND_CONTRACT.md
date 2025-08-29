# Frontend API Contract

This document defines the API contract between the A2G backend and frontend applications. It outlines request/response formats, expected payloads, error handling, and performance expectations.

## Request Format

### POST /ask

**Endpoint:** `POST /ask`

**Description:** Submit a user query to retrieve an answer from the A2G system.

**Request Body:**
```json
{
  "text": "string",        // Required: The user's query text
  "lang": "string",        // Required: Language code ("en", "hi", or "hi-en")
  "ctx": {                 // Optional: Conversation context
    "prev_query": "string",
    "prev_slots": {
      "slot_name": "value"
    },
    "session_id": "string"
  }
}
```

**Example Request:**
```json
{
  "text": "What is the fee deadline for BTech semester 1?",
  "lang": "en"
}
```

**Example Request with Context:**
```json
{
  "text": "What about for MTech?",
  "lang": "en",
  "ctx": {
    "prev_query": "What is the fee deadline for BTech semester 1?",
    "prev_slots": {
      "program": "BTech",
      "semester": "1"
    },
    "session_id": "user123-session456"
  }
}
```

## Response Format

All responses follow a standardized structure with a common set of fields and mode-specific fields.

### Common Response Structure

```json
{
  "mode": "string",        // Response mode: "rules", "rag", "disambiguation", or "fallback"
  "answer": "string",      // The natural language answer text (null for disambiguation)
  "query": "string",       // The original query text
  "slots": {               // Extracted and normalized slots from the query
    "slot_name": "value"
  },
  "sources": [             // Source citations (null for disambiguation)
    {
      "id": "string",
      "title": "string",
      "url": "string",
      "page": number
    }
  ],
  "response_time_ms": number,  // Processing time in milliseconds
  "ticket_id": "string"        // Only present in fallback mode
}
```

### Response Modes

#### 1. Rules-based Response (mode: "rules")

This mode is used when the system can answer the query using predefined rules.

**Example Response:**
```json
{
  "mode": "rules",
  "answer": "The fee deadline for BTech semester 1 is September 15, 2025. Late payment will incur a penalty of Rs. 1000.",
  "query": "What is the fee deadline for BTech semester 1?",
  "slots": {
    "program": "BTech",
    "semester": "1",
    "campus": "Main"
  },
  "sources": [
    {
      "id": "fee-schedule-2025",
      "title": "Fee Schedule 2025-26",
      "url": "https://university.edu/fees/schedule-2025.pdf",
      "page": 12
    }
  ],
  "response_time_ms": 87
}
```

#### 2. RAG-based Response (mode: "rag")

This mode is used when the system answers using the Retrieval-Augmented Generation approach.

**Example Response:**
```json
{
  "mode": "rag",
  "answer": "According to the university fee policy, BTech semester 1 students must pay their fees by September 15, 2025. The payment can be made online through the student portal or at the accounts office. Please note that a late fee of Rs. 1000 will be charged after the deadline.",
  "query": "When do I need to pay my BTech first semester fees?",
  "slots": {
    "program": "BTech",
    "semester": "1"
  },
  "sources": [
    {
      "id": "fee-policy-2025",
      "title": "University Fee Policy 2025-26",
      "url": "https://university.edu/policies/fee-policy-2025.pdf",
      "page": 8
    },
    {
      "id": "student-handbook",
      "title": "Student Handbook 2025",
      "url": "https://university.edu/student/handbook.pdf",
      "page": 23
    }
  ],
  "response_time_ms": 156
}
```

#### 3. Disambiguation Response (mode: "disambiguation")

This mode is used when the query is incomplete and requires additional information.

**Example Response:**
```json
{
  "mode": "disambiguation",
  "answer": null,
  "query": "What is the fee deadline?",
  "slots": {},
  "sources": null,
  "missing_slots": ["program", "semester"],
  "disambiguation_message": "Please specify which program and semester you're asking about.",
  "chips": [
    {
      "text": "BTech",
      "slot": "program",
      "value": "BTech"
    },
    {
      "text": "MTech",
      "slot": "program",
      "value": "MTech"
    },
    {
      "text": "MBA",
      "slot": "program",
      "value": "MBA"
    },
    {
      "text": "Semester 1",
      "slot": "semester",
      "value": "1"
    },
    {
      "text": "Semester 2",
      "slot": "semester",
      "value": "2"
    }
  ],
  "response_time_ms": 65
}
```

#### 4. Fallback Response (mode: "fallback")

This mode is used when the system cannot provide a reliable answer.

**Example Response:**
```json
{
  "mode": "fallback",
  "answer": "I'm sorry, but I couldn't find reliable information about your query. A support ticket has been created and our team will look into this shortly. Your ticket ID is TKT-12345.",
  "query": "How much is the scholarship for international Olympic medalists?",
  "slots": {},
  "sources": null,
  "ticket_id": "TKT-12345",
  "failure_reasons": [
    "no_relevant_documents",
    "confidence_below_threshold"
  ],
  "response_time_ms": 134
}
```

## Performance Requirements

### Latency Budget

- **Web Response Time:** ≤ 2000ms (2 seconds)
- **Target p95 Response Time:** ≤ 1500ms
- **Target p99 Response Time:** ≤ 2000ms

### Error Messages

| HTTP Status | Error Type | Description | Example |
|-------------|------------|-------------|---------|
| 400 | Bad Request | Invalid input parameters | `{"error": "Bad Request", "detail": "Invalid language code. Supported values are 'en', 'hi', and 'hi-en'"}` |
| 429 | Too Many Requests | Rate limit exceeded | `{"error": "Too Many Requests", "detail": "Rate limit exceeded. Please try again later."}` |
| 500 | Internal Server Error | Server-side error | `{"error": "Internal Server Error", "detail": "An unexpected error occurred. Please try again later."}` |
| 503 | Service Unavailable | Service temporarily unavailable | `{"error": "Service Unavailable", "detail": "The service is currently unavailable. Please try again later."}` |

## Demo Queries and Expected Responses

### Demo 1: Basic Fee Deadline Query

**Query:**
```
What is the fee deadline for BTech semester 1 at Main campus?
```

**Expected Response:**
```json
{
  "mode": "rules",
  "answer": "The fee deadline for BTech semester 1 at Main campus is September 15, 2025. Late payment will incur a penalty of Rs. 1000.",
  "query": "What is the fee deadline for BTech semester 1 at Main campus?",
  "slots": {
    "program": "BTech",
    "semester": "1",
    "campus": "Main"
  },
  "sources": [
    {
      "id": "fee-schedule-2025",
      "title": "Fee Schedule 2025-26",
      "url": "https://university.edu/fees/schedule-2025.pdf",
      "page": 12
    }
  ],
  "response_time_ms": 87
}
```

### Demo 2: Query Requiring Disambiguation

**Query:**
```
When is the scholarship form deadline?
```

**Expected Response:**
```json
{
  "mode": "disambiguation",
  "answer": null,
  "query": "When is the scholarship form deadline?",
  "slots": {},
  "sources": null,
  "missing_slots": ["scholarship_type", "campus"],
  "disambiguation_message": "Please specify which scholarship type and campus you're asking about.",
  "chips": [
    {
      "text": "Merit Scholarship",
      "slot": "scholarship_type",
      "value": "merit"
    },
    {
      "text": "Need-based Scholarship",
      "slot": "scholarship_type",
      "value": "need_based"
    },
    {
      "text": "Sports Scholarship",
      "slot": "scholarship_type",
      "value": "sports"
    },
    {
      "text": "Main Campus",
      "slot": "campus",
      "value": "Main"
    },
    {
      "text": "City Campus",
      "slot": "campus",
      "value": "City"
    }
  ],
  "response_time_ms": 72
}
```

### Demo 3: Follow-up to Disambiguation

**Query:**
```
Merit Scholarship at Main Campus
```

**Expected Response:**
```json
{
  "mode": "rules",
  "answer": "The deadline for submitting the Merit Scholarship application form for Main Campus is October 10, 2025. All supporting documents must be submitted by October 15, 2025.",
  "query": "Merit Scholarship at Main Campus",
  "slots": {
    "scholarship_type": "merit",
    "campus": "Main"
  },
  "sources": [
    {
      "id": "scholarship-2025",
      "title": "Scholarship Information 2025-26",
      "url": "https://university.edu/scholarship/info-2025.pdf",
      "page": 5
    }
  ],
  "response_time_ms": 92
}
```

### Demo 4: Complex RAG Query

**Query:**
```
What documents do I need to submit for hostel allocation at City campus?
```

**Expected Response:**
```json
{
  "mode": "rag",
  "answer": "For hostel allocation at City campus, you need to submit the following documents: 1) Completed hostel application form, 2) Fee payment receipt, 3) Medical fitness certificate, 4) Two passport-sized photographs, 5) Copy of your student ID card, and 6) Proof of residence. International students must also provide a copy of their visa and passport. All documents should be submitted to the Hostel Administration Office at least two weeks before the semester begins.",
  "query": "What documents do I need to submit for hostel allocation at City campus?",
  "slots": {
    "campus": "City",
    "topic": "hostel_allocation"
  },
  "sources": [
    {
      "id": "hostel-manual",
      "title": "Hostel Administration Manual 2025",
      "url": "https://university.edu/hostel/manual-2025.pdf",
      "page": 17
    },
    {
      "id": "city-campus-guide",
      "title": "City Campus Student Guide",
      "url": "https://university.edu/campus/city-guide.pdf",
      "page": 42
    }
  ],
  "response_time_ms": 187
}
```

### Demo 5: Fallback for Unsupported Query

**Query:**
```
How do I transfer credits from another university in a different country?
```

**Expected Response:**
```json
{
  "mode": "fallback",
  "answer": "I'm sorry, but I don't have enough information about international credit transfers. A support ticket has been created and our academic team will respond to your query soon. Your ticket ID is TKT-54321.",
  "query": "How do I transfer credits from another university in a different country?",
  "slots": {
    "topic": "credit_transfer",
    "international": true
  },
  "sources": null,
  "ticket_id": "TKT-54321",
  "failure_reasons": [
    "topic_out_of_scope",
    "requires_human_expertise"
  ],
  "response_time_ms": 105
}
```

## Implementation Notes for UI Team

1. **Handling Disambiguation**:
   - When receiving a disambiguation response, display the disambiguation message and the suggested chips to the user.
   - When the user selects a chip or provides additional information, send a new request with the updated query.

2. **Context Preservation**:
   - Store the previous query and slots to provide context for follow-up questions.
   - Include this context in subsequent requests using the `ctx` field.

3. **Source Citations**:
   - Always display source citations when available.
   - Make source links clickable to allow users to access the referenced documents.

4. **Error Handling**:
   - Implement appropriate UI feedback for different HTTP error codes.
   - Display the ticket ID prominently when in fallback mode to allow users to reference it in support communications.

5. **Performance Monitoring**:
   - Track client-side response times and compare with server-reported `response_time_ms`.
   - Alert users if the system is experiencing unusual delays.
