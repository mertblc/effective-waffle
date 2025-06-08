"""
File: utils/catalog_utils.py

This module handles the metadata catalog for the Dune Archive System.
It provides functions to manage type definitions and their metadata.

Note: The primary key index (pk_index) is specified in 1-based indexing (1 to num_fields)
      but is stored internally as 0-based (0 to num_fields-1).
"""

import os
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum, auto

from utils.field_types import FieldType  # Import common FieldType enum

@dataclass
class Field:
    """Represents a field in a type definition."""
    name: str
    type: FieldType
    max_length: int

@dataclass
class TypeDefinition:
    """Represents a complete type definition."""
    name: str
    num_fields: int
    pk_index: int
    fields: List[Field]

class CatalogError(Exception):
    """Base exception for catalog-related errors."""
    pass

class DuplicateTypeError(CatalogError):
    """Raised when attempting to create a type that already exists."""
    pass

class TypeNotFoundError(CatalogError):
    """Raised when attempting to access a type that doesn't exist."""
    pass

class InvalidTypeDefinitionError(CatalogError):
    """Raised when a type definition is invalid."""
    pass

# Global catalog storage
_catalog: Dict[str, TypeDefinition] = {}

def _parse_field_type(type_str: str) -> FieldType:
    """Parse a field type string into a FieldType enum."""
    type_str = type_str.lower().strip()
    if type_str == "int":
        return FieldType.INT
    elif type_str == "str":
        return FieldType.STR
    raise InvalidTypeDefinitionError(f"Unsupported field type: {type_str}")

def _parse_type_definition(line: str) -> TypeDefinition:
    """Parse a type definition line from catalog.txt."""
    try:
        # Format: <type>|<num_fields>|<pk_index>|<field1>:<type1>,<field2>:<type2>,...
        # Note: pk_index in file is 1-based
        parts = line.strip().split("|")
        if len(parts) != 4:
            raise InvalidTypeDefinitionError("Invalid type definition format")
        
        type_name, num_fields_str, pk_index_str, fields_str = parts
        
        try:
            num_fields = int(num_fields_str)
            pk_index = int(pk_index_str)  # This is 1-based from the file
        except ValueError:
            raise InvalidTypeDefinitionError("Invalid number format in type definition")
        
        if pk_index < 1 or pk_index > num_fields:
            raise InvalidTypeDefinitionError("Primary key index must be between 1 and num_fields")
        
        # Convert to 0-based for internal storage
        pk_index_0based = pk_index - 1
        
        # Parse fields
        fields = []
        field_parts = fields_str.split(",")
        if len(field_parts) != num_fields:
            raise InvalidTypeDefinitionError("Field count mismatch")
        
        for field_part in field_parts:
            name, type_str = field_part.split(":")
            field_type = _parse_field_type(type_str)
            # Set max_length: 8 bytes for INT, 32 bytes for STR
            max_length = 8 if field_type == FieldType.INT else 32
            fields.append(Field(name.strip(), field_type, max_length))
        
        return TypeDefinition(type_name, num_fields, pk_index_0based, fields)  # Store 0-based
    
    except Exception as e:
        raise InvalidTypeDefinitionError(f"Failed to parse type definition: {str(e)}")

def initialize_catalog() -> None:
    """Initialize the catalog file if it doesn't exist."""
    if not os.path.exists("catalog.txt"):
        with open("catalog.txt", "w") as f:
            pass  # Create empty file

def create_type(type_name: str, num_fields: int, pk_index: int, fields: List[Tuple[str, str]]) -> None:
    """
    Add a new type definition to the catalog.
    
    Args:
        type_name: Name of the type
        num_fields: Number of fields in the type
        pk_index: Index of the primary key field (1-based, 1 to num_fields)
        fields: List of (field_name, field_type) tuples
    
    Raises:
        DuplicateTypeError: If type already exists
        InvalidTypeDefinitionError: If type definition is invalid
    """
    if type_name in _catalog:
        raise DuplicateTypeError(f"Type '{type_name}' already exists")
    
    if len(fields) != num_fields:
        raise InvalidTypeDefinitionError("Field count mismatch")
    
    # Convert 1-based pk_index to 0-based
    pk_index_0based = pk_index - 1
    if pk_index < 1 or pk_index > num_fields:
        raise InvalidTypeDefinitionError("Primary key index must be between 1 and num_fields")
    
    # Create fields with appropriate max_length
    field_objects = []
    for name, type_str in fields:
        field_type = _parse_field_type(type_str)
        # Set max_length: 8 bytes for INT, 32 bytes for STR (configurable)
        max_length = 8 if field_type == FieldType.INT else 32
        field_objects.append(Field(name, field_type, max_length))
    
    # Create type definition with 0-based pk_index
    type_def = TypeDefinition(
        name=type_name,
        num_fields=num_fields,
        pk_index=pk_index_0based,  # Store as 0-based
        fields=field_objects
    )
    
    # Write to catalog file (store as 1-based for user interface)
    with open("catalog.txt", "a") as f:
        fields_str = ",".join(f"{f.name}:{f.type.name.lower()}" for f in type_def.fields)
        f.write(f"{type_name}|{num_fields}|{pk_index}|{fields_str}\n")  # Write 1-based pk_index
    
    # Update in-memory catalog
    _catalog[type_name] = type_def

def load_catalog() -> None:
    """
    Load all type definitions from catalog.txt into memory.
    
    Raises:
        CatalogError: If catalog file is invalid or cannot be read
    """
    _catalog.clear()
    
    if not os.path.exists("catalog.txt"):
        return
    
    try:
        with open("catalog.txt", "r") as f:
            for line in f:
                if line.strip():  # Skip empty lines
                    type_def = _parse_type_definition(line)
                    _catalog[type_def.name] = type_def
    except Exception as e:
        raise CatalogError(f"Failed to load catalog: {str(e)}")

def type_exists(type_name: str) -> bool:
    """Check if a type exists in the catalog."""
    return type_name in _catalog

def get_type_meta(type_name: str) -> TypeDefinition:
    """
    Get metadata for a given type.
    
    Args:
        type_name: Name of the type to retrieve
    
    Returns:
        TypeDefinition object containing type metadata
    
    Raises:
        TypeNotFoundError: If type doesn't exist
    """
    if not type_exists(type_name):
        raise TypeNotFoundError(f"Type '{type_name}' not found")
    return _catalog[type_name]