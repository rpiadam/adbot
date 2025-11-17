#!/usr/bin/env python3
"""Generate a bcrypt hash for the dashboard password."""

import sys
from pathlib import Path

# Add parent directory to path to import dashboard module
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.dashboard import get_password_hash


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/hash_dashboard_password.py <password>")
        print("\nExample:")
        print("  python scripts/hash_dashboard_password.py mypassword123")
        print("\nThen update your .env file:")
        print("  DASHBOARD_PASSWORD=<hash_output>")
        sys.exit(1)
    
    password = sys.argv[1]
    hashed = get_password_hash(password)
    
    print(f"\nPassword hash: {hashed}")
    print("\nAdd this to your .env file:")
    print(f"DASHBOARD_PASSWORD={hashed}")
    print("\n⚠️  Keep this hash secure! Anyone with it can authenticate.")


if __name__ == "__main__":
    main()

