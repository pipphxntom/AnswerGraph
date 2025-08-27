"""
Run database migrations.

This script runs Alembic migrations to create or update the database schema.
"""
import argparse
import os
import subprocess
import sys


def run_migrations(offline: bool = False, revision: str = 'head') -> int:
    """Run Alembic migrations."""
    # Ensure we're in the correct directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(script_dir)
    os.chdir(root_dir)
    
    # Build command
    if offline:
        cmd = ['alembic', 'upgrade', revision, '--sql']
    else:
        cmd = ['alembic', 'upgrade', revision]
    
    # Run command
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    # Display output
    if result.stdout:
        print("Output:")
        print(result.stdout)
    
    if result.stderr:
        print("Errors:")
        print(result.stderr)
    
    return result.returncode


def main():
    parser = argparse.ArgumentParser(description="Run database migrations")
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Generate SQL but don't run it"
    )
    parser.add_argument(
        "--revision",
        default="head",
        help="Target revision (default: head)"
    )
    
    args = parser.parse_args()
    
    exit_code = run_migrations(offline=args.offline, revision=args.revision)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
