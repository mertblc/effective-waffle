"""
File: utils/field_types.py

Common field type definitions used across the Dune Archive System.
"""

from enum import Enum, auto

class FieldType(Enum):
    """Supported field types for records."""
    INT = auto()  # 8-byte signed integer
    STR = auto()  # Variable-length string (up to max_length bytes) 