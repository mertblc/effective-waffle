"""
File: archive.py

Main entry point for the Dune Archive System.
Handles command-line operations, input processing, and operation dispatching.
"""

import sys
import time
import argparse
from typing import List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum, auto
import traceback
import os

from utils.catalog_utils import (
    initialize_catalog, create_type, load_catalog, get_type_meta,
    TypeDefinition, Field, FieldType, CatalogError
)
from utils.page_utils import (
    write_record, find_record, delete_record, iterate_pages,
    PageError, MAX_SLOTS, HEADER_SIZE, SLOT_SIZE
)
from utils.record_utils import (
    serialize_record, deserialize_record, compare_record_key,
    get_field_offset, RecordError, Field as RecordField, FieldType,
    validate_record_values, check_primary_key_exists, DuplicateKeyError
)

class Operation(Enum):
    """Supported operations."""
    CREATE_TYPE = auto()
    CREATE_RECORD = auto()
    SEARCH_RECORD = auto()
    DELETE_RECORD = auto()

@dataclass
class OperationResult:
    """Result of an operation."""
    success: bool
    message: str
    data: Optional[List[str]] = None

def parse_operation(line: str) -> Tuple[Operation, List[str]]:
    """
    Parse an operation line into operation type and arguments.
    
    Args:
        line: Raw operation line from input file
    
    Returns:
        Tuple of (Operation, arguments)
    
    Raises:
        ValueError: If operation is invalid
    """
    parts = line.strip().split()
    if not parts:
        raise ValueError("Empty operation")
    
    op_str = parts[0].lower()
    args = parts[1:]
    
    if op_str == "create" and len(args) >= 3 and args[0] == "type":
        return Operation.CREATE_TYPE, args
    elif op_str == "create" and len(args) >= 3 and args[0] == "record":
        return Operation.CREATE_RECORD, args
    elif op_str == "search" and len(args) >= 2 and args[0] == "record":
        return Operation.SEARCH_RECORD, args
    elif op_str == "delete" and len(args) >= 2 and args[0] == "record":
        return Operation.DELETE_RECORD, args
    else:
        raise ValueError(f"Invalid operation: {line}")

def log_debug(message: str) -> None:
    """Write debug message to debug.log."""
    with open("debug.log", "a") as f:
        f.write(f"{message}\n")

def handle_create_type(args: List[str]) -> OperationResult:
    """
    Handle create type operation.
    
    Format: create type <type> <num_fields> <pk_index> <field1> <type1> <field2> <type2> ...
    """
    try:
        if len(args) < 4:
            raise ValueError("Insufficient arguments")
        
        type_name = args[1]
        num_fields = int(args[2])
        pk_index = int(args[3])
        
        # Parse field definitions (space-separated pairs)
        field_args = args[4:]
        if len(field_args) != num_fields * 2:
            raise ValueError(f"Expected {num_fields * 2} field arguments, got {len(field_args)}")
        fields = []
        for i in range(0, len(field_args), 2):
            name = field_args[i]
            type_str = field_args[i+1]
            fields.append((name, type_str))
        
        log_debug(f"Creating type: {type_name} with {num_fields} fields, pk_index={pk_index}")
        log_debug(f"Fields: {fields}")
        
        create_type(type_name, num_fields, pk_index, fields)
        return OperationResult(True, f"Created type '{type_name}'")
    
    except (ValueError, CatalogError) as e:
        log_debug(f"Error in create_type: {str(e)}")
        log_debug(traceback.format_exc())
        return OperationResult(False, str(e))

def handle_create_record(args: List[str]) -> OperationResult:
    """
    Handle create record operation.
    
    Format: create record <type> <field1_value> <field2_value> ...
    """
    try:
        if len(args) < 3:
            raise ValueError("Insufficient arguments")
        
        type_name = args[1]
        field_values = args[2:]
        
        # Get type metadata
        type_def = get_type_meta(type_name)
        
        # Convert type definition to RecordField objects, preserving original field lengths
        fields = [
            RecordField(f.name, f.type, f.max_length)  # Use the field's actual max_length
            for f in type_def.fields
        ]
        
        # Validate field values
        validate_record_values(fields, field_values, type_def.pk_index)
        
        # Get primary key field and offset
        pk_field = fields[type_def.pk_index]
        pk_offset = get_field_offset(fields, type_def.pk_index)
        
        # Check for duplicate primary key
        if check_primary_key_exists(type_name, field_values[type_def.pk_index], pk_field, pk_offset):
            raise DuplicateKeyError(f"Record with primary key '{field_values[type_def.pk_index]}' already exists")
        
        # Serialize and write record
        record_data = serialize_record(fields, field_values)
        write_record(type_name, record_data)
        
        return OperationResult(True, f"Created record in type '{type_name}'")
    
    except (ValueError, CatalogError, RecordError, PageError) as e:
        log_debug(f"Error in create_record: {str(e)}")
        log_debug(traceback.format_exc())
        return OperationResult(False, str(e))

