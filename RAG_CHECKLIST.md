# RAG Path Validation Checklist

This document provides a structured approach to validate the RAG (Retrieval Augmented Generation) path in the A2G system, focusing on handling messy and multilingual queries.

## Test Queries and Expected Checks

Below are five challenging queries designed to test the RAG system's robustness. Each query should be validated against the listed checks.

### Query 1: Misspelled English Query

```
when iz teh BTec 1st sem fee paymeent dedline for main cmpus?
```

**Checks:**
- [ ] `mode` is "rag" in the response
- [ ] `intent` is recognized as "fee_deadline"
- [ ] `sources` array is non-empty
- [ ] Each source has `url` and `page` fields
- [ ] Answer includes a date that appears in the evidence texts
- [ ] `confidence` score is present and reasonable (>0.7)
- [ ] The extracted slots match: program="BTech", semester=1, campus="Main"

### Query 2: Hinglish Query

```
BBA ke 3rd semester ka timetable kab release hoga city campus me?
```

**Checks:**
- [ ] `mode` is "rag" in the response
- [ ] `intent` is recognized as "timetable_release"
- [ ] `sources` array is non-empty
- [ ] Each source has `url` and `page` fields
- [ ] Answer includes a date that appears in the evidence texts
- [ ] `confidence` score is present and reasonable (>0.7)
- [ ] The extracted slots match: program="BBA", semester=3, campus="City"
- [ ] Language is properly detected as "hi-en" (Hinglish)

### Query 3: Hindi Query (Transliterated)

```
hostel fee jama karne ki antim tithi kya hai main campus ke liye?
```

**Checks:**
- [ ] `mode` is "rag" in the response
- [ ] `intent` is recognized as "hostel_fee_due"
- [ ] `sources` array is non-empty
- [ ] Each source has `url` and `page` fields
- [ ] Answer includes a date that appears in the evidence texts
- [ ] `confidence` score is present and reasonable (>0.7)
- [ ] The extracted slots match: campus="Main"
- [ ] Language is properly detected as "hi" (Hindi)

### Query 4: Mixed Script with Numbers

```
BSc 5th sem ka exam form last date kab hai? 2023 me kitne din hai?
```

**Checks:**
- [ ] `mode` is "rag" in the response
- [ ] `intent` is recognized as "exam_form_deadline"
- [ ] `sources` array is non-empty
- [ ] Each source has `url` and `page` fields
- [ ] Answer includes a date that appears in the evidence texts
- [ ] All numbers in the answer (dates, counts) appear in the evidence
- [ ] `confidence` score is present and reasonable (>0.7)
- [ ] The extracted slots match: program="BSc", semester=5
- [ ] Numeric guard passes (all numbers in answer appear in evidence)

### Query 5: Ambiguous Query with Typos

```
scolrship ki lst dte cty campus m?
```

**Checks:**
- [ ] `mode` is "rag" in the response OR "disambiguation" if slots are incomplete
- [ ] `intent` is recognized as "scholarship_form_deadline"
- [ ] If `mode` is "rag", `sources` array is non-empty
- [ ] If `mode` is "rag", each source has `url` and `page` fields
- [ ] If `mode` is "rag", answer includes a date that appears in the evidence texts
- [ ] If `mode` is "disambiguation", appropriate chips are provided
- [ ] `confidence` score is present
- [ ] The extracted slots match: campus="City"
- [ ] System handles extreme abbreviations and typos

## Guard Validation Checks

For each query response, verify that the following guards are applied correctly:

### Citation Guard
- [ ] Answer includes at least one source citation
- [ ] Each citation has a URL and page number
- [ ] Citations match relevant sources in the database

### Numeric Consistency Guard
- [ ] All numbers in the answer appear in the evidence texts
- [ ] Dates in the answer match dates in the evidence
- [ ] Any monetary amounts match amounts in the evidence
- [ ] No hallucinated numeric values

