"""Utility functions for the bot."""

import logging
from typing import Optional, Any
from datetime import datetime, timedelta
import re

logger = logging.getLogger(__name__)


def format_uptime(seconds: float) -> str:
    """Format uptime in seconds to human-readable string.
    
    Args:
        seconds: Uptime in seconds
        
    Returns:
        Formatted string like "2d 3h 15m"
    """
    if seconds < 0:
        return "0s"
    
    days = int(seconds // 86400)
    hours = int((seconds % 86400) // 3600)
    minutes = int((seconds % 3600) // 60)
    seconds = int(seconds % 60)
    
    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if seconds > 0 and len(parts) < 2:
        parts.append(f"{seconds}s")
    
    return " ".join(parts) if parts else "0s"


def format_bytes(bytes_count: int) -> str:
    """Format bytes to human-readable string.
    
    Args:
        bytes_count: Number of bytes
        
    Returns:
        Formatted string like "1.5 MB"
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_count < 1024.0:
            return f"{bytes_count:.2f} {unit}"
        bytes_count /= 1024.0
    return f"{bytes_count:.2f} PB"


def sanitize_filename(filename: str) -> str:
    """Sanitize a filename by removing invalid characters.
    
    Args:
        filename: Original filename
        
    Returns:
        Sanitized filename safe for filesystem
    """
    # Remove invalid characters
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # Remove leading/trailing dots and spaces
    filename = filename.strip('. ')
    # Limit length
    if len(filename) > 255:
        filename = filename[:255]
    return filename or "unnamed"


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """Truncate text to maximum length.
    
    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add if truncated
        
    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def parse_duration(duration_str: str) -> Optional[timedelta]:
    """Parse a duration string to timedelta.
    
    Supports formats like:
    - "5m" (5 minutes)
    - "2h" (2 hours)
    - "3d" (3 days)
    - "1h 30m" (1 hour 30 minutes)
    
    Args:
        duration_str: Duration string
        
    Returns:
        Timedelta object or None if invalid
    """
    duration_str = duration_str.strip().lower()
    if not duration_str:
        return None
    
    total_seconds = 0
    
    # Match patterns like "5m", "2h", "3d", "1h 30m"
    pattern = r'(\d+)\s*([smhd])'
    matches = re.findall(pattern, duration_str)
    
    if not matches:
        return None
    
    for value, unit in matches:
        value = int(value)
        if unit == 's':
            total_seconds += value
        elif unit == 'm':
            total_seconds += value * 60
        elif unit == 'h':
            total_seconds += value * 3600
        elif unit == 'd':
            total_seconds += value * 86400
    
    return timedelta(seconds=total_seconds)


def format_duration(delta: timedelta) -> str:
    """Format timedelta to human-readable string.
    
    Args:
        delta: Timedelta object
        
    Returns:
        Formatted string like "2h 30m"
    """
    total_seconds = int(delta.total_seconds())
    return format_uptime(total_seconds)


def safe_int(value: Any, default: int = 0) -> int:
    """Safely convert value to integer.
    
    Args:
        value: Value to convert
        default: Default value if conversion fails
        
    Returns:
        Integer value or default
    """
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def safe_float(value: Any, default: float = 0.0) -> float:
    """Safely convert value to float.
    
    Args:
        value: Value to convert
        default: Default value if conversion fails
        
    Returns:
        Float value or default
    """
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def validate_url(url: str) -> bool:
    """Validate if a string is a valid URL.
    
    Args:
        url: URL string to validate
        
    Returns:
        True if valid URL, False otherwise
    """
    pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    return pattern.match(url) is not None


def escape_markdown(text: str) -> str:
    """Escape Discord markdown characters.
    
    Args:
        text: Text to escape
        
    Returns:
        Escaped text
    """
    # Escape Discord markdown characters
    chars = ['*', '_', '~', '`', '|', '>', '#']
    for char in chars:
        text = text.replace(char, f'\\{char}')
    return text


def chunk_text(text: str, max_length: int = 2000, separator: str = "\n") -> list[str]:
    """Split text into chunks that don't exceed max_length.
    
    Args:
        text: Text to chunk
        max_length: Maximum length per chunk
        separator: Separator to use when splitting
        
    Returns:
        List of text chunks
    """
    if len(text) <= max_length:
        return [text]
    
    chunks = []
    lines = text.split(separator)
    current_chunk = ""
    
    for line in lines:
        if len(current_chunk) + len(line) + len(separator) <= max_length:
            if current_chunk:
                current_chunk += separator + line
            else:
                current_chunk = line
        else:
            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = line
    
    if current_chunk:
        chunks.append(current_chunk)
    
    return chunks

