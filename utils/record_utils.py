# File: utils/record_utils.py
#
# This module handles record serialization/deserialization for the Dune Archive System. It must:
#
# 1. Define functions to serialize a Python record (list of field values) into bytes:
#    - Pad or truncate string fields to fixed lengths.
#    - Pack integer fields using struct.pack.
#    - Prepend a validity flag (1 byte).
#
# 2. Define functions to deserialize a record byte sequence back into Python values:
#    - Read and interpret the validity flag.
#    - Unpack fixed-length strings (strip padding) and integers.
#
# 3. Provide a function to compare a record's primary key value with a search key.
#
# 4. Calculate the byte offset for a given slot index in a page.
#
# 5. Ensure consistency with page_utils' PAGE_SIZE, MAX_SLOTS, and header format.
#
# Requirements:
# - Use Python's struct module for packing/unpacking.
# - Clear exceptions on format mismatches.
# - Type hints and docstrings for each function.
#
# Deliverable:
# Return a complete Python module implementing these operations with inline comments.

import struct
from typing import List, Tuple, Any, Optional
from dataclasses import dataclass
from enum import Enum, auto

from utils.field_types import FieldType  # Import common FieldType enum
from utils.page_utils import (  # Import constants from page_utils
    PAGE_SIZE, HEADER_SIZE, MAX_SLOTS, SLOT_SIZE
)

@dataclass
class Field:
    """Metadata for a field in a record."""
    name: str
    type: FieldType
    max_length: int  # For strings, maximum length; for ints, always 8

class RecordError(Exception):
    """Base exception for record-related errors."""
    pass

class RecordFormatError(RecordError):
    """Base class for record format/type errors."""
    pass

class RecordDataError(RecordError):
    """Base class for record data/content errors."""
    pass

class FieldTypeError(RecordFormatError):
    """Raised when field type is invalid or type conversion fails."""
    pass

class InvalidRecordError(RecordDataError):
    """Raised when record data is invalid (wrong size, invalid values, etc)."""
    pass

class DuplicateKeyError(RecordDataError):
    """Raised when attempting to insert a record with a duplicate primary key."""
    pass

class FieldConstraintError(RecordDataError):
    """Raised when a field value violates its constraints."""
    pass

def _pack_int(value: int) -> bytes:
    """Pack an integer into 8 bytes."""
    try:
        return struct.pack(">q", value)  # 8-byte signed integer
    except struct.error as e:
        raise FieldTypeError(f"Failed to pack integer: {str(e)}")

def _unpack_int(data: bytes) -> int:
    """Unpack 8 bytes into an integer."""
    try:
        return struct.unpack(">q", data)[0]
    except struct.error as e:
        raise FieldTypeError(f"Failed to unpack integer: {str(e)}")

def _pack_str(value: str, max_length: int) -> bytes:
    """Pack a string into fixed-length bytes."""
    if not isinstance(value, str):
        raise FieldTypeError("Expected string value")
    
    # Convert to bytes and truncate/pad
    value_bytes = value.encode('utf-8')
    if len(value_bytes) > max_length:
        value_bytes = value_bytes[:max_length]
    elif len(value_bytes) < max_length:
        value_bytes = value_bytes + b'\0' * (max_length - len(value_bytes))
    
    return value_bytes

def _unpack_str(data: bytes) -> str:
    """Unpack bytes into a string, removing padding."""
    try:
        # Remove null padding and decode
        return data.rstrip(b'\0').decode('utf-8')
    except UnicodeDecodeError as e:
        raise FieldTypeError(f"Failed to unpack string: {str(e)}")

def serialize_record(fields: List[Field], values: List[Any]) -> bytes:
    """
    Serialize a record into bytes.
    
    Args:
        fields: List of Field objects defining the record structure
        values: List of field values to serialize
    
    Returns:
        Bytes containing the serialized record
    
    Raises:
        RecordError: If serialization fails
    """
    if len(fields) != len(values):
        raise InvalidRecordError("Field count mismatch")
    
    # Start with validity flag (1 byte)
    record_data = bytearray([1])  # 1 = valid record
    
    # Serialize each field
    for field, value in zip(fields, values):
        try:
            if field.type == FieldType.INT:
                record_data.extend(_pack_int(int(value)))
            elif field.type == FieldType.STR:
                record_data.extend(_pack_str(str(value), field.max_length))
            else:
                raise FieldTypeError(f"Unsupported field type: {field.type}")
        except (ValueError, TypeError) as e:
            raise InvalidRecordError(f"Invalid value for field '{field.name}': {str(e)}")
    
    # Check if record fits in slot
    if len(record_data) > SLOT_SIZE:
        raise InvalidRecordError("Record too large for slot")
    
    # Pad to slot size
    record_data.extend(b'\0' * (SLOT_SIZE - len(record_data)))
    return bytes(record_data)

