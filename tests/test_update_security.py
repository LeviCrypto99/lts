from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from update_security import (
    calculate_file_sha256,
    extract_sha256_from_metadata,
    normalize_sha256,
    verify_file_sha256,
)


class UpdateSecurityTests(unittest.TestCase):
    def test_normalize_sha256(self) -> None:
        sha = "A" * 64
        self.assertEqual(normalize_sha256(sha), "a" * 64)
        self.assertIsNone(normalize_sha256("abc"))
        self.assertIsNone(normalize_sha256(None))

    def test_extract_sha256_from_direct_key(self) -> None:
        metadata = {
            "app_sha256": "1" * 64,
        }
        resolved = extract_sha256_from_metadata(
            metadata,
            keys=("app_sha256", "app_hash"),
        )
        self.assertEqual(resolved, "1" * 64)

    def test_extract_sha256_from_nested_filename_key(self) -> None:
        metadata = {
            "sha256": {
                "LTS-Updater.exe": "2" * 64,
            }
        }
        resolved = extract_sha256_from_metadata(
            metadata,
            keys=("updater_sha256",),
            file_url="https://example.com/releases/LTS-Updater.exe",
        )
        self.assertEqual(resolved, "2" * 64)

    def test_verify_file_sha256(self) -> None:
        payload = b"levia-update-integrity"
        expected = hashlib.sha256(payload).hexdigest()
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "sample.bin"
            file_path.write_bytes(payload)

            calculated = calculate_file_sha256(file_path)
            self.assertEqual(calculated, expected)

            ok, actual = verify_file_sha256(file_path, expected)
            self.assertTrue(ok)
            self.assertEqual(actual, expected)

            bad_ok, bad_actual = verify_file_sha256(file_path, "0" * 64)
            self.assertFalse(bad_ok)
            self.assertEqual(bad_actual, expected)


if __name__ == "__main__":
    unittest.main()
