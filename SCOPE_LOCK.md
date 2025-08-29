# A2G MVP Scope Lock

This document defines the locked scope for the Answer Graph (A2G) Minimum Viable Product, specifying the supported intents, their slot requirements, and field mappings to database entities.

## MVP Intent Definitions

The following five intents are included in the MVP scope:

### 1. fee_deadline

**Description:** Provides information about payment deadlines for various academic programs and semesters.

**Required Slots:**
- `program`: Academic program (e.g., BTech, BBA, BSc)
- `semester`: Academic semester (e.g., 1, 3, 5)
- `campus`: Campus location (e.g., Main, City, Hostel)

**DSL Field Mappings:**
```
fee_deadline → {program, semester, campus} → Procedure.deadlines, Source(page, url)
```

**Example Query:**
> "When is the fee deadline for BTech semester 1 at Main campus?"

**Response Format:**
> "The fee deadline for BTech semester 1 at Main campus is [DATE]."

### 2. scholarship_form_deadline

**Description:** Provides submission deadlines for scholarship applications.

**Required Slots:**
- `campus`: Campus location (e.g., Main, City, Hostel)

**Optional Slots:**
- `scholarship_type`: Type of scholarship (e.g., merit, need-based, sports)

**DSL Field Mappings:**
```
scholarship_form_deadline → {campus} → Procedure.deadlines
```

**Example Query:**
> "What is the last date to submit scholarship forms at City campus?"

**Response Format:**
> "The scholarship form submission deadline for City campus is [DATE]."

### 3. timetable_release

**Description:** Provides information about when course timetables will be released.

**Required Slots:**
- `program`: Academic program (e.g., BTech, BBA, BSc)
- `semester`: Academic semester (e.g., 1, 3, 5)
- `campus`: Campus location (e.g., Main, City, Hostel)

**DSL Field Mappings:**
```
timetable_release → {program, semester, campus} → Calendar.release_date
```

**Example Query:**
> "When will the BSc semester 5 timetable be released for Main campus?"

**Response Format:**
> "The timetable for BSc semester 5 at Main campus will be released on [DATE]."

### 4. hostel_fee_due

**Description:** Provides information about hostel fee payment deadlines.

**Required Slots:**
- `campus`: Campus location (e.g., Main, City, Hostel)

**DSL Field Mappings:**
```
hostel_fee_due → {campus} → Procedure.deadlines + fees
```

**Example Query:**
> "What is the last date to pay hostel fees for Main campus?"

**Response Format:**
> "The hostel fee payment deadline for Main campus is [DATE]. The fee amount is [AMOUNT]."

### 5. exam_form_deadline

**Description:** Provides information about examination form submission deadlines.

**Required Slots:**
- `program`: Academic program (e.g., BTech, BBA, BSc)
- `semester`: Academic semester (e.g., 1, 3, 5)

**DSL Field Mappings:**
```
exam_form_deadline → {program, semester} → Procedure.deadlines
```

**Example Query:**
> "When is the last date to submit exam forms for BTech semester 3?"

**Response Format:**
> "The exam form submission deadline for BTech semester 3 is [DATE]."

## Quality Gates

The following quality gates must be met for MVP release:

### Functional Gates

| Metric | Threshold | Measurement |
|--------|-----------|-------------|
| Citation Rate | ≥ 0.85 | Number of answers with valid citations / Total number of answers |
| Field Correctness Rate (FCR) | ≥ 0.85 | Number of correctly extracted slots / Total number of extracted slots |
| Uncited Answers | 0 | No answers should be provided without citations |

### Performance Gates

| Metric | Threshold | Measurement |
|--------|-----------|-------------|
| p95 Response Time | ≤ 2000 ms | 95th percentile of end-to-end response time |
| Availability | ≥ 99.5% | System uptime during working hours |

## Disambiguation Strategy

When required slots are missing, the system should:

1. Return a disambiguation response with mode="disambiguation"
2. Include chips for the missing slots
3. Preserve the context for the next turn

Example missing program:
```json
{
  "mode": "disambiguation",
  "text": "Could you please specify which program you're asking about?",
  "chips": {
    "program": ["BTech", "BBA", "BSc"]
  }
}
```

## Out of Scope for MVP

The following are explicitly out of scope for the MVP:

1. Free-form RAG answers outside the 5 defined intents
2. Multiple intent handling in a single query
3. Document uploading via the API
4. User authentication and personalization
5. Multi-turn conversations beyond disambiguation
6. Intents beyond the 5 defined above

## Testing Requirements

1. Unit tests for each intent handler function
2. Integration tests for the entire pipeline
3. Gold tests against the 200-query dataset
4. Performance tests at 10x expected load
5. Citation validation tests
