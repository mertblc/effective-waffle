import os
import subprocess
import tempfile
import unittest
from pathlib import Path

class TestDuneArchiveSystem(unittest.TestCase):
    ARCHIVE_SCRIPT = "archive.py"  # Adjust path if needed

    def run_archive(self, input_commands):
        """Helper to run archive.py with given commands and return output/log contents."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cwd = Path(tmpdir)
            # Copy script into tmpdir
            src = Path(TestDuneArchiveSystem.ARCHIVE_SCRIPT)
            dst = cwd / "archive.py"
            dst.write_bytes(src.read_bytes())
            # Prepare utils and pages folder
            utils_dir = cwd / "utils"
            utils_dir.mkdir()
            # Copy utils modules
            for fname in Path("utils").glob("*.py"):
                (utils_dir / fname.name).write_bytes(fname.read_bytes())
            # Create input file
            input_path = cwd / "input.txt"
            input_path.write_text("\n".join(input_commands))
            # Run the script
            subprocess.run(
                ["python3", "archive.py", str(input_path)],
                cwd=cwd,
                check=True
            )
            # Read outputs
            output = (cwd / "output.txt").read_text().strip().splitlines()
            log = (cwd / "log.csv").read_text().strip().splitlines()
        return output, log

    def test_create_and_search(self):
        cmds = [
            "create type house 6 1 name str origin str leader str military_strength int wealth int spice_production int",
            "create record house Atreides Caladan Duke 8000 5000 150",
            "search record house Atreides"
        ]
        output, log = self.run_archive(cmds)
        self.assertIn("Atreides Caladan Duke 8000 5000 150", output)
        # Log should contain success entries
        self.assertTrue(any("create type house" in line and "success" in line for line in log))
        self.assertTrue(any("search record house Atreides" in line and "success" in line for line in log))

    def test_delete_and_search(self):
        cmds = [
            "create type fremen 5 1 name str tribe str skill_level int allegiance str age int",
            "create record fremen Stilgar SietchTabr 9 Atreides 45",
            "delete record fremen Stilgar",
            "search record fremen Stilgar"
        ]
        output, log = self.run_archive(cmds)
        # After deletion, search should fail (no output)
        self.assertEqual(output, [])
        # Last log entry for search should indicate failure
        last_log = log[-1]
        self.assertIn("search record fremen Stilgar", last_log)
        self.assertTrue(last_log.endswith("failure"))

    def test_duplicate_type_and_record(self):
        cmds = [
            "create type planet 2 1 name str size int",
            "create type planet 2 1 name str size int",  # duplicate
            "create record planet Dune 500",
            "create record planet Dune 500"  # duplicate record
        ]
        output, log = self.run_archive(cmds)
        # Second create type must record success if idempotent or failure otherwise
        self.assertTrue(any("create type planet" in line for line in log))
        # Duplicate record should be failure in log
        dup_record_log = [l for l in log if "create record planet Dune 500" in l]
        self.assertTrue(any("failure" in l for l in dup_record_log))

    def test_pagination_and_large_volume(self):
        # Insert 12 records to fill more than one page (10 slots/page)
        cmds = ["create type test 1 1 id int"]
        for i in range(12):
            cmds.append(f"create record test {i}")
        # Search for last record
        cmds.append("search record test 11")
        output, log = self.run_archive(cmds)
        self.assertIn("11", output)

    def test_invalid_operations(self):
        cmds = [
            "invalid command",
            "create record no_table 1"
        ]
        output, log = self.run_archive(cmds)
        # Both should be logged as failures
        self.assertTrue(all("failure" in line for line in log if line != "timestamp,operation,status"))
        
    # --- Additional edge-case tests ---

    def test_empty_string_field(self):
        cmds = [
            "create type note 1 1 text str",
            "create record note \"\"",
            "search record note \"\""
        ]
        output, log = self.run_archive(cmds)
        self.assertIn("", output)

    def test_max_length_string(self):
        # string max_length = 32 bytes, create 32-char string
        long_str = "A" * 32
        cmds = [
            "create type tag 1 1 label str",
            f"create record tag {long_str}",
            f"search record tag {long_str}"
        ]
        output, log = self.run_archive(cmds)
        self.assertIn(long_str, output)

    def test_string_truncation_or_rejection(self):
        # 33-char string should be rejected or truncated to 32
        too_long = "B" * 33
        cmds = [
            "create type tag 1 1 label str",
            f"create record tag {too_long}"
        ]
        output, log = self.run_archive(cmds)
        # Should log failure for this record creation
        self.assertTrue(any("failure" in l for l in log if "create record tag" in l))

    def test_negative_and_boundary_integers(self):
        min_int = str(-2**63)
        max_int = str(2**63 - 1)
        cmds = [
            "create type numbers 2 1 neg int pos int",
            f"create record numbers {min_int} {max_int}",
            f"search record numbers {min_int}"
        ]
        output, log = self.run_archive(cmds)
        self.assertIn(f"{min_int} {max_int}", output)

    def test_insert_after_delete_reuse_slot(self):
        cmds = [
            "create type item 1 1 id int"
        ]
        # insert, delete, then insert again to reuse slot 0
        cmds += [
            "create record item 10",
            "delete record item 10",
            "create record item 20",
            "search record item 20"
        ]
        output, log = self.run_archive(cmds)
        self.assertIn("20", output)

    def test_delete_from_empty_table(self):
        cmds = [
            "create type empty 1 1 a int",
            "delete record empty 1"
        ]
        output, log = self.run_archive(cmds)
        # delete should fail
        self.assertTrue(any("delete record empty 1" in l and l.endswith("failure") for l in log))

    def test_search_no_records(self):
        cmds = [
            "create type nobody 1 1 name str",
            "search record nobody nobody"
        ]
        output, log = self.run_archive(cmds)
        self.assertEqual(output, [])
        last_log = log[-1]
        self.assertTrue(last_log.endswith("failure"))
        

if __name__ == "__main__":
    unittest.main()

