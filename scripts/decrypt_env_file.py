#!/usr/bin/env python3
"""
Utility script to decrypt an encrypted .env file.

Usage:
    python scripts/decrypt_env_file.py .env.encrypted
    
This creates .env with the decrypted contents.
"""

import os
import sys
from pathlib import Path

from cryptography.fernet import Fernet


def get_decryption_key() -> bytes:
    """Get decryption key from environment or key file."""
    # Try environment variable first
    key_str = os.getenv("ENCRYPTION_KEY")
    if key_str:
        return key_str.encode()
    
    # Try key file
    key_file = os.getenv("ENCRYPTION_KEY_FILE", ".encryption_key")
    if os.path.exists(key_file):
        with open(key_file, "rb") as f:
            return f.read().strip()
    
    print("Error: ENCRYPTION_KEY or ENCRYPTION_KEY_FILE must be set", file=sys.stderr)
    print("\nSet the encryption key:", file=sys.stderr)
    print("  export ENCRYPTION_KEY='your-key-here'", file=sys.stderr)
    print("  # Or:", file=sys.stderr)
    print("  export ENCRYPTION_KEY_FILE=.encryption_key", file=sys.stderr)
    sys.exit(1)


def decrypt_file(input_path: Path, output_path: Path, key: bytes) -> None:
    """Decrypt a file and write to output path."""
    fernet = Fernet(key)
    
    with open(input_path, "rb") as f:
        encrypted = f.read()
    
    try:
        plaintext = fernet.decrypt(encrypted)
    except Exception as e:
        print(f"Error: Failed to decrypt file. Wrong key? {e}", file=sys.stderr)
        sys.exit(1)
    
    with open(output_path, "wb") as f:
        f.write(plaintext)
    
    print(f"Decrypted {input_path} -> {output_path}")
    print(f"Decrypted file size: {len(plaintext)} bytes")


def main():
    if len(sys.argv) != 2:
        print("Usage: python decrypt_env_file.py <encrypted-file>", file=sys.stderr)
        print("\nExample:", file=sys.stderr)
        print("  python scripts/decrypt_env_file.py .env.encrypted", file=sys.stderr)
        print("\nThis creates .env with decrypted contents", file=sys.stderr)
        sys.exit(1)
    
    input_file = Path(sys.argv[1])
    if not input_file.exists():
        print(f"Error: File not found: {input_file}", file=sys.stderr)
        sys.exit(1)
    
    # Default output removes .encrypted extension
    if input_file.suffix == ".encrypted":
        output_file = input_file.with_suffix("")
    else:
        output_file = input_file.with_suffix(input_file.suffix + ".decrypted")
    
    # If output file already exists, ask for confirmation
    if output_file.exists():
        response = input(f"{output_file} already exists. Overwrite? [y/N]: ")
        if response.lower() != 'y':
            print("Cancelled.", file=sys.stderr)
            sys.exit(0)
    
    try:
        key = get_decryption_key()
        decrypt_file(input_file, output_file, key)
        print(f"\n✓ Successfully decrypted file.")
    except Exception as e:
        print(f"Error decrypting file: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

