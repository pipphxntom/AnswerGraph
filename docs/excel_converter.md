# Excel Template to JSON DSL Converter

This tool converts the `A2G_templates.xlsx` file, specifically the `FAQ_seed` sheet, into JSON DSL files for the A2G RAG system.

## Purpose

The script reads policy and procedure data from an Excel file and generates standardized JSON files that can be used as input for the RAG system. It groups rows by Source URL to create coherent policy documents.

## Usage

```bash
# Basic usage with default file locations
python src/scripts/process_excel_templates.py

# Specify custom file paths
python src/scripts/process_excel_templates.py --excel-file path/to/your/file.xlsx --output-dir custom/output/directory
```

## Excel File Structure

The Excel file should have a sheet named `FAQ_seed` with the following columns:

- `Source URL`: The URL of the policy document (used for grouping)
- `Title`: Policy title
- `Issuer`: Department or organization issuing the policy
- `Effective Date`: When the policy goes into effect
- `Last Updated`: When the policy was last updated
- `Procedure`: Name of a procedure associated with the policy
- `Applies To`: Who the procedure applies to
- `Deadlines`: Relevant deadlines for the procedure
- `Fees`: Any fees associated with the procedure
- `Contacts`: Contact information for the procedure
- `Citation`: Reference to a specific section of the policy
- `Page`: Page number for the citation
- `Text`: Policy text content

## Output JSON Structure

The script generates one JSON file per unique Source URL with the following structure:

```json
{
  "policy_id": "POL-YYYY-NNNN",
  "title": "Policy Title",
  "issuer": "Department Name",
  "source_url": "https://example.com/policy",
  "procedures": [
    {
      "id": "PROC-XXXXXXXX",
      "name": "Procedure Name",
      "applies_to": "Target Audience",
      "deadlines": "Relevant Deadlines",
      "fees": "Fee Information",
      "contacts": "Contact Information"
    }
  ],
  "citations": [
    {
      "text": "Citation Text",
      "url": "Source URL",
      "page": 123
    }
  ],
  "last_updated": "YYYY-MM-DD",
  "effective_from": "YYYY-MM-DD",
  "text_full": "Combined text content from all rows with the same Source URL"
}
```

## Creating Sample Data

You can create sample data using the included script:

```bash
python src/scripts/create_sample_excel.py
```

This will generate an `A2G_templates.xlsx` file with sample data that you can use to test the converter.
