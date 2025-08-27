"""
Policy loader wrapper script.

This script provides a simpler interface to the standalone_loader package.
"""
import sys
from standalone_loader.cli import main

if __name__ == "__main__":
    sys.exit(main())