def handle_search_record(args: List[str]) -> OperationResult:
    """
    Handle search record operation.
    
    Format: search record <type> <key_value>
    """
    try:
        if len(args) < 3:
            raise ValueError("Insufficient arguments")
        
        type_name = args[1]
        key_value = args[2]
        
        log_debug(f"Searching for record in type '{type_name}' with key '{key_value}'")
        
        # Get type metadata
        type_def = get_type_meta(type_name)
        log_debug(f"Type definition: {type_def}")
        
        # Convert type definition to RecordField objects, preserving original field lengths
        fields = [
            RecordField(f.name, f.type, f.max_length)  # Use the field's actual max_length
            for f in type_def.fields
        ]
        log_debug(f"Fields: {fields}")
        
        # Get key field offset
        key_offset = get_field_offset(fields, type_def.pk_index)
        key_type = fields[type_def.pk_index].type
        log_debug(f"Key field: {fields[type_def.pk_index]}, offset: {key_offset}, type: {key_type}")
        
        # Search all pages
        found_records = []
        for page_num, header, page_data in iterate_pages(type_name):
            log_debug(f"Searching page {page_num}, bitmap: {bin(header.bitmap)}")
            for slot in range(MAX_SLOTS):
                if header.bitmap & (1 << slot):
                    # page_data is already the data portion (after header)
                    # so we just need slot * SLOT_SIZE to get the slot's start
                    slot_start = slot * SLOT_SIZE
                    record_data = page_data[slot_start:slot_start + SLOT_SIZE]
                    
                    log_debug(f"Checking slot {slot}, record data: {record_data[:20]}...")
                    
                    if compare_record_key(record_data, key_value, key_type, key_offset, fields[type_def.pk_index]):
                        log_debug("Found matching record!")
                        values = deserialize_record(fields, record_data)
                        log_debug(f"Deserialized values: {values}")
                        found_records.append(" ".join(str(v) for v in values))
                    else:
                        log_debug("Record did not match")
        
        if found_records:
            log_debug(f"Found {len(found_records)} records: {found_records}")
            return OperationResult(True, f"Found {len(found_records)} records", found_records)
        else:
            log_debug("No matching records found")
            return OperationResult(False, "No matching records found")
    
    except (ValueError, CatalogError, RecordError, PageError) as e:
        log_debug(f"Error in search_record: {str(e)}")
        log_debug(traceback.format_exc())
        return OperationResult(False, str(e))

def handle_delete_record(args: List[str]) -> OperationResult:
    """
    Handle delete record operation.
    
    Format: delete record <type> <key_value>
    """
    try:
        if len(args) < 3:
            raise ValueError("Insufficient arguments")
        
        type_name = args[1]
        key_value = args[2]
        
        # Get type metadata
        type_def = get_type_meta(type_name)
        
        # Convert type definition to RecordField objects, preserving original field lengths
        fields = [
            RecordField(f.name, f.type, f.max_length)  # Use the field's actual max_length
            for f in type_def.fields
        ]
        
        # Get key field offset
        key_offset = get_field_offset(fields, type_def.pk_index)
        key_type = fields[type_def.pk_index].type
        
        # Search and delete record
        deleted = False
        for page_num, header, page_data in iterate_pages(type_name):
            for slot in range(MAX_SLOTS):
                if header.bitmap & (1 << slot):
                    # page_data is already the data portion (after header)
                    # so we just need slot * SLOT_SIZE to get the slot's start
                    slot_start = slot * SLOT_SIZE
                    record_data = page_data[slot_start:slot_start + SLOT_SIZE]
                    
                    if compare_record_key(record_data, key_value, key_type, key_offset, fields[type_def.pk_index]):
                        if delete_record(type_name, page_num, slot):
                            deleted = True
        
        if deleted:
            return OperationResult(True, f"Deleted record from type '{type_name}'")
        else:
            return OperationResult(False, "No matching record found")
    
    except (ValueError, CatalogError, RecordError, PageError) as e:
        log_debug(f"Error in delete_record: {str(e)}")
        log_debug(traceback.format_exc())
        return OperationResult(False, str(e))

def log_operation(operation: str, result: OperationResult) -> None:
    """Log an operation and its result to log.csv."""
    timestamp = int(time.time())
    status = "success" if result.success else "failure"
    with open("log.csv", "a") as f:
        f.write(f"{timestamp},{operation},{status}\n")

def write_output(records: List[str]) -> None:
    """Write search results to output.txt."""
    with open("output.txt", "a") as f:
        for record in records:
            f.write(f"{record}\n")

