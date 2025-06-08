clean:
	del /f /q catalog.txt
	rmdir /s /q pages
	del /f /q output.txt log.csv

test:
	python archive.py updated_input.txt

all: clean test