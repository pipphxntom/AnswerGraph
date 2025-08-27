# A2G Documentation

This documentation covers key components of the A2G system including policy loading, retrieval, and reranking functionality.

## Policy JSON Loading Functions

This module provides functions for loading policy JSON files into the database using SQLAlchemy 2.0's async ORM.

## Overview

The module includes:

1. `load_policy_json(path, session)` - Load a single policy JSON file
2. `load_dir(dirpath)` - Load all policy JSON files from a directory

## Usage Examples

### From the Command Line

Process an Excel file and load the generated JSON files into the database:

```bash
python -m src.scripts.process_excel_templates --excel-file A2G_templates.xlsx --output-dir data/policies --load
```

Skip Excel processing and just load existing JSON files:

```bash
python -m src.scripts.process_excel_templates --skip-excel --load-dir data/policies
```

### From Your Application Code

To load a single policy file:

```python
import asyncio
from src.scripts.process_excel_templates import load_policy_json
from src.core.db import async_session_factory

async def load_policy():
    async with async_session_factory() as session:
        try:
            policy, procedures, sources = await load_policy_json("data/policies/example.json", session)
            await session.commit()
            print(f"Loaded policy {policy.id} with {len(procedures)} procedures and {len(sources)} sources")
        except Exception as e:
            await session.rollback()
            print(f"Error: {str(e)}")

# Run the async function
asyncio.run(load_policy())
```

To load all policies from a directory:

```python
import asyncio
from src.scripts.process_excel_templates import load_dir

async def load_policies():
    counts = await load_dir("data/policies")
    print(f"Loaded {counts['policies']} policies, {counts['procedures']} procedures, {counts['sources']} sources")
    if counts['errors'] > 0:
        print(f"Encountered {counts['errors']} errors")

# Run the async function
asyncio.run(load_policies())
```

## Function Details

### load_policy_json

```python
async def load_policy_json(path: str, session: AsyncSession) -> Tuple[Policy, List[Procedure], List[Source]]:
    """
    Load a policy JSON DSL file and upsert to the database.
    
    Args:
        path: Path to the JSON file
        session: AsyncSession for database operations
        
    Returns:
        Tuple of (Policy, List[Procedure], List[Source]) objects
    """
```

This function:
- Reads a JSON policy file
- Creates or updates a Policy record
- Creates or updates related Procedure records
- Creates or updates related Source records
- Returns the created/updated records
- Does NOT commit the session (caller must commit)

### load_dir

```python
async def load_dir(dirpath: str) -> Dict[str, int]:
    """
    Load all JSON policy files from a directory into the database.
    
    Args:
        dirpath: Path to directory containing JSON files
        
    Returns:
        Dictionary with counts of loaded entities
    """
```

This function:
- Scans a directory for JSON files
- Creates a database session
- Processes each file with load_policy_json
- Handles errors for individual files
- Commits all changes in a single transaction
- Returns counts of loaded entities

## Error Handling

Both functions handle errors appropriately:

- `load_policy_json` may raise exceptions that should be caught by the caller
- `load_dir` catches exceptions for individual files but may still raise exceptions for critical errors

## Transaction Management

- `load_policy_json` does not commit the session, allowing it to be part of a larger transaction
- `load_dir` manages its own transaction and commits all changes at once

## Retrieval and Reranking

The A2G system implements a sophisticated retrieval pipeline that includes:

1. **Vector Search**: Using SentenceTransformer embeddings and Qdrant
2. **Lexical Search**: Using BM25 for keyword matching
3. **Hybrid Retrieval**: Combining vector and lexical search
4. **Cross-Encoder Reranking**: Fine-grained reranking of candidate results

### Cross-Encoder Reranking

The cross-encoder reranking component is implemented in `src/rag/reranker.py` and provides significantly improved relevance ranking by performing detailed query-document comparison.

```python
from src.rag.reranker import cross_encode_rerank

# Get initial candidates (e.g., from hybrid retrieval)
candidates = hybrid_retrieve(query, ...)

# Rerank with cross-encoder
reranked_results = cross_encode_rerank(
    query=query,
    candidates=candidates,
    top_n=8,  # Return top 8 results
    model_name="mixedbread-ai/mxbai-rerank-large-v1"
)
```

#### Key Features:

- Uses the powerful `mixedbread-ai/mxbai-rerank-large-v1` cross-encoder model
- Preserves original scores while adding cross-encoder scores
- Configurable number of final results
- Handles both "text" and "content" fields automatically
- Returns top_n documents with final_score field added

#### Implementation Details:

```python
def cross_encode_rerank(
    query: str, 
    candidates: List[Dict[str, Any]], 
    top_n: int = 8,
    model_name: str = "mixedbread-ai/mxbai-rerank-large-v1"
) -> List[Dict[str, Any]]:
    """
    Rerank candidates using a cross-encoder model.
    
    Args:
        query: The search query
        candidates: List of candidate documents to rerank
        top_n: Number of top candidates to return after reranking
        model_name: Name of the cross-encoder model to use
        
    Returns:
        List of top_n documents reranked by relevance with final_score
    """
```

