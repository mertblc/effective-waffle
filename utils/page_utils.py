import os
import struct
from typing import List, Tuple, Optional, BinaryIO
from dataclasses import dataclass

# Constants
MAX_SLOTS = 10     # Maximum number of records per page (per spec)
SLOT_SIZE = 128    # Maximum size of a record in bytes
HEADER_SIZE = 10   # 4 bytes page_num + 4 bytes record_count + 2 bytes bitmap
PAGE_SIZE = HEADER_SIZE + (MAX_SLOTS * SLOT_SIZE)  # Total page size

@dataclass
class PageHeader:
    """Represents a page header with metadata."""
    page_num: int
    record_count: int
    bitmap: int  # Bitmap for slot usage (1 = used, 0 = free)

class PageError(Exception):
    """Base exception for page-related errors."""
    pass

class PageNotFoundError(PageError):
    """Raised when attempting to access a non-existent page."""
    pass

class PageFullError(PageError):
    """Raised when attempting to write to a full page."""
    pass

class InvalidPageNumberError(PageError):
    """Raised when page number is invalid."""
    pass

class InvalidSlotError(PageError):
    """Raised when slot number is invalid."""
    pass

def _get_page_file_path(type_name: str) -> str:
    """Get the path to the binary file for a type."""
    # Create pages directory if it doesn't exist
    pages_dir = "pages"
    if not os.path.exists(pages_dir):
        os.makedirs(pages_dir)
    return os.path.join(pages_dir, f"{type_name}.bin")

def _ensure_page_file_exists(type_name: str) -> None:
    """Ensure that the page file exists and is initialized with proper structure."""
    file_path = _get_page_file_path(type_name)
    if not os.path.exists(file_path):
        # Create new file with empty first page
        header = PageHeader(0, 0, 0)  # page_num=0, record_count=0, bitmap=0
        empty_data = bytes(PAGE_SIZE - HEADER_SIZE)
        with open(file_path, "wb") as f:
            header_bytes = struct.pack(">IIH", header.page_num, header.record_count, header.bitmap)
            f.write(header_bytes + empty_data)

def _read_page_header(file: BinaryIO, page_num: int) -> PageHeader:
    """Read a page header from the file."""
    try:
        file.seek(page_num * PAGE_SIZE)
        header_bytes = file.read(HEADER_SIZE)
        if len(header_bytes) < HEADER_SIZE:
            raise PageNotFoundError(f"Page {page_num} not found")
        
        page_num, record_count, bitmap = struct.unpack(">IIH", header_bytes)
        return PageHeader(page_num, record_count, bitmap)
    except struct.error as e:
        raise PageError(f"Failed to read page header: {str(e)}")

def _write_page_header(file: BinaryIO, header: PageHeader) -> None:
    """Write a page header to the file."""
    try:
        file.seek(header.page_num * PAGE_SIZE)
        header_bytes = struct.pack(">IIH", header.page_num, header.record_count, header.bitmap)
        file.write(header_bytes)
    except struct.error as e:
        raise PageError(f"Failed to write page header: {str(e)}")

def _get_slot_offset(slot_num: int) -> int:
    """Calculate the byte offset for a slot in a page."""
    if not 0 <= slot_num < MAX_SLOTS:
        raise InvalidSlotError(f"Invalid slot number: {slot_num}")
    return HEADER_SIZE + (slot_num * SLOT_SIZE)

def _find_free_slot(bitmap: int) -> Optional[int]:
    """Find the first free slot in a page using the bitmap."""
    for slot in range(MAX_SLOTS):
        if not (bitmap & (1 << slot)):
            return slot
    return None

def read_page(type_name: str, page_num: int) -> Tuple[PageHeader, bytes]:
    """
    Read a page from the binary file.
    
    Args:
        type_name: Name of the type
        page_num: Page number to read
    
    Returns:
        Tuple of (PageHeader, page_data)
    
    Raises:
        PageNotFoundError: If page doesn't exist
        PageError: For other page-related errors
    """
    if page_num < 0:
        raise InvalidPageNumberError(f"Invalid page number: {page_num}")
    
    # Ensure file exists before reading
    _ensure_page_file_exists(type_name)
    
    file_path = _get_page_file_path(type_name)
    try:
        with open(file_path, "rb") as f:
            header = _read_page_header(f, page_num)
            f.seek(page_num * PAGE_SIZE + HEADER_SIZE)
            data = f.read(PAGE_SIZE - HEADER_SIZE)
            return header, data
    except IOError as e:
        raise PageError(f"Failed to read page: {str(e)}")

def write_page(type_name: str, page_num: int, header: PageHeader, data: bytes) -> None:
    """
    Write a page to the binary file.
    
    Args:
        type_name: Name of the type
        page_num: Page number to write
        header: Page header
        data: Page data (excluding header)
    
    Raises:
        PageError: For page-related errors
    """
    if page_num < 0:
        raise InvalidPageNumberError(f"Invalid page number: {page_num}")
    
    if len(data) > PAGE_SIZE - HEADER_SIZE:
        raise PageError("Page data too large")
    
    # Ensure file exists before writing
    _ensure_page_file_exists(type_name)
    
    file_path = _get_page_file_path(type_name)
    try:
        with open(file_path, "r+b") as f:
            _write_page_header(f, header)
            f.seek(page_num * PAGE_SIZE + HEADER_SIZE)
            f.write(data)
    except IOError as e:
        raise PageError(f"Failed to write page: {str(e)}")

