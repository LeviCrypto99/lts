from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from log_rotation import append_rotating_log_line
from runtime_paths import get_log_path


class LogRotationAndRuntimePathTests(unittest.TestCase):
    def test_get_log_path_uses_logs_subfolder_with_named_stream_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime_exe = Path(temp_dir) / "LTS.exe"
            runtime_exe.write_text("", encoding="utf-8")

            path = get_log_path("LTS-Trade.log", target_executable=runtime_exe)

            self.assertEqual(path.parent.name, "LTS-Trade_log_file")
            self.assertEqual(path.parent.parent.name, "logs")
            self.assertEqual(path.name, "LTS-Trade.log")

    def test_rotation_keeps_max_ten_files_total_for_one_log_stream(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / "logs" / "LTS-Trade_log_file" / "LTS-Trade.log"
            for index in range(120):
                append_rotating_log_line(
                    log_path,
                    f"[{index:03d}] {'x' * 260}\n",
                    max_bytes=1024,
                    backup_count=9,
                )

            files = sorted(log_path.parent.glob("LTS-Trade.log*"))
            self.assertTrue(log_path.exists())
            self.assertLessEqual(len(files), 10)
            self.assertFalse((log_path.parent / "LTS-Trade.log.10").exists())
            for item in files:
                self.assertLessEqual(item.stat().st_size, 1024)

    def test_rotation_removes_backups_over_limit_during_next_roll(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / "logs" / "LTS-Login_log_file" / "LTS-Login.log"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text("A" * 1100, encoding="utf-8")
            (log_path.parent / "LTS-Login.log.10").write_text("old", encoding="utf-8")
            (log_path.parent / "LTS-Login.log.11").write_text("older", encoding="utf-8")

            append_rotating_log_line(
                log_path,
                "[001] trigger rotate\n",
                max_bytes=1024,
                backup_count=9,
            )

            self.assertFalse((log_path.parent / "LTS-Login.log.10").exists())
            self.assertFalse((log_path.parent / "LTS-Login.log.11").exists())


if __name__ == "__main__":
    unittest.main()