def process_operation_line(line: str, line_num: int) -> OperationResult:
    """
    Process a single operation line, handling all possible errors.
    
    Args:
        line: The operation line to process
        line_num: Line number for error reporting
    
    Returns:
        OperationResult indicating success/failure
    """
    # Skip empty lines and comments
    line = line.strip()
    if not line or line.startswith('#'):
        return OperationResult(True, "Skipped empty line or comment")
    
    try:
        # Parse operation
        op, op_args = parse_operation(line)
        
        # Handle each operation type
        if op == Operation.CREATE_TYPE:
            result = handle_create_type(op_args)
        elif op == Operation.CREATE_RECORD:
            result = handle_create_record(op_args)
        elif op == Operation.SEARCH_RECORD:
            result = handle_search_record(op_args)
            # Only write record data to output.txt, not operation status
            if result.success and result.data:
                write_output(result.data)
        elif op == Operation.DELETE_RECORD:
            result = handle_delete_record(op_args)
        else:
            return OperationResult(False, f"Unknown operation type: {op}")
        
        # Write operation status to log.csv only
        log_operation(line.strip(), result)
        
        # Write operation status to output.txt only for non-search operations
        # if op != Operation.SEARCH_RECORD:
        #     with open("output.txt", "a") as out:
        #         status = "Success" if result.success else "Failed"
        #         out.write(f"Line {line_num}: {status} - {result.message}\n")
        
        return result
    
    except ValueError as e:
        # Handle parsing and validation errors
        log_debug(f"Validation error on line {line_num}: {str(e)}")
        result = OperationResult(False, f"Invalid operation format: {str(e)}")
        log_operation(line.strip(), result)
        with open("output.txt", "a") as out:
            out.write(f"Line {line_num}: Failed - {result.message}\n")
        return result
    
    except CatalogError as e:
        # Handle catalog-related errors (type not found, etc)
        log_debug(f"Catalog error on line {line_num}: {str(e)}")
        result = OperationResult(False, str(e))
        log_operation(line.strip(), result)
        with open("output.txt", "a") as out:
            out.write(f"Line {line_num}: Failed - {result.message}\n")
        return result
    
    except RecordError as e:
        # Handle record-related errors (data validation, duplicates, etc)
        log_debug(f"Record error on line {line_num}: {str(e)}")
        result = OperationResult(False, str(e))
        log_operation(line.strip(), result)
        with open("output.txt", "a") as out:
            out.write(f"Line {line_num}: Failed - {result.message}\n")
        return result
    
    except PageError as e:
        # Handle page-related errors (I/O, corruption, etc)
        log_debug(f"Page error on line {line_num}: {str(e)}")
        result = OperationResult(False, str(e))
        log_operation(line.strip(), result)
        with open("output.txt", "a") as out:
            out.write(f"Line {line_num}: Failed - {result.message}\n")
        return result
    
    except Exception as e:
        # Handle any unexpected errors
        log_debug(f"Unexpected error on line {line_num}: {str(e)}")
        log_debug(traceback.format_exc())
        result = OperationResult(False, f"Internal error: {str(e)}")
        log_operation(line.strip(), result)
        with open("output.txt", "a") as out:
            out.write(f"Line {line_num}: Critical error - {result.message}\n")
        return result

def main():
    """Main entry point for the Dune Archive System."""
    # Clear debug log and output files
    with open("debug.log", "w") as f:
        f.write("=== Starting Dune Archive System ===\n")
    with open("output.txt", "w") as f:
        pass  # Clear output file
    if not os.path.exists("log.csv"):
        with open("log.csv", "w") as f:
            f.write("timestamp,operation,status\n")
    
    parser = argparse.ArgumentParser(description="Dune Archive System")
    parser.add_argument("input_file", help="Path to input file")
    args = parser.parse_args()
    
    # Validate input file exists
    if not os.path.exists(args.input_file):
        with open("output.txt", "w") as f:
            f.write(f"Error: Input file '{args.input_file}' not found\n")
        sys.exit(1)
    
    log_debug("Initializing catalog...")
    try:
        # Initialize catalog
        initialize_catalog()
        load_catalog()
    except CatalogError as e:
        with open("output.txt", "w") as f:
            f.write(f"Error initializing catalog: {str(e)}\n")
        sys.exit(1)
    
    # Process input file
    try:
        with open(args.input_file, "r") as f:
            for line_num, line in enumerate(f, 1):
                try:
                    # Process the operation line
                    result = process_operation_line(line, line_num)
                except Exception as e:
                    # This should never happen as process_operation_line handles all exceptions
                    # But we keep it as a safety net
                    log_debug(f"Critical error processing line {line_num}: {str(e)}")
                    log_debug(traceback.format_exc())
                    log_operation(line.strip(), OperationResult(False, f"Critical error: {str(e)}"))
                    with open("output.txt", "a") as out:
                        out.write(f"Line {line_num}: Critical error - {str(e)}\n")
    
    except IOError as e:
        with open("output.txt", "w") as f:
            f.write(f"Error reading input file: {str(e)}\n")
        sys.exit(1)
    
    # Write completion message to output.txt
    # with open("output.txt", "a") as f:
    #     f.write("\nProcessing complete. Check debug.log for details.\n")

if __name__ == "__main__":
    main()
