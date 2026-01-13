#!/usr/bin/env python3
"""
Setup script for PDF generation system
"""
import os
import sys
from pathlib import Path

def setup_directories():
    """Create necessary directories"""
    directories = [
        "templates/pdf",
        "static/pdfs/terms",
        "static/pdfs/applications",
        "templates/email"
    ]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        print(f"Created directory: {directory}")
    
    return True

def create_templates():
    """Create basic template files if they don't exist"""
    templates = {
        "templates/pdf/terms_conditions.html": """<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: Arial, sans-serif; }
        .header { text-align: center; }
        .content { margin: 20px; }
        .footer { margin-top: 50px; text-align: center; font-size: 10px; }
    </style>
</head>
<body>
    <div class="header">
        <h1>MARSHAL CORE NIGERIA LIMITED</h1>
        <h2>Terms & Conditions</h2>
    </div>
    <div class="content">
        <p><strong>Officer:</strong> {{ officer_full_name }}</p>
        <p><strong>Officer ID:</strong> {{ officer_id }}</p>
        <p><strong>Date:</strong> {{ agreement_date }}</p>
        <h3>Terms of Service Agreement</h3>
        <p>This document outlines the terms and conditions of employment...</p>
    </div>
    <div class="footer">
        <p>Generated: {{ generation_date }}</p>
    </div>
</body>
</html>""",
        
        "templates/pdf/application_form.html": """<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: Arial, sans-serif; }
        .header { text-align: center; }
        .section { margin: 20px 0; }
        .label { font-weight: bold; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Marshal Core Nigeria Application Form</h1>
    </div>
    <div class="section">
        <p><span class="label">Name:</span> {{ full_name }}</p>
        <p><span class="label">Email:</span> {{ email }}</p>
        <p><span class="label">Phone:</span> {{ phone_number }}</p>
        <p><span class="label">NIN:</span> {{ nin_number }}</p>
    </div>
    <div class="footer">
        <p>Generated: {{ generation_date }}</p>
    </div>
</body>
</html>"""
    }
    
    for filepath, content in templates.items():
        if not Path(filepath).exists():
            Path(filepath).write_text(content)
            print(f"Created template: {filepath}")
    
    return True

def check_dependencies():
    """Check if required packages are installed"""
    try:
        import weasyprint
        import jinja2
        print("✓ WeasyPrint and Jinja2 are installed")
        return True
    except ImportError as e:
        print(f"✗ Missing dependency: {e}")
        print("Install with: pip install weasyprint jinja2")
        return False

if __name__ == "__main__":
    print("Setting up PDF generation system...")
    
    if not check_dependencies():
        sys.exit(1)
    
    if setup_directories() and create_templates():
        print("\n✅ PDF system setup complete!")
        print("\nNext steps:")
        print("1. Run the migration to add PDF columns:")
        print("   alembic upgrade head")
        print("2. Start the server:")
        print("   python -m uvicorn app.main:app --reload")
        print("3. Test the system by submitting a form")
    else:
        print("\n✗ Setup failed")
        sys.exit(1)