def allocate_page(type_name: str) -> int:
    """
    Allocate a new page for a type.
    
    Args:
        type_name: Name of the type
    
    Returns:
        Page number of the new page
    
    Raises:
        PageError: For page-related errors
    """
    file_path = _get_page_file_path(type_name)
    exists = os.path.exists(file_path)
    
    # Calculate new page number
    new_page_num = 0 if not exists else os.path.getsize(file_path) // PAGE_SIZE
    
    # Create new page with empty header and data
    header = PageHeader(new_page_num, 0, 0)
    empty_data = bytes(PAGE_SIZE - HEADER_SIZE)
    header_bytes = struct.pack(">IIH", header.page_num, header.record_count, header.bitmap)
    
    try:
        # Write header and data in one operation
        with open(file_path, "r+b" if exists else "wb") as f:
            f.seek(new_page_num * PAGE_SIZE)
            f.write(header_bytes + empty_data)
        return new_page_num
    except IOError as e:
        raise PageError(f"Failed to allocate page: {str(e)}")

def write_record(type_name: str, record_data: bytes) -> Tuple[int, int]:
    """
    Write a record to the first available slot in any page.
    
    Args:
        type_name: Name of the type
        record_data: Serialized record data
    
    Returns:
        Tuple of (page_num, slot_num) where the record was written
    
    Raises:
        PageError: For page-related errors
    """
    if len(record_data) > SLOT_SIZE:
        raise PageError("Record too large")
    
    # Ensure file exists before writing
    _ensure_page_file_exists(type_name)
    
    file_path = _get_page_file_path(type_name)
    # Try to find a free slot in existing pages
    page_num = 0
    while True:
        try:
            header, page_data = read_page(type_name, page_num)
            slot_num = _find_free_slot(header.bitmap)
            if slot_num is not None:
                break
            page_num += 1
        except PageNotFoundError:
            # No free slots found, allocate new page
            page_num = allocate_page(type_name)
            header = PageHeader(page_num, 0, 0)
            slot_num = 0
            break
    
    # Write record to slot
    # page_data is already the data portion (after header)
    # so we just need slot * SLOT_SIZE to get the slot's start
    slot_start = slot_num * SLOT_SIZE
    page_data = bytearray(page_data)  # Convert to mutable
    
    # Ensure the record data starts with validity flag (1)
    if record_data[0] != 1:
        record_data = bytearray(record_data)
        record_data[0] = 1
        record_data = bytes(record_data)
    
    # Write the record data to the slot
    page_data[slot_start:slot_start + len(record_data)] = record_data
    
    # Update header
    header.record_count += 1
    header.bitmap |= (1 << slot_num)
    
    write_page(type_name, page_num, header, bytes(page_data))
    return page_num, slot_num

def find_record(type_name: str, page_num: int, slot_num: int) -> Optional[bytes]:
    """
    Find a record in a specific page and slot.
    
    Args:
        type_name: Name of the type
        page_num: Page number
        slot_num: Slot number
    
    Returns:
        Record data if found and valid, None otherwise
    
    Raises:
        PageError: For page-related errors
    """
    try:
        header, page_data = read_page(type_name, page_num)
        if not (header.bitmap & (1 << slot_num)):
            return None
        
        slot_offset = _get_slot_offset(slot_num)
        record_data = page_data[slot_offset - HEADER_SIZE:slot_offset - HEADER_SIZE + SLOT_SIZE]
        
        # Check if record is valid (first byte is 1)
        if record_data[0] != 1:
            return None
        
        return record_data
    except (PageNotFoundError, InvalidSlotError):
        return None

def delete_record(type_name: str, page_num: int, slot_num: int) -> bool:
    """
    Delete a record from a specific page and slot.
    
    Args:
        type_name: Name of the type
        page_num: Page number
        slot_num: Slot number
    
    Returns:
        True if record was deleted, False if not found
    
    Raises:
        PageError: For page-related errors
    """
    try:
        header, page_data = read_page(type_name, page_num)
        if not (header.bitmap & (1 << slot_num)):
            return False
        
        # Mark record as invalid (set first byte to 0)
        slot_offset = _get_slot_offset(slot_num)
        page_data = bytearray(page_data)
        page_data[slot_offset - HEADER_SIZE] = 0
        
        # Update header
        header.record_count -= 1
        header.bitmap &= ~(1 << slot_num)
        
        write_page(type_name, page_num, header, bytes(page_data))
        return True
    except (PageNotFoundError, InvalidSlotError):
        return False

def iterate_pages(type_name: str):
    """
    Iterator that yields all pages for a type.
    
    Args:
        type_name: Name of the type
    
    Yields:
        Tuple of (page_num, PageHeader, page_data) for each page
    
    Raises:
        PageError: For page-related errors
    """
    file_path = _get_page_file_path(type_name)
    if not os.path.exists(file_path):
        return
    
    page_num = 0
    while True:
        try:
            header, data = read_page(type_name, page_num)
            yield page_num, header, data
            page_num += 1
        except PageNotFoundError:
            break
