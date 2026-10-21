"""
datapype - Automated Test Suite Runner
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Convenience script to run the full test suite and coverage reports.
Supports both pytest (with coverage metrics) and standard library unittest fallback.

Usage:
    python run_tests.py             # Runs pytest with coverage (or falls back to unittest)
    python run_tests.py --pytest    # Force pytest execution
    python run_tests.py --unittest  # Force standard library unittest
"""

import sys
import subprocess


def run_pytest() -> int:
    print("=" * 70)
    print("  Running test suite via PYTEST (with coverage)...")
    print("=" * 70)
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "-v",
        "--cov=datapype",
        "--cov-report=term-missing",
    ]
    return subprocess.run(cmd).returncode


def run_unittest() -> int:
    print("=" * 70)
    print("  Running test suite via Python standard library UNITTEST...")
    print("=" * 70)
    cmd = [sys.executable, "-m", "unittest", "discover", "-v", "-s", "tests"]
    return subprocess.run(cmd).returncode


def main() -> None:
    if "--unittest" in sys.argv:
        code = run_unittest()
    elif "--pytest" in sys.argv:
        code = run_pytest()
    else:
        # Default: try pytest, fallback to unittest if pytest not installed
        try:
            import pytest  # noqa: F401
            code = run_pytest()
        except ImportError:
            print("[INFO] pytest not detected in environment. Falling back to unittest runner.")
            code = run_unittest()

    if code == 0:
        print("\n[SUCCESS] All test suites passed successfully!")
    else:
        print(f"\n[FAILURE] Test suite returned exit code {code}.")
    sys.exit(code)


if __name__ == "__main__":
    main()
