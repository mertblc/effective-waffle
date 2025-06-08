# Dune Archive System

A simple database system that stores and manages records for different types of data, inspired by the Dune universe.

## Features

- Create and manage different types of records (e.g., houses, planets, characters)
- Support for string and integer fields
- Primary key constraints to ensure record uniqueness
- Efficient page-based storage system
- Search and delete operations
- Command-line interface for operations
- Cross-platform compatibility (Windows and macOS)

## Project Structure

```
.
├── archive.py              # Main entry point and command processor
├── utils/
│   ├── catalog_utils.py    # Type definitions and catalog management
│   ├── page_utils.py       # Page-level storage operations
│   ├── record_utils.py     # Record serialization and validation
│   └── field_types.py      # Field type definitions
├── updated_input.txt       # Sample input file for testing
├── makefile               # Cross-platform build and clean commands
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

2. Run the system:
   ```bash
   # Using Python directly
   python archive.py <input-file>  # Windows
   python3 archive.py <input-file> # macOS

   # Or using make
   make test
   ```

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

## Development

The project includes a cross-platform makefile for common development tasks:

```bash
# Clean up database files and logs
make clean

# Run the system with sample input
make test

# Clean and run tests
make all
```

These commands work on both Windows and macOS. The makefile automatically detects the operating system and uses the appropriate commands.

## Notes

- The system uses a page-based storage mechanism
- Each page can store up to 10 records
- String fields are limited to 32 bytes
- Integer fields are 8-byte signed integers
- Primary keys must be unique within each type
- Database files (`catalog.txt`, `pages/`, `output.txt`, `log.csv`) are automatically ignored by Git
- Python cache files (`__pycache__/`, `*.pyc`) are also ignored

## Contributing

1. Fork the repository
2. Create a new branch for your feature
3. Make your changes
4. Submit a pull request

## License

This project is open source and available under the MIT License.
