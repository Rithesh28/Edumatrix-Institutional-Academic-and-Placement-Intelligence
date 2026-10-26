"""
File Utilities

Helper functions for file operations:
- File size formatting
- MIME type detection
- File validation
- File name sanitization
- File type detection
"""

import os
import re
import mimetypes
from typing import Optional, Tuple, List, Dict, Any
from datetime import datetime

# Initialize mimetypes
mimetypes.init()


def format_file_size(size_bytes: int) -> str:
    """
    Format file size in human-readable format.
    
    Args:
        size_bytes: File size in bytes
        
    Returns:
        Formatted string (e.g., "2.5 MB")
    """
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    size = float(size_bytes)
    
    while size >= 1024 and i < len(size_names) - 1:
        size /= 1024
        i += 1
    
    return f"{size:.1f} {size_names[i]}"


def get_file_extension(filename: str) -> str:
    """
    Get file extension from filename.
    
    Args:
        filename: Filename
        
    Returns:
        File extension with dot (e.g., ".pdf")
    """
    return os.path.splitext(filename)[1].lower()


def get_mime_type(filename: str) -> str:
    """
    Get MIME type from filename.
    
    Args:
        filename: Filename
        
    Returns:
        MIME type
    """
    mime_type, _ = mimetypes.guess_type(filename)
    return mime_type or "application/octet-stream"


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename by removing unsafe characters.
    
    Args:
        filename: Original filename
        
    Returns:
        Sanitized filename
    """
    # Remove path separators
    filename = filename.replace("/", "_").replace("\\", "_")
    
    # Remove any non-alphanumeric characters except . - _
    filename = re.sub(r'[^\w\-_.]', '_', filename)
    
    # Remove multiple underscores
    filename = re.sub(r'_+', '_', filename)
    
    # Remove leading/trailing underscores
    filename = filename.strip('_')
    
    # Limit length
    if len(filename) > 255:
        name, ext = os.path.splitext(filename)
        filename = name[:250] + ext
    
    return filename


def generate_unique_filename(filename: str) -> str:
    """
    Generate a unique filename using timestamp.
    
    Args:
        filename: Original filename
        
    Returns:
        Unique filename
    """
    name, ext = os.path.splitext(filename)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    unique_name = f"{name}_{timestamp}{ext}"
    return sanitize_filename(unique_name)


def get_file_type_category(filename: str) -> str:
    """
    Get file category based on extension.
    
    Args:
        filename: Filename
        
    Returns:
        File category: image, document, spreadsheet, presentation, archive, other
    """
    ext = get_file_extension(filename)
    
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp', '.svg'}
    document_extensions = {'.pdf', '.doc', '.docx', '.txt', '.rtf', '.odt'}
    spreadsheet_extensions = {'.xls', '.xlsx', '.csv', '.ods'}
    presentation_extensions = {'.ppt', '.pptx', '.odp'}
    archive_extensions = {'.zip', '.rar', '.7z', '.tar', '.gz'}
    
    if ext in image_extensions:
        return "image"
    elif ext in document_extensions:
        return "document"
    elif ext in spreadsheet_extensions:
        return "spreadsheet"
    elif ext in presentation_extensions:
        return "presentation"
    elif ext in archive_extensions:
        return "archive"
    else:
        return "other"


def is_image_file(filename: str) -> bool:
    """Check if file is an image."""
    return get_file_type_category(filename) == "image"


def is_document_file(filename: str) -> bool:
    """Check if file is a document."""
    return get_file_type_category(filename) == "document"


def is_spreadsheet_file(filename: str) -> bool:
    """Check if file is a spreadsheet."""
    return get_file_type_category(filename) == "spreadsheet"


def is_presentation_file(filename: str) -> bool:
    """Check if file is a presentation."""
    return get_file_type_category(filename) == "presentation"


def get_allowed_extensions() -> List[str]:
    """
    Get list of allowed file extensions from settings.
    
    Returns:
        List of allowed extensions
    """
    from ..core.config import settings
    return settings.ALLOWED_EXTENSIONS


def is_file_allowed(filename: str) -> bool:
    """
    Check if file type is allowed.
    
    Args:
        filename: Filename
        
    Returns:
        True if allowed, False otherwise
    """
    ext = get_file_extension(filename)
    return ext in get_allowed_extensions()


def validate_file_size(file_size: int, max_size: Optional[int] = None) -> bool:
    """
    Validate file size.
    
    Args:
        file_size: File size in bytes
        max_size: Maximum allowed size in bytes (uses settings if None)
        
    Returns:
        True if valid, False otherwise
    """
    if max_size is None:
        from ..core.config import settings
        max_size = settings.MAX_FILE_SIZE
    
    return file_size <= max_size


def get_file_info(file_path: str) -> Dict[str, Any]:
    """
    Get file information.
    
    Args:
        file_path: Path to file
        
    Returns:
        Dictionary with file info
    """
    import os
    from datetime import datetime
    
    stat = os.stat(file_path)
    
    return {
        "filename": os.path.basename(file_path),
        "extension": get_file_extension(file_path),
        "size_bytes": stat.st_size,
        "size_formatted": format_file_size(stat.st_size),
        "mime_type": get_mime_type(file_path),
        "category": get_file_type_category(file_path),
        "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
        "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        "is_image": is_image_file(file_path),
        "is_document": is_document_file(file_path),
        "is_allowed": is_file_allowed(file_path)
    }


def extract_text_from_filename(filename: str) -> str:
    """
    Extract meaningful text from filename for search.
    
    Args:
        filename: Filename
        
    Returns:
        Extracted text
    """
    # Remove extension
    name, _ = os.path.splitext(filename)
    
    # Replace common separators with spaces
    name = name.replace('_', ' ').replace('-', ' ').replace('.', ' ')
    
    # Remove extra spaces
    name = ' '.join(name.split())
    
    return name


def get_file_icon(filename: str) -> str:
    """
    Get icon name for file type.
    
    Args:
        filename: Filename
        
    Returns:
        Icon name (for UI)
    """
    category = get_file_type_category(filename)
    
    icons = {
        "image": "Image",
        "document": "FileText",
        "spreadsheet": "Table",
        "presentation": "Presentation",
        "archive": "Archive",
        "other": "File"
    }
    
    return icons.get(category, "File")


def get_file_color(filename: str) -> str:
    """
    Get color for file type.
    
    Args:
        filename: Filename
        
    Returns:
        Color code
    """
    category = get_file_type_category(filename)
    
    colors = {
        "image": "#8B5CF6",      # Purple
        "document": "#3B82F6",   # Blue
        "spreadsheet": "#10B981", # Green
        "presentation": "#F59E0B", # Yellow
        "archive": "#6B7280",     # Gray
        "other": "#9CA3AF"        # Light Gray
    }
    
    return colors.get(category, "#9CA3AF")


def is_previewable(filename: str) -> bool:
    """
    Check if file can be previewed.
    
    Args:
        filename: Filename
        
    Returns:
        True if previewable, False otherwise
    """
    ext = get_file_extension(filename)
    previewable_extensions = {
        '.pdf', '.jpg', '.jpeg', '.png', '.gif', '.svg',
        '.txt', '.csv', '.md'
    }
    return ext in previewable_extensions


def get_preview_type(filename: str) -> str:
    """
    Get preview type for file.
    
    Args:
        filename: Filename
        
    Returns:
        Preview type: image, pdf, text, none
    """
    ext = get_file_extension(filename)
    
    if ext in {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.webp'}:
        return "image"
    elif ext == '.pdf':
        return "pdf"
    elif ext in {'.txt', '.csv', '.md', '.json', '.xml', '.html', '.css', '.js'}:
        return "text"
    else:
        return "none"


# Dictionary of common file types for quick reference
FILE_TYPE_DISPLAY = {
    'exam_duty': 'Exam Duty',
    'assignment': 'Assignment',
    'circular': 'Circular',
    'resume': 'Resume',
    'timetable': 'Timetable',
    'certificate': 'Certificate',
    'placement_doc': 'Placement Document',
    'other': 'Other'
}


def get_file_type_display(file_type: str) -> str:
    """
    Get display name for file type.
    
    Args:
        file_type: Internal file type
        
    Returns:
        Display name
    """
    return FILE_TYPE_DISPLAY.get(file_type, file_type.replace('_', ' ').title())


def get_department_display(department: str) -> str:
    """
    Get display name for department from branch code.

    Args:
        department: Department code (branch code)

    Returns:
        Display name (full department name)
    """
    departments = {
        'AIML': 'Artificial Intelligence and Machine Learning',
        'CD': 'Data Science',
        'CV': 'Civil',
        'CSE': 'Computer Science',
        'EC': 'Electronics and Communication',
        'ME': 'Mechanical',
        'MBA': 'MBA',
        'MCA': 'MCA',
        # Legacy mappings preserved for backward compatibility
        'CS': 'Computer Science',
        'IT': 'Information Technology',
        'EE': 'Electrical Engineering',
        'CE': 'Civil Engineering',
    }
    return departments.get(department.strip().upper(), department.strip())
