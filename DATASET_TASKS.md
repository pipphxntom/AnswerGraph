# Dataset Tasks for A2G MVP

This document outlines the CSV schemas and data generation requirements for the Answer Graph (A2G) Minimum Viable Product.

## 1. FAQ Seed Dataset

The FAQ seed dataset will be used to populate the knowledge base with structured intent-based answers.

### Schema: FAQ_seed.csv

| Column | Description |
|--------|-------------|
| Intent | The classified intent type for the FAQ |
| Example question | Sample question that triggers this intent |
| Program | Academic program (BTech, BBA, BSc) |
| Semester | Academic semester (1, 3, 5) |
| Campus | Campus location (Main, City, Hostel) |
| Answer snippet | Concise answer text |
| Source URL | URL to the source document |
| Page | Page number in the source document |
| Clause ID | Unique identifier for the policy clause |
| Last updated | ISO date when the information was last updated |

### Generation Requirements

- Generate 60 rows covering 5 intents: 
  - fee_deadline
  - scholarship_form_deadline
  - timetable_release
  - hostel_fee_due
  - exam_form_deadline
- Vary Program across {BTech, BBA, BSc}
- Vary Semester across {1, 3, 5}
- Vary Campus across {Main, City, Hostel}
- Use ISO dates in YYYY-MM-DD format
- Use plausible Page integers between 1-4
- Use placeholder URLs like https://college.edu/notices/YYYY-MM-DD_<topic>.pdf

### Sample Rows for FAQ_seed.csv

```csv
Intent,Example question,Program,Semester,Campus,Answer snippet,Source URL,Page,Clause ID,Last updated
fee_deadline,When is the fee deadline for BTech semester 1?,BTech,1,Main,The fee deadline for BTech semester 1 at Main campus is October 15 2023.,https://college.edu/notices/2023-08-15_fee_deadlines.pdf,2,FEE-BTech-2023-01,2023-08-15
scholarship_form_deadline,What's the last date to submit merit scholarship forms?,BBA,3,City,The merit scholarship form submission deadline for BBA semester 3 at City campus is September 30 2023.,https://college.edu/notices/2023-07-20_scholarships.pdf,1,SCH-MERIT-2023-05,2023-07-20
timetable_release,When will the BSc semester 5 timetable be released?,BSc,5,Main,The timetable for BSc semester 5 at Main campus will be released on August 25 2023.,https://college.edu/notices/2023-08-10_timetables.pdf,3,TT-BSc-2023-02,2023-08-10
```

## 2. Gold Test Dataset

The gold test dataset will be used for evaluating the system's performance with a variety of query inputs.

### Schema: Gold_tests.csv

| Column | Description |
|--------|-------------|
| Query | The user query text |
| Language | Language of the query (en, hi, hi-en) |
| Expected intent | The expected intent classification |
| Program | Expected program extraction |
| Semester | Expected semester extraction |
| Campus | Expected campus extraction |
| Expected citation filename | Filename part of the expected citation |
| Expected page | Expected page number in the citation |
| Expected fields (JSON) | JSON object with expected extracted fields |
| Notes | Additional testing notes |

### Generation Requirements

- Generate 200 queries mixing:
  - English (standard)
  - Hinglish (Hindi-English mix)
  - Hindi (transliterated to Latin script)
  - Include common typos and variations
- Fill Expected fields (JSON) for dates/fees
- Provide a good mix of queries for all 5 intents
- Include edge cases and potential confusion cases

### Sample Rows for Gold_tests.csv

```csv
Query,Language,Expected intent,Program,Semester,Campus,Expected citation filename,Expected page,Expected fields (JSON),Notes
When is the fee due for BTech first sem?,en,fee_deadline,BTech,1,Main,fee_deadlines.pdf,2,"{""deadline"":""2023-10-15""}",Standard query
BTech fee payment ki last date kya hai?,hi-en,fee_deadline,BTech,null,null,fee_deadlines.pdf,2,"{""deadline"":""2023-10-15""}",Hinglish query missing semester
BBA ka scholarship form kb tk submit krna h?,hi-en,scholarship_form_deadline,BBA,null,null,scholarships.pdf,1,"{""deadline"":""2023-09-30""}",Hinglish with abbreviations
Main campus hostel fees kab tak bharne hai?,hi,hostel_fee_due,null,null,Main,hostel_fees.pdf,2,"{""deadline"":""2023-09-15""}",Hindi query for hostel fees
```

## 3. Validation Checklist

Before finalizing the datasets, verify the following:

- [ ] No empty URLs in any row
- [ ] Page is always an integer between 1-4
- [ ] All dates follow ISO format (YYYY-MM-DD)
- [ ] Answer snippets are concise and factually correct
- [ ] All snippets are copied/derived from actual sources
- [ ] Intent distribution is balanced (approximately 12 rows per intent)
- [ ] Adequate variation in Program, Semester, and Campus values
- [ ] All Clause IDs follow a consistent format
- [ ] Variety of query phrasings in the gold test dataset
- [ ] Mix of languages (60% English, 30% Hinglish, 10% Hindi)
- [ ] Gold test dataset includes common typos and variations

## 4. Data Generation Process

1. First generate the FAQ seed dataset with authoritative answers
2. Then create the gold test dataset that references answers from the seed dataset
3. Validate both datasets against the checklist
4. Convert to appropriate formats for import into the system
5. Document any special cases or exceptions for future reference
