#!/usr/bin/env python3
"""
Utility script to encrypt environment variable values for use in .env files.

Usage:
    python scripts/encrypt_env_value.py "my-secret-value"
    
This will output: encrypted:<base64-encrypted-value>

Then set ENCRYPTION_KEY or ENCRYPTION_KEY_FILE to the encryption key.
Generate a key with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""

import base64
import os
import sys

from cryptography.fernet import Fernet


def main():
    if len(sys.argv) != 2:
        print("Usage: python encrypt_env_value.py <value-to-encrypt>", file=sys.stderr)
        print("\nFirst, generate an encryption key:", file=sys.stderr)
        print('  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"', file=sys.stderr)
        print("\nSet ENCRYPTION_KEY environment variable or ENCRYPTION_KEY_FILE path", file=sys.stderr)
        sys.exit(1)
    
    # Try to get key from environment
    key_str = None
    if "ENCRYPTION_KEY" in os.environ:
        key_str = os.environ["ENCRYPTION_KEY"]
    elif "ENCRYPTION_KEY_FILE" in os.environ:
        key_file = os.environ["ENCRYPTION_KEY_FILE"]
        with open(key_file, "rb") as f:
            key_str = f.read().decode().strip()
    else:
        print("Error: ENCRYPTION_KEY or ENCRYPTION_KEY_FILE must be set", file=sys.stderr)
        print("\nGenerate a key with:", file=sys.stderr)
        print('  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"', file=sys.stderr)
        sys.exit(1)
    
    try:
        # Fernet keys are base64-encoded strings - use directly as bytes
        key = key_str.encode()
        fernet = Fernet(key)
        value = sys.argv[1]
        encrypted = fernet.encrypt(value.encode())
        encrypted_b64 = base64.urlsafe_b64encode(encrypted).decode()
        print(f"encrypted:{encrypted_b64}")
    except Exception as e:
        print(f"Error encrypting value: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

