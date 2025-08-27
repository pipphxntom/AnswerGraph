"""
Create a sample A2G_templates.xlsx file for testing.

This script creates a sample Excel file with the FAQ_seed sheet
that can be used to test the process_excel_templates.py script.
"""
import os
import pandas as pd
from datetime import datetime, timedelta

def create_sample_excel():
    """Create a sample Excel file with the FAQ_seed sheet."""
    # Create output directory if it doesn't exist
    os.makedirs("data", exist_ok=True)
    
    # Sample data
    data = [
        # Policy 1 - Multiple rows with the same Source URL
        {
            "Source URL": "https://example.com/policy1",
            "Title": "Remote Work Policy",
            "Issuer": "HR Department",
            "Effective Date": datetime.now() - timedelta(days=30),
            "Last Updated": datetime.now() - timedelta(days=5),
            "Procedure": "Request Remote Work",
            "Applies To": "All Employees",
            "Deadlines": "Submit requests 2 weeks in advance",
            "Fees": None,
            "Contacts": "hr@example.com",
            "Citation": "Section 2.1 of Employee Handbook",
            "Page": 12,
            "Text": "Employees may request to work remotely up to 3 days per week."
        },
        {
            "Source URL": "https://example.com/policy1",
            "Title": "Remote Work Policy",
            "Issuer": "HR Department",
            "Effective Date": datetime.now() - timedelta(days=30),
            "Last Updated": datetime.now() - timedelta(days=5),
            "Procedure": "Set Up Home Office",
            "Applies To": "Remote Employees",
            "Deadlines": "Within 30 days of approval",
            "Fees": "Up to $500 reimbursement available",
            "Contacts": "it_support@example.com",
            "Citation": "Section 2.3 of Employee Handbook",
            "Page": 14,
            "Text": "Employees must ensure they have adequate internet connection and a suitable home office setup."
        },
        
        # Policy 2 - Single row
        {
            "Source URL": "https://example.com/policy2",
            "Title": "Travel Expense Policy",
            "Issuer": "Finance Department",
            "Effective Date": datetime.now() - timedelta(days=90),
            "Last Updated": datetime.now() - timedelta(days=90),
            "Procedure": "Submit Expense Report",
            "Applies To": "All Employees",
            "Deadlines": "Within 30 days of travel completion",
            "Fees": None,
            "Contacts": "finance@example.com",
            "Citation": "Travel Policy Section 3",
            "Page": 5,
            "Text": "All travel expenses must be submitted with receipts for reimbursement."
        },
        
        # Policy 3 - Multiple rows, testing different fields
        {
            "Source URL": "https://example.com/policies/confidentiality",
            "Title": "Confidentiality Agreement",
            "Issuer": "Legal Department",
            "Effective Date": datetime.now() - timedelta(days=180),
            "Last Updated": datetime.now() - timedelta(days=45),
            "Procedure": "Report Confidentiality Breach",
            "Applies To": "All Employees",
            "Deadlines": "Immediately upon discovery",
            "Fees": None,
            "Contacts": "legal@example.com",
            "Citation": "Confidentiality Agreement Section 1",
            "Page": 1,
            "Text": "All employees must maintain strict confidentiality of company information."
        },
        {
            "Source URL": "https://example.com/policies/confidentiality",
            "Title": "Confidentiality Agreement",
            "Issuer": "Legal Department",
            "Effective Date": datetime.now() - timedelta(days=180),
            "Last Updated": datetime.now() - timedelta(days=45),
            "Procedure": None,
            "Applies To": None,
            "Deadlines": None,
            "Fees": None,
            "Contacts": None,
            "Citation": "Confidentiality Agreement Section 2",
            "Page": 2,
            "Text": "Violation of this policy may result in termination of employment."
        }
    ]
    
    # Create DataFrame
    df = pd.DataFrame(data)
    
    # Save to Excel
    output_path = "A2G_templates.xlsx"
    with pd.ExcelWriter(output_path) as writer:
        df.to_excel(writer, sheet_name="FAQ_seed", index=False)
    
    print(f"Created sample Excel file: {output_path}")


if __name__ == "__main__":
    create_sample_excel()
