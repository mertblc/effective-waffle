# Detect OS
ifeq ($(OS),Windows_NT)
    RM_FILE = del /f /q
    RM_DIR = rmdir /s /q
    PYTHON = python
else
    RM_FILE = rm -f
    RM_DIR = rm -rf
    PYTHON = python3
endif

clean:
	$(RM_FILE) catalog.txt
	$(RM_DIR) pages
	$(RM_FILE) output.txt log.csv

test:
	$(PYTHON) archive.py updated_input.txt

all: clean test

.PHONY: clean test all