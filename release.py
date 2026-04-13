#!/usr/bin/env python3
"""
Automated build and publish script for mindretriever.

Usage:
    python release.py                 # Build only
    python release.py --test-upload   # Build and test upload
    python release.py --upload        # Build and upload to PyPI
"""

import sys
import subprocess
import shutil
from pathlib import Path
from argparse import ArgumentParser


def run_command(cmd, description):
    """Run command and handle errors."""
    print(f"\n{'='*60}")
    print(f"🚀 {description}")
    print(f"{'='*60}")
    print(f"Command: {' '.join(cmd)}")

    result = subprocess.run(cmd, capture_output=False)
    if result.returncode != 0:
        print(f"❌ {description} failed with exit code {result.returncode}")
        sys.exit(1)
    print(f"✅ {description} completed")


def clean_builds():
    """Remove previous build artifacts."""
    print("\n🧹 Cleaning previous builds...")
    dirs_to_remove = ["build", "dist", "mindretriever.egg-info", ".pytest_cache"]
    for dirname in dirs_to_remove:
        path = Path(dirname)
        if path.exists():
            shutil.rmtree(path)
            print(f"  Removed {dirname}")


def build_package():
    """Build distribution packages."""
    run_command(
        [sys.executable, "-m", "build"],
        "Build distribution packages"
    )


def validate_package():
    """Validate built packages."""
    run_command(
        [sys.executable, "-m", "twine", "check", "dist/*"],
        "Validate package metadata"
    )


def test_upload():
    """Upload to TestPyPI."""
    api_token = input("\n📝 Enter your TestPyPI API token (from https://test.pypi.org/manage/account/token/): ").strip()
    if not api_token:
        print("❌ No token provided")
        sys.exit(1)

    run_command(
        [
            sys.executable, "-m", "twine", "upload",
            "--repository", "testpypi",
            "dist/*",
            "--username", "__token__",
            "--password", api_token,
        ],
        "Upload to TestPyPI"
    )

    print("\n✅ Test upload complete!")
    print("📦 Test installation: pip install --index-url https://test.pypi.org/simple/ mindretriever")


def upload_to_pypi():
    """Upload to production PyPI."""
    api_token = input("\n📝 Enter your PyPI API token (from https://pypi.org/manage/account/token/): ").strip()
    if not api_token:
        print("❌ No token provided")
        sys.exit(1)

    run_command(
        [
            sys.executable, "-m", "twine", "upload",
            "dist/*",
            "--username", "__token__",
            "--password", api_token,
        ],
        "Upload to PyPI"
    )

    print("\n" + "="*60)
    print("🎉 Package published to PyPI!")
    print("="*60)
    print("📦 Installation: pip install mindretriever")
    print("🔗 Package: https://pypi.org/project/mindretriever/")
    print("="*60)


def main():
    """Main entry point."""
    parser = ArgumentParser(description="Build and publish mindretriever to PyPI")
    parser.add_argument("--test-upload", action="store_true", help="Upload to TestPyPI")
    parser.add_argument("--upload", action="store_true", help="Upload to production PyPI")
    parser.add_argument("--check-only", action="store_true", help="Only validate, don't upload")

    args = parser.parse_args()

    # Check for required tools
    print("🔍 Checking for required tools...")
    try:
        subprocess.run([sys.executable, "-m", "build", "--version"], capture_output=True, check=True)
        subprocess.run([sys.executable, "-m", "twine", "--version"], capture_output=True, check=True)
        print("✅ All required tools found")
    except subprocess.CalledProcessError:
        print("❌ Missing required tools. Install with:")
        print("   pip install build twine wheel setuptools")
        sys.exit(1)

    # Build process
    clean_builds()
    build_package()

    if args.check_only:
        validate_package()
        print("\n✅ Package validation complete!")
        sys.exit(0)

    # Determine upload target
    if args.test_upload:
        test_upload()
    elif args.upload:
        upload_to_pypi()
    else:
        print("\n✅ Package built successfully in dist/")
        print("\nNext steps:")
        print("  1. Validate:          python release.py --check-only")
        print("  2. Test upload:       python release.py --test-upload")
        print("  3. Upload to PyPI:    python release.py --upload")


if __name__ == "__main__":
    main()
