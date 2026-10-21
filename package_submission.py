"""
datapype - Submission Packaging Script
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Creates a clean, self-contained ZIP archive containing:
  - The Python module (datapype/)
  - The automated test suite (tests/)
  - Test documentation & methodology (TEST_DOCUMENTATION.md, README.md)
  - Runner and demo scripts (run_tests.py, demo.py)
  - Metadata and dependency files (pyproject.toml, requirements.txt, requirements-dev.txt)

Usage:
    python package_submission.py
"""

import os
import zipfile
from pathlib import Path


def create_submission_zip(output_zip_name: str = "datapype_test_submission.zip") -> str:
    root_dir = Path(__file__).parent.resolve()
    output_path = root_dir / output_zip_name

    # Files and directories to include
    include_dirs = ["datapype", "tests"]
    include_files = [
        "README.md",
        "TEST_DOCUMENTATION.md",
        "demo.py",
        "run_tests.py",
        "pyproject.toml",
        "requirements.txt",
        "requirements-dev.txt",
    ]

    # Exclusions (cache, byte-code, temporary files)
    exclude_patterns = ["__pycache__", ".pytest_cache", ".coverage", "*.pyc", "*.pyo"]

    print("=" * 70)
    print(f"Creating Submission Archive: {output_zip_name}")
    print("=" * 70)

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        # Add directories
        for d in include_dirs:
            dir_path = root_dir / d
            for file_path in dir_path.rglob("*"):
                # Check exclusions
                if any(ex in str(file_path) for ex in exclude_patterns):
                    continue
                if file_path.is_file():
                    arcname = file_path.relative_to(root_dir)
                    zipf.write(file_path, arcname)
                    print(f"  + Added: {arcname}")

        # Add root files
        for f in include_files:
            file_path = root_dir / f
            if file_path.exists() and file_path.is_file():
                zipf.write(file_path, f)
                print(f"  + Added: {f}")
            else:
                print(f"  ! Warning: {f} not found!")

    archive_size_kb = output_path.stat().st_size / 1024
    print("\n" + "=" * 70)
    print(f"Archive successfully created: {output_path.name} ({archive_size_kb:.1f} KB)")
    print("=" * 70)

    # Verify archive content
    with zipfile.ZipFile(output_path, "r") as zipf:
        namelist = zipf.namelist()
        print(f"Verified {len(namelist)} files packaged inside archive.")

    return str(output_path)


if __name__ == "__main__":
    create_submission_zip()
