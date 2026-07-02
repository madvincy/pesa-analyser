"""Validation Utilities"""

import re
from typing import Optional

def validate_email(email: str) -> bool:
    """Validate email address format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def validate_phone(phone: str) -> bool:
    """Validate phone number format (Kenya)"""
    # Remove spaces and special characters
    phone = re.sub(r'[\s\-\(\)]', '', phone)
    
    # Check Kenyan phone number patterns
    patterns = [
        r'^07\d{8}$',      # 0712345678
        r'^01\d{8}$',      # 0112345678
        r'^2547\d{8}$',    # 254712345678
        r'^2541\d{8}$',    # 254112345678
        r'^\+2547\d{8}$',  # +254712345678
        r'^\+2541\d{8}$'   # +254112345678
    ]
    
    return any(re.match(pattern, phone) for pattern in patterns)

def validate_amount(amount: float) -> bool:
    """Validate amount is positive and within reasonable range"""
    try:
        amount = float(amount)
        return amount > 0 and amount <= 10000000  # Max 10M KES
    except (ValueError, TypeError):
        return False

def validate_password(password: str) -> tuple:
    """Validate password strength"""
    errors = []
    
    if len(password) < 8:
        errors.append("Password must be at least 8 characters long")
    
    if not re.search(r'[A-Z]', password):
        errors.append("Password must contain at least one uppercase letter")
    
    if not re.search(r'[a-z]', password):
        errors.append("Password must contain at least one lowercase letter")
    
    if not re.search(r'\d', password):
        errors.append("Password must contain at least one number")
    
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        errors.append("Password must contain at least one special character")
    
    return len(errors) == 0, errors

def validate_file_type(filename: str) -> bool:
    """Validate file type is allowed"""
    allowed_extensions = ['.pdf', '.csv', '.xls', '.xlsx']
    ext = re.search(r'\.[^.]+$', filename)
    if not ext:
        return False
    return ext.group().lower() in allowed_extensions

def validate_date(date_str: str) -> bool:
    """Validate date format"""
    patterns = [
        r'^\d{2}/\d{2}/\d{4}$',  # DD/MM/YYYY
        r'^\d{4}-\d{2}-\d{2}$',  # YYYY-MM-DD
        r'^\d{2}-\d{2}-\d{4}$',  # DD-MM-YYYY
    ]
    return any(re.match(pattern, date_str) for pattern in patterns)

def validate_transaction_reference(ref: str) -> bool:
    """Validate transaction reference"""
    # M-PESA references are alphanumeric
    return bool(re.match(r'^[A-Z0-9]{6,15}$', ref.upper()))

def sanitize_description(desc: str) -> str:
    """Sanitize transaction description"""
    # Remove special characters and extra spaces
    desc = re.sub(r'[^a-zA-Z0-9\s]', '', desc)
    desc = re.sub(r'\s+', ' ', desc)
    return desc.strip()

def validate_phone_number(phone: str) -> str:
    """Format phone number to standard format"""
    # Remove spaces and special characters
    phone = re.sub(r'[\s\-\(\)]', '', phone)
    
    # Convert to 254 format
    if phone.startswith('0'):
        phone = '254' + phone[1:]
    elif phone.startswith('+254'):
        phone = phone[1:]
    elif not phone.startswith('254'):
        phone = '254' + phone
    
    return phone
