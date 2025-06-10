# Dune Archive System

A simple database system that stores and manages records for different types of data, inspired by the Dune universe.

## Features

- Create and manage different types of records (e.g., houses, planets, characters)
- Support for string and integer fields
- Primary key constraints to ensure record uniqueness
- Efficient page-based storage system
- Search and delete operations
- Command-line interface for operations

## Project Structure

```
.
├── archive.py              # Main entry point and command processor
├── utils/
│   ├── catalog_utils.py    # Type definitions and catalog management
│   ├── page_utils.py       # Page-level storage operations
│   ├── record_utils.py     # Record serialization and validation
│   └── field_types.py      # Field type definitions

```

## Prerequisites

- Python 3.x
- Git (for version control)
- Make (for build commands)
  - Windows: Install via [Chocolatey](https://chocolatey.org/) (`choco install make`)
  - macOS: Install via [Homebrew](https://brew.sh/) (`brew install make`)

## Setup

1. Clone this repository:
   ```bash
   git clone <repository-url>
   cd ProjectDatabase
   ```
2.	Create a Python 3.11 virtual environment:
   ```
   python3.11 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Run the system:
   ```bash
   # Using Python directly
   python archive.py <input-file>  # Windows
   python3 archive.py <input-file> # macOS

## Usage

The system accepts commands through an input file. Each line represents an operation:

```
# Create a new type
create type <type_name> <num_fields> <pk_index> <field1> <type1> <field2> <type2> ...

# Create a record
create record <type_name> <field1_value> <field2_value> ...

# Search for records
search record <type_name> <key_value>

# Delete a record
delete record <type_name> <key_value>
```

### Example

```
# Create a type for houses
create type house 6 1 name str origin str leader str military_strength int wealth int spice_production int

# Create a record
create record house Atreides Caladan Duke 8000 5000 150

# Search for a record
search record house Atreides
```
