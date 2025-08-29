# Statistics and Rate Limits Validation Guide

This document outlines the procedure for validating the statistics tracking and rate limiting features of the A2G system.

## Test Overview

The statistics and rate limiting system should:
1. Track and report API usage metrics
2. Calculate quality metrics like FCR and citation rate
3. Enforce rate limits to prevent abuse
4. Provide insights into system performance

## Statistics Validation

### Step 1: Generate Test Traffic

Run a series of queries covering various intents and scenarios:

```bash
# Run 20 diverse queries
for i in {1..20}; do
  # Mix of queries to test different intents and paths
  if [ $i -le 5 ]; then
    # Fee deadline queries
    curl -X POST "http://localhost:8000/ask" \
      -H "Content-Type: application/json" \
      -d '{"text": "What is the fee deadline for BTech semester 1?", "lang": "en"}'
  elif [ $i -le 10 ]; then
    # Scholarship queries
    curl -X POST "http://localhost:8000/ask" \
      -H "Content-Type: application/json" \
      -d '{"text": "When is the scholarship form deadline for City campus?", "lang": "en"}'
  elif [ $i -le 15 ]; then
    # Hostel fee queries
    curl -X POST "http://localhost:8000/ask" \
      -H "Content-Type: application/json" \
      -d '{"text": "What is the last date to pay hostel fees for Main campus?", "lang": "en"}'
  else
    # Some RAG path queries
    curl -X POST "http://localhost:8000/ask" \
      -H "Content-Type: application/json" \
      -d '{"text": "fee deadline btech first sem main campus", "lang": "en"}'
  fi
  # Small delay to avoid rate limiting during testing
  sleep 1
done
```

### Step 2: Check Statistics Endpoint

```bash
curl -X GET "http://localhost:8000/stats" \
  -H "Authorization: Bearer admin-token"
```

**Expected Response:**
```json
{
  "request_stats": {
    "total_requests": 20,
    "rules_path_requests": 15,
    "rag_path_requests": 5,
    "disambiguation_requests": 0,
    "fallback_responses": 0
  },
  "quality_metrics": {
    "field_correctness_rate": 0.92,
    "citation_rate": 1.0,
    "intent_classification_accuracy": 0.95
  },
  "performance_metrics": {
    "avg_response_time_ms": 87.5,
    "p95_response_time_ms": 123.4,
    "p99_response_time_ms": 156.7
  },
  "intent_distribution": {
    "fee_deadline": 10,
    "scholarship_form_deadline": 5,
    "hostel_fee_due": 5,
    "timetable_release": 0,
    "exam_form_deadline": 0
  },
  "updated_at": "2025-08-30T15:45:23.456Z"
}
```

**Validation Checks:**
- [ ] `total_requests` matches the number of queries run
- [ ] `rules_path_requests` and `rag_path_requests` sum to the total
- [ ] `field_correctness_rate` (FCR) is reported and reasonable
- [ ] `citation_rate` is reported and should be 1.0 (100%)
- [ ] `intent_distribution` shows the correct breakdown of intents
- [ ] `avg_response_time_ms` and percentiles are reported

## Rate Limit Validation

### Step 1: Rapid Query Execution

```bash
# Run 20 identical queries in rapid succession
for i in {1..20}; do
  curl -X POST "http://localhost:8000/ask" \
    -H "Content-Type: application/json" \
    -d '{"text": "fee deadline", "lang": "en"}'
  echo ""
  # No delay to trigger rate limiting
done
```

### Step 2: Observe Rate Limit Response

After approximately 10-15 requests (depending on configured threshold), you should start receiving rate limit responses:

**Expected Rate Limit Response:**
```json
{
  "error": "Too many requests",
  "detail": "Rate limit exceeded. Please try again later.",
  "status_code": 429
}
```

**Validation Checks:**
- [ ] Initial requests are processed normally
- [ ] After threshold is exceeded, 429 status code is returned
- [ ] Error message clearly indicates rate limiting
- [ ] Rate limiting is per-client (based on IP or session)
- [ ] System recovers after rate limit window expires (typically 1 minute)

## Metric Interpretation Guide

### Field Correctness Rate (FCR)

**Definition:** Percentage of correctly extracted fields out of all fields that should have been extracted.

**How it's calculated:**
- System tracks extracted fields from queries
- Each field is compared to expected values (when available)
- FCR = (Correctly extracted fields) / (Total fields that should be extracted)

**What increments FCR:**
- Correctly identifying program="BTech" when query mentions "BTech"
- Correctly extracting semester=1 when query mentions "first semester"
- Correctly mapping "main campus" to campus="Main"

**What decrements FCR:**
- Extracting program="BBA" when query mentioned "BTech"
- Missing semester extraction when it was present in query
- Incorrectly identifying a campus

### Citation Rate

**Definition:** Percentage of responses that include proper citations to source documents.

**How it's calculated:**
- System tracks all non-disambiguation responses
- Citation Rate = (Responses with valid citations) / (Total non-disambiguation responses)

**What counts as a valid citation:**
- Response includes at least one source with URL and page number
- Source can be verified in the database
- Citation passes the citation guard check

**What doesn't count:**
- Disambiguation responses (these don't need citations)
- Error responses
- Responses where the guard checks were skipped

### Performance Metrics

**p95 Response Time:** The response time below which 95% of all requests are processed. For example, if p95 = 150ms, this means 95% of requests were processed in less than 150ms.

**p99 Response Time:** The response time below which 99% of all requests are processed. This is a good indicator of worst-case performance.

## Quality Gates Tracking

| Metric | Required Gate | Current Value | Status | Notes |
|--------|---------------|---------------|--------|-------|
| Citation Rate | ≥ 85% | | | |
| Field Correctness Rate | ≥ 85% | | | |
| p95 Response Time | ≤ 2000ms | | | |
| Uncited Answers | 0 | | | |

## Troubleshooting

| Issue | Possible Cause | Resolution |
|-------|----------------|------------|
| Stats not updating | Stats service not running | Check background task status |
| FCR unexpectedly low | Slot extraction issues | Review slot extraction logic and normalization |
| Rate limiting not triggering | Configuration issue | Check rate limit settings in config.py |
| High response times | Resource constraints | Check system resources and optimize queries |
| Missing intent statistics | New intent not added to tracking | Update stats tracking for new intent |
| Citation rate < 100% | Guard failures | Investigate uncited responses in logs |

## Maintenance Recommendations

- Reset statistics counters during deployments
- Archive statistics data periodically
- Adjust rate limits based on production load
- Monitor p95/p99 response times for performance degradation
- Track FCR over time to identify regression in NLP components
