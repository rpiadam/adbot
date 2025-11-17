#!/usr/bin/env python3
"""
Utility script to encrypt an entire .env file.

Usage:
    python scripts/encrypt_env_file.py .env
    
This creates .env.encrypted with the encrypted contents.

To use an encrypted .env file, set ENCRYPTION_KEY or ENCRYPTION_KEY_FILE
and rename .env.encrypted to .env, or set ENV_FILE=.env.encrypted
"""

import base64
import os
import sys
from pathlib import Path

from cryptography.fernet import Fernet


def get_encryption_key() -> bytes:
    """Get encryption key from environment or key file."""
    # Try environment variable first
    key_str = os.getenv("ENCRYPTION_KEY")
    if key_str:
        return key_str.encode()
    
    # Try key file
    key_file = os.getenv("ENCRYPTION_KEY_FILE", ".encryption_key")
    if os.path.exists(key_file):
        with open(key_file, "rb") as f:
            return f.read().strip()
    
    # Generate new key if none exists
    print("No encryption key found. Generating new key...", file=sys.stderr)
    new_key = Fernet.generate_key()
    print(f"New encryption key (save this!): {new_key.decode()}", file=sys.stderr)
    print(f"\nTo use it:", file=sys.stderr)
    print(f"  export ENCRYPTION_KEY='{new_key.decode()}'", file=sys.stderr)
    print(f"  # Or save to file:", file=sys.stderr)
    print(f"  echo '{new_key.decode()}' > .encryption_key", file=sys.stderr)
    print("", file=sys.stderr)
    return new_key


def encrypt_file(input_path: Path, output_path: Path, key: bytes) -> None:
    """Encrypt a file and write to output path."""
    fernet = Fernet(key)
    
    with open(input_path, "rb") as f:
        plaintext = f.read()
    
    encrypted = fernet.encrypt(plaintext)
    
    with open(output_path, "wb") as f:
        f.write(encrypted)
    
    print(f"Encrypted {input_path} -> {output_path}")
    print(f"Original file size: {len(plaintext)} bytes")
    print(f"Encrypted file size: {len(encrypted)} bytes")


def main():
    if len(sys.argv) != 2:
        print("Usage: python encrypt_env_file.py <input-file>", file=sys.stderr)
        print("\nExample:", file=sys.stderr)
        print("  python scripts/encrypt_env_file.py .env", file=sys.stderr)
        print("\nThis creates .env.encrypted", file=sys.stderr)
        print("\nGenerate a key first:", file=sys.stderr)
        print('  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"', file=sys.stderr)
        sys.exit(1)
    
    input_file = Path(sys.argv[1])
    if not input_file.exists():
        print(f"Error: File not found: {input_file}", file=sys.stderr)
        sys.exit(1)
    
    # Default output is input file with .encrypted extension
    output_file = input_file.with_suffix(input_file.suffix + ".encrypted")
    
    # If output file already exists, ask for confirmation
    if output_file.exists():
        response = input(f"{output_file} already exists. Overwrite? [y/N]: ")
        if response.lower() != 'y':
            print("Cancelled.", file=sys.stderr)
            sys.exit(0)
    
    try:
        key = get_encryption_key()
        encrypt_file(input_file, output_file, key)
        print(f"\n✓ Successfully encrypted file.")
        print(f"\nTo use the encrypted file, either:")
        print(f"  1. Rename it: mv {output_file} {input_file}")
        print(f"  2. Or set ENV_FILE={output_file} environment variable")
    except Exception as e:
        print(f"Error encrypting file: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

