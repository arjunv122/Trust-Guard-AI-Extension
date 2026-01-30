from typing import Optional
import re


def validate_analysis_request(
    content_type: str,
    text: Optional[str] = None,
    url: Optional[str] = None,
    page_data: Optional[dict] = None
) -> None:
    """Validate analysis request, raises ValueError if invalid"""
    
    valid_types = ['text', 'url', 'page']
    if content_type not in valid_types:
        raise ValueError(f"Invalid content_type. Must be: {', '.join(valid_types)}")
    
    if content_type == 'text':
        if not text or len(text.strip()) < 10:
            raise ValueError("Text must be at least 10 characters")
    
    elif content_type == 'url':
        if not url:
            raise ValueError("URL is required")
        if not re.match(r'^https?://', url):
            raise ValueError("Invalid URL format")
    
    elif content_type == 'page':
        if not page_data:
            raise ValueError("Page data is required")
        if not isinstance(page_data, dict):
            raise ValueError("Page data must be a dictionary")