This function takes a query and list of candidate documents, and returns a reordered list with the most relevant documents first, based on the cross-encoder scoring.

### Demo Script

A demonstration script is provided at `rerank_demo.py` that shows the complete two-stage retrieval pipeline:

```bash
python rerank_demo.py "employee conduct guidelines"
```

Options:
- `--first-stage`: Number of candidates to retrieve in first stage (default: 20)
- `--final`: Number of final results after reranking (default: 8)
- `--model`: Cross-encoder model to use (default: mixedbread-ai/mxbai-rerank-large-v1)
- `--collection`: Qdrant collection name (default: a2g_chunks)
- `--no-details`: Hide scoring details in output

## RAG Guard Functions

The A2G system implements several guard functions to ensure high-quality and factually accurate answers. These guards are implemented in `src/rag/guards.py` and provide a comprehensive set of checks for RAG system outputs.

### Guard Functions Overview

1. **Citation Guard** - Ensures answers include proper citations with source URLs and page numbers
2. **Temporal Guard** - Verifies sources are temporally valid and up-to-date
3. **Numeric Consistency Guard** - Ensures numeric values in answers appear in evidence
4. **Confidence Gate** - Computes final confidence score and applies thresholding

### Citation Guard

```python
def require_citation(answer: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Verify that the answer contains at least one source citation with URL and page.
    """
```

This guard ensures that answers include proper citations with both a URL and page number. This prevents unsourced claims and provides traceability back to original documents.

### Temporal Guard

```python
async def temporal_guard(sources: List[Dict[str, Any]], session: AsyncSession) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Check temporal validity of sources used in the answer.
    """
```

Key features:
- Prefers policies with the most recent effective date
- Rejects answers if all sources are older than 180 days and newer policies exist
- Identifies the preferred source for the answer
- Requires database access to check policy metadata

### Numeric Consistency Guard

```python
def numeric_consistency(answer_text: str, evidence_texts: List[str]) -> Tuple[bool, str, List[str]]:
    """
    Verify that all dates and numeric amounts in the answer appear in at least one evidence text.
    """
```

This guard:
- Extracts dates, dollar amounts, percentages, and other numeric values from answers
- Verifies each value appears in at least one evidence text
- Helps prevent hallucinated numbers, dates, and amounts
- Uses regex patterns to identify different types of numeric values

### Confidence Gate

```python
def confidence_gate(
    margin: float, 
    coverage: float, 
    lang_ok: bool, 
    factual_score: Optional[float] = None,
    source_quality: Optional[float] = None
) -> Tuple[bool, float, str]:
    """
    Compute final confidence score and apply thresholding.
    """
```

This function:
- Combines multiple quality signals into a single confidence score
- Applies weighted scoring based on retrieval margin, evidence coverage, language quality, etc.
- Uses customizable thresholding to determine if an answer meets quality standards
- Provides flexibility with optional quality signals

### Using the Guard Functions

A demonstration script is provided at `guard_demo.py` that shows how to use the guard functions:

```bash
python guard_demo.py
```

Options:
- `--input`: Path to JSON file with sample answer
- `--skip-temporal`: Skip temporal guard check
- `--skip-numeric`: Skip numeric consistency check
- `--skip-confidence`: Skip confidence gate check
- `--create-bad-answer`: Create a sample answer that fails checks

## Intent Classification and API Router

The A2G system implements intent classification and a FastAPI router for handling both rule-based and RAG-based queries.

### Intent Classification

The intent classification system is implemented in `src/rag/intent_classifier.py` and uses pattern matching with RapidFuzz to classify intents and extract slots from user queries.

```python
def classify_intent_and_slots(text: str) -> Tuple[str, Dict[str, str], float]:
    """
    Classify the intent of a text and extract slots.
    
    Returns:
        Tuple of (intent, slots, confidence)
    """
```

Key features:
- Uses fuzzy matching to identify intents from predefined patterns
- Extracts slots like program, semester, and campus using regex and fuzzy matching
- Returns a confidence score based on pattern match and slot filling
- Falls back to "freeform" intent for queries that don't match rule-based intents

The system supports the following rule-based intents:
- `deadline_inquiry`: Questions about deadlines and due dates
- `fee_inquiry`: Questions about costs and fees
- `program_info`: Questions about program details
- `application_process`: Questions about how to apply
- `registration_process`: Questions about how to register
- `contact_info`: Questions about who to contact
- `campus_services`: Questions about services at different campuses

### Rule-Based Answers

For queries that match rule-based intents with high confidence, the system uses structured data from the database to generate answers. This is implemented in `src/rag/rule_answers.py`.

```python
async def answer_from_rules(
    intent: str,
    slots: Dict[str, str],
    session: AsyncSession
) -> Optional[AnswerContract]:
    """
    Generate an answer from rules based on intent and slots.
    """
```

The system extracts relevant information from the database based on the intent and slots, and returns a structured answer with proper source attribution.

### FastAPI Router

The API router is implemented in `src/api/ask_routes.py` and provides endpoints for asking questions, checking system health, and retrieving statistics.

#### Ask Endpoint

