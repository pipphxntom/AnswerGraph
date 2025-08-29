# Rules Path Audit Checklist

This document provides a comprehensive audit checklist for each supported intent in the rules-based answer path.

## Intent Requirements Table

| Intent | Required Slots | Sources | Evidence | Answer Validation | Empty Evidence Handling | Verified ✓ |
|--------|---------------|---------|----------|-------------------|-------------------------|------------|
| fee_deadline | program, semester, campus | | | | | □ |
| scholarship_form_deadline | campus, (opt) scholarship_type | | | | | □ |
| timetable_release | program, semester, campus | | | | | □ |
| hostel_fee_due | campus | | | | | □ |
| exam_form_deadline | program, semester | | | | | □ |

## Intent: fee_deadline

### Required Context Slots
- `program`: Academic program (BTech, BBA, BSc)
- `semester`: Academic semester (1, 3, 5)
- `campus`: Campus location (Main, City, Hostel)

### AnswerContract Validation
- [ ] `mode` is set to "rules"
- [ ] `intent` is set to "fee_deadline"
- [ ] `answer` contains formatted text with deadline
- [ ] `sources` array contains at least one item
- [ ] Each source has `url`, `page`, `title`, and `updated_at` fields
- [ ] `evidence_texts` array contains at least one item
- [ ] `ctx` contains the original extracted slots

### Answer Text Verification
- [ ] Answer mentions the program name
- [ ] Answer mentions the semester number
- [ ] Answer mentions the campus
- [ ] Deadline date matches the source data
- [ ] Date format is consistent (e.g., "October 15, 2023")
- [ ] No placeholder text or "[PLACEHOLDER]" markers

### Empty Evidence Handling
- [ ] If `evidence_texts` is empty, system attempts to fetch from adjacent pages
- [ ] If no chunks found, returns a fallback message: "No specific content found for this reference. Please refer to the source document."
- [ ] System logs a warning when evidence text cannot be found

## Intent: scholarship_form_deadline

### Required Context Slots
- `campus`: Campus location (Main, City, Hostel)

### Optional Context Slots
- `scholarship_type`: Type of scholarship (merit, need-based, sports)

### AnswerContract Validation
- [ ] `mode` is set to "rules"
- [ ] `intent` is set to "scholarship_form_deadline"
- [ ] `answer` contains formatted text with deadline
- [ ] `sources` array contains at least one item
- [ ] Each source has `url`, `page`, `title`, and `updated_at` fields
- [ ] `evidence_texts` array contains at least one item
- [ ] `ctx` contains the original extracted slots

### Answer Text Verification
- [ ] Answer mentions the campus
- [ ] If provided, answer mentions the scholarship type
- [ ] Deadline date matches the source data
- [ ] Date format is consistent (e.g., "September 30, 2023")
- [ ] No placeholder text or "[PLACEHOLDER]" markers

### Empty Evidence Handling
- [ ] If `evidence_texts` is empty, system attempts to fetch from adjacent pages
- [ ] If no chunks found, returns a fallback message: "No specific content found for this reference. Please refer to the source document."
- [ ] System logs a warning when evidence text cannot be found

## Intent: timetable_release

### Required Context Slots
- `program`: Academic program (BTech, BBA, BSc)
- `semester`: Academic semester (1, 3, 5)
- `campus`: Campus location (Main, City, Hostel)

### AnswerContract Validation
- [ ] `mode` is set to "rules"
- [ ] `intent` is set to "timetable_release"
- [ ] `answer` contains formatted text with release date
- [ ] `sources` array contains at least one item
- [ ] Each source has `url`, `page`, `title`, and `updated_at` fields
- [ ] `evidence_texts` array contains at least one item
- [ ] `ctx` contains the original extracted slots

### Answer Text Verification
- [ ] Answer mentions the program name
- [ ] Answer mentions the semester number
- [ ] Answer mentions the campus
- [ ] Release date matches the source data
- [ ] Date format is consistent (e.g., "August 25, 2023")
- [ ] No placeholder text or "[PLACEHOLDER]" markers
- [ ] Uses "will be released" phrasing for future dates

### Empty Evidence Handling
- [ ] If `evidence_texts` is empty, system attempts to fetch from adjacent pages
- [ ] If no chunks found, returns a fallback message: "No specific content found for this reference. Please refer to the source document."
- [ ] System logs a warning when evidence text cannot be found

## Intent: hostel_fee_due

### Required Context Slots
- `campus`: Campus location (Main, City, Hostel)

### AnswerContract Validation
- [ ] `mode` is set to "rules"
- [ ] `intent` is set to "hostel_fee_due"
- [ ] `answer` contains formatted text with deadline
- [ ] `sources` array contains at least one item
- [ ] Each source has `url`, `page`, `title`, and `updated_at` fields
- [ ] `evidence_texts` array contains at least one item
- [ ] `ctx` contains the original extracted slots

### Answer Text Verification
- [ ] Answer mentions the campus
- [ ] Deadline date matches the source data
- [ ] Date format is consistent (e.g., "September 15, 2023")
- [ ] If available in source, fee amount is included and matches source data
- [ ] No placeholder text or "[PLACEHOLDER]" markers

### Empty Evidence Handling
- [ ] If `evidence_texts` is empty, system attempts to fetch from adjacent pages
- [ ] If no chunks found, returns a fallback message: "No specific content found for this reference. Please refer to the source document."
- [ ] System logs a warning when evidence text cannot be found

## Intent: exam_form_deadline

### Required Context Slots
- `program`: Academic program (BTech, BBA, BSc)
- `semester`: Academic semester (1, 3, 5)

### AnswerContract Validation
- [ ] `mode` is set to "rules"
- [ ] `intent` is set to "exam_form_deadline"
- [ ] `answer` contains formatted text with deadline
- [ ] `sources` array contains at least one item
- [ ] Each source has `url`, `page`, `title`, and `updated_at` fields
- [ ] `evidence_texts` array contains at least one item
- [ ] `ctx` contains the original extracted slots

### Answer Text Verification
- [ ] Answer mentions the program name
- [ ] Answer mentions the semester number
- [ ] Deadline date matches the source data
- [ ] Date format is consistent (e.g., "November 10, 2023")
- [ ] No placeholder text or "[PLACEHOLDER]" markers

### Empty Evidence Handling
- [ ] If `evidence_texts` is empty, system attempts to fetch from adjacent pages
- [ ] If no chunks found, returns a fallback message: "No specific content found for this reference. Please refer to the source document."
- [ ] System logs a warning when evidence text cannot be found

## Audit Process

1. For each intent, run a sample query with all required slots
2. Examine the AnswerContract fields in the response
3. Verify the answer text contains all required information
4. Check if all dates and amounts match the evidence texts
5. Test empty evidence handling by using a query with valid slots but missing source content

## Edge Cases to Test

1. **Outdated Source**: Query with slots that match an outdated policy (should return the most recent policy)
2. **Missing Page**: Query with slots that match a source with missing page number (should use default page 1)
3. **Slot Variations**: Test with variations of slot values (e.g., "BTech" vs "B.Tech" vs "B Tech")
4. **Future Dates**: Verify correct phrasing for deadlines in the future vs. past

## Status Tracking

| Intent | Last Audited | Status | Auditor | Notes |
|--------|--------------|--------|---------|-------|
| fee_deadline | | | | |
| scholarship_form_deadline | | | | |
| timetable_release | | | | |
| hostel_fee_due | | | | |
| exam_form_deadline | | | | |