def deserialize_record(fields: List[Field], data: bytes) -> List[Any]:
    """
    Deserialize a record from bytes.
    
    Args:
        fields: List of Field objects defining the record structure
        data: Bytes containing the serialized record
    
    Returns:
        List of deserialized field values
    
    Raises:
        RecordError: If deserialization fails
    """
    if len(data) != SLOT_SIZE:
        raise InvalidRecordError("Invalid record size")
    
    # Check validity flag
    if data[0] != 1:
        raise InvalidRecordError("Invalid record")
    
    values = []
    offset = 1  # Skip validity flag
    
    for field in fields:
        try:
            if field.type == FieldType.INT:
                value = _unpack_int(data[offset:offset + 8])
                offset += 8
            elif field.type == FieldType.STR:
                value = _unpack_str(data[offset:offset + field.max_length])
                offset += field.max_length
            else:
                raise FieldTypeError(f"Unsupported field type: {field.type}")
            values.append(value)
        except (struct.error, UnicodeDecodeError) as e:
            raise InvalidRecordError(f"Failed to deserialize field '{field.name}': {str(e)}")
    
    return values

def compare_record_key(record_data: bytes, key_value: Any, key_type: FieldType, key_offset: int, key_field: Field) -> bool:
    """
    Compare a record's key field with a search key.
    
    Args:
        record_data: Serialized record data
        key_value: Value to compare against
        key_type: Type of the key field
        key_offset: Byte offset of the key field in the record
        key_field: Field metadata for the key field (needed for string length)
    
    Returns:
        True if the record's key matches the search key
    
    Raises:
        RecordError: If comparison fails
    """
    from archive import log_debug  # Import log_debug from archive
    
    if record_data[0] != 1:  # Check validity flag
        log_debug("Record is invalid (validity flag is not 1)")
        return False
    
    try:
        if key_type == FieldType.INT:
            record_key = _unpack_int(record_data[key_offset:key_offset + 8])
            log_debug(f"Comparing INT keys: record_key={record_key}, search_key={key_value}")
            return record_key == int(key_value)
        elif key_type == FieldType.STR:
            record_key = _unpack_str(record_data[key_offset:key_offset + key_field.max_length])
            log_debug(f"Comparing STR keys: record_key='{record_key}', search_key='{key_value}'")
            return record_key == str(key_value)
        else:
            raise FieldTypeError(f"Unsupported key type: {key_type}")
    except (ValueError, TypeError) as e:
        log_debug(f"Invalid key value: {str(e)}")
        raise RecordDataError(f"Invalid key value: {str(e)}")
    except (struct.error, UnicodeDecodeError) as e:
        log_debug(f"Failed to compare record key: {str(e)}")
        raise RecordFormatError(f"Failed to compare record key: {str(e)}")

def get_field_offset(fields: List[Field], field_index: int) -> int:
    """
    Calculate the byte offset of a field in a serialized record.
    
    Args:
        fields: List of Field objects defining the record structure
        field_index: Index of the field to calculate offset for
    
    Returns:
        Byte offset of the field in the serialized record
    
    Raises:
        RecordError: If field index is invalid
    """
    if not 0 <= field_index < len(fields):
        raise RecordError(f"Invalid field index: {field_index}")
    
    # Start after validity flag
    offset = 1
    
    # Add sizes of all fields before the target field
    for i in range(field_index):
        if fields[i].type == FieldType.INT:
            offset += 8
        elif fields[i].type == FieldType.STR:
            offset += fields[i].max_length
    
    return offset

def validate_record_values(fields: List[Field], values: List[Any], pk_index: int) -> None:
    """
    Validate record values before insertion.
    
    Args:
        fields: List of Field objects defining the record structure
        values: List of field values to validate
        pk_index: Index of the primary key field
    
    Raises:
        RecordDataError: If validation fails
        FieldConstraintError: If field constraints are violated
    """
    if len(fields) != len(values):
        raise InvalidRecordError("Field count mismatch")
    
    # Validate each field
    for i, (field, value) in enumerate(zip(fields, values)):
        try:
            if field.type == FieldType.INT:
                # Validate integer
                int_val = int(value)
                if int_val < -2**63 or int_val > 2**63 - 1:  # 8-byte signed int range
                    raise FieldConstraintError(f"Integer value out of range for field '{field.name}'")
            elif field.type == FieldType.STR:
                # Validate string
                str_val = str(value)
                if len(str_val.encode('utf-8')) > field.max_length:
                    raise FieldConstraintError(
                        f"String value too long for field '{field.name}' (max {field.max_length} bytes)"
                    )
            else:
                raise FieldTypeError(f"Unsupported field type: {field.type}")
        except ValueError as e:
            raise FieldConstraintError(f"Invalid value for field '{field.name}': {str(e)}")

def check_primary_key_exists(type_name: str, pk_value: Any, pk_field: Field, pk_offset: int) -> bool:
    """
    Check if a primary key value already exists in the database.
    
    Args:
        type_name: Name of the type
        pk_value: Primary key value to check
        pk_field: Field metadata for the primary key
        pk_offset: Byte offset of the primary key in the record
    
    Returns:
        True if the primary key exists, False otherwise
    
    Raises:
        RecordError: If check fails
    """
    from utils.page_utils import iterate_pages
    
    for _, header, page_data in iterate_pages(type_name):
        for slot in range(MAX_SLOTS):
            if header.bitmap & (1 << slot):
                # page_data is already the data portion (after header)
                # so we just need slot * SLOT_SIZE to get the slot's start
                slot_start = slot * SLOT_SIZE
                record_data = page_data[slot_start:slot_start + SLOT_SIZE]
                
                if compare_record_key(record_data, pk_value, pk_field.type, pk_offset, pk_field):
                    return True
    return False