```
POST /ask
```

Request body:
```json
{
  "text": "What is the deadline for applying to the computer science program?",
  "lang": "en",
  "ctx": {}
}
```

Response:
```json
{
  "text": "For computer science, the application deadline is May 1, 2025.",
  "sources": [
    {
      "policy_id": "P-2024-01",
      "procedure_id": "PROC-2024-01",
      "url": "/policies/P-2024-01",
      "name": "Computer Science Application Procedure",
      "page": null
    }
  ],
  "intent": "deadline_inquiry",
  "slots": {
    "program": "computer science"
  },
  "confidence": 0.85,
  "processing_time": 156.42,
  "updated_date": "2025-08-28T14:30:00"
}
```

The endpoint follows these steps:
1. Classify the intent and extract slots from the query
2. If a rule-based intent is identified with sufficient confidence, generate an answer using rule-based logic
3. Otherwise, use the RAG pipeline (retrieve → rerank → compose) to generate an answer

#### Health Check Endpoint

```
GET /health
```

Response:
```json
{
  "status": "ok",
  "version": "0.1.0",
  "uptime": 3600,
  "timestamp": "2025-08-28T14:30:00"
}
```

#### Statistics Endpoint

```
GET /stats
```

Response:
```json
{
  "total_requests": 100,
  "rule_based_responses": 35,
  "rag_responses": 65,
  "intent_distribution": {
    "deadline_inquiry": 20,
    "fee_inquiry": 15,
    "freeform": 65
  },
  "avg_response_time": 150.5
}
```

### Demo Script

A demonstration script is provided at `intent_demo.py` that shows how the intent classification works:

```bash
python intent_demo.py
```

Options:
- `--interactive`: Run in interactive mode
- `--query`: Test specific queries
- `--list-intents`: List available rule-based intents

## Deterministic Fetch

The A2G system includes a deterministic fetch module for structured data retrieval that joins the Procedure, Policy, and Source models to provide consistent, formatted results.

### Overview

The deterministic fetch functionality is implemented in `src/rag/deterministic_fetch.py` and provides a way to retrieve structured data with proper source attribution in a format suitable for direct use in API responses.

```python
async def deterministic_fetch(
    session: AsyncSession,
    query_type: str,
    params: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Perform a deterministic fetch based on query type and parameters.
    """
```

The result format is:

```json
{
  "answer": "Information about the requested data",
  "fields": {
    "key1": "value1",
    "key2": "value2",
    ...
  },
  "source": {
    "url": "https://example.com/policy",
    "page": 5,
    "title": "Policy Title",
    "updated_at": "2025-08-28T14:30:00"
  }
}
```

### Key Features

1. **Joined Data**: Automatically joins Procedure, Policy, and Source models
2. **Structured Format**: Returns data in a consistent, structured format
3. **Source Attribution**: Includes source information with URL, page, and title
4. **Metadata Preservation**: Keeps important metadata like update dates
5. **Query Types**: Supports different query types for various use cases

### Query Types

The deterministic fetch supports the following query types:

- `procedure`: Fetches procedure data by ID or policy ID
- `program_info`: Fetches information about a specific program
- `deadline_info`: Fetches deadline information for a program/term
- `fee_info`: Fetches fee information for a program/term

### Integration with Rule-Based Answers

The deterministic fetch is integrated with the rule-based answer system:

```python
async def answer_from_rules(intent, slots, session):
    # Map intents to query types
    query_type_map = {
        "deadline_inquiry": "deadline_info",
        "fee_inquiry": "fee_info",
        ...
    }
    
    # Get query type for this intent
    query_type = query_type_map.get(intent)
    
    # Execute deterministic fetch
    result = await deterministic_fetch(session, query_type, fetch_params)
    
    # Create answer contract from result
    return AnswerContract(...)
```

### Demo Script

A demonstration script is provided at `deterministic_fetch_demo.py`:

```bash
# Query procedure by ID
python deterministic_fetch_demo.py procedure --id PROC-2024-01

# Query by program
python deterministic_fetch_demo.py program "computer science" --term "fall 2025"

# Run deterministic query
python deterministic_fetch_demo.py query deadline_info --program "computer science" --term "fall 2025"
```

The guard functions can be integrated into your RAG pipeline to filter or flag problematic answers before they reach users:

```python
from src.rag.guards import require_citation, numeric_consistency, confidence_gate

# Check an answer
citation_passed, msg = require_citation(answer)
if not citation_passed:
    # Handle uncited answer
    print(f"Citation check failed: {msg}")
    
# Check numeric consistency
numeric_passed, msg, missing = numeric_consistency(answer_text, evidence_texts)
if not numeric_passed:
    # Handle numeric inconsistencies
    print(f"Numeric check failed: {msg}")
    print(f"Missing values: {missing}")
    
# Apply confidence gate
confidence_passed, score, msg = confidence_gate(
    margin=0.8, 
    coverage=0.9, 
    lang_ok=True, 
    factual_score=0.85
)
if not confidence_passed:
    # Handle low confidence answer
    print(f"Confidence check failed: {msg}")
```