### Temporal Guard
- [ ] If multiple policies exist, the most recent one is used
- [ ] Outdated policies (>180 days old) are not used if newer ones exist
- [ ] Dates are formatted consistently

### Confidence Scoring
- [ ] Confidence score reflects the quality of the answer
- [ ] Low confidence (<0.7) correlates with more uncertain answers
- [ ] High confidence (>0.85) correlates with precise answers

## If RAG Path Fails

If the RAG path fails any of the above checks, consider implementing the following fixes:

### 1. Normalization Rules

**Issues Addressed:**
- Misspellings
- Abbreviations
- Transliteration variations

**Implementation Steps:**
1. Add additional text normalization rules to `src/nlp/normalize.py`
2. Include common misspellings for program names (e.g., "BTec" → "BTech")
3. Add abbreviation expansion (e.g., "sem" → "semester")
4. Implement character-level normalization for Hinglish text
5. Add special handling for numeric expressions (e.g., "1st" → "1")

**Example Rule:**
```python
def normalize_program_names(text):
    replacements = {
        r'\bb\.?tech\b': 'BTech',
        r'\bb\.?b\.?a\b': 'BBA',
        r'\bb\.?sc\b': 'BSc',
        # Add more variations
    }
    
    for pattern, replacement in replacements.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    
    return text
```

### 2. Retrieval Parameters

**Issues Addressed:**
- Missing relevant documents
- Low recall in vector search
- Incorrect intent classification

**Implementation Steps:**
1. Increase `top_k` parameter in retriever from current value to 15-20
2. Adjust embedding model parameters for better multilingual support
3. Lower the similarity threshold to capture more potential matches
4. Implement hybrid retrieval (combining vector search with keyword search)

**Example Configuration:**
```python
# Update in src/rag/retriever.py
async def retrieve_documents(query, limit=20, filters=None):
    # Increase top_k to improve recall
    top_k = min(20, limit * 2)  # Get more candidates for reranking
    
    # Implement hybrid retrieval
    vector_results = await vector_search(query, top_k=top_k)
    keyword_results = keyword_search(query, limit=top_k)
    
    # Combine results with deduplication
    combined_results = merge_and_deduplicate(vector_results, keyword_results)
    
    return combined_results[:limit]
```

### 3. Reranker Improvements

**Issues Addressed:**
- Poor ranking of retrieved documents
- Irrelevant documents ranked too high
- Relevant content buried in results

**Implementation Steps:**
1. Increase `top_n` parameter in reranker from current value to 8-10
2. Adjust cross-encoder model parameters
3. Implement domain-specific reranking features
4. Add boosting for documents containing slots from the query

**Example Configuration:**
```python
# Update in src/rag/reranker.py
def cross_encode_rerank(query, candidates, top_n=10):
    # Increase top_n to include more candidates in final results
    
    # Extract potential slots from query
    slots = extract_potential_slots(query)
    
    # Boost scores for documents containing slots
    boosted_scores = []
    for i, (score, doc) in enumerate(zip(scores, candidates)):
        boost = calculate_slot_match_boost(doc, slots)
        boosted_scores.append((score + boost, i))
    
    # Sort by boosted score and return top_n
    boosted_scores.sort(reverse=True)
    top_indices = [idx for _, idx in boosted_scores[:top_n]]
    
    return [candidates[i] for i in top_indices]
```

## Performance Tracking

| Query | Date Tested | Success | Confidence | Processing Time (ms) | Notes |
|-------|-------------|---------|------------|----------------------|-------|
| Query 1 | | | | | |
| Query 2 | | | | | |
| Query 3 | | | | | |
| Query 4 | | | | | |
| Query 5 | | | | | |

## Periodic Validation Schedule

- Perform full RAG validation after any code changes affecting the RAG pipeline
- Run basic RAG checks weekly on production system
- Conduct comprehensive validation monthly with all test queries
- Update normalization rules based on failed queries from production logs
