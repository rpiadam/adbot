#!/usr/bin/env python3
"""Backup configuration and data files."""

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path


def backup_config():
    """Create a backup of configuration and data files."""
    backup_dir = Path("backups")
    backup_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"backup_{timestamp}"
    backup_path = backup_dir / backup_name
    backup_path.mkdir(exist_ok=True)
    
    # Files to backup
    files_to_backup = [
        Path("data/config_state.json"),
        Path(".env"),
        Path(".env.encrypted"),
    ]
    
    # Directories to backup
    dirs_to_backup = [
        Path("data"),
    ]
    
    backed_up = []
    
    # Backup individual files
    for file_path in files_to_backup:
        if file_path.exists():
            dest = backup_path / file_path.name
            shutil.copy2(file_path, dest)
            backed_up.append(str(file_path))
            print(f"✓ Backed up {file_path}")
    
    # Backup directories
    for dir_path in dirs_to_backup:
        if dir_path.exists():
            dest = backup_path / dir_path.name
            shutil.copytree(dir_path, dest, dirs_exist_ok=True)
            backed_up.append(str(dir_path))
            print(f"✓ Backed up {dir_path}/")
    
    if not backed_up:
        print("⚠ No files found to backup")
        backup_path.rmdir()
        return False
    
    # Create manifest
    manifest = {
        "timestamp": timestamp,
        "backup_name": backup_name,
        "files": backed_up,
    }
    manifest_path = backup_path / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    
    print(f"\n✅ Backup created: {backup_path}")
    print(f"   Files backed up: {len(backed_up)}")
    return True


def list_backups():
    """List all available backups."""
    backup_dir = Path("backups")
    if not backup_dir.exists():
        print("No backups found")
        return
    
    backups = sorted(backup_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
    
    if not backups:
        print("No backups found")
        return
    
    print("Available backups:")
    for backup in backups:
        if backup.is_dir():
            manifest_path = backup / "manifest.json"
            if manifest_path.exists():
                with open(manifest_path) as f:
                    manifest = json.load(f)
                print(f"  - {backup.name} ({manifest.get('timestamp', 'unknown')})")
            else:
                print(f"  - {backup.name}")


def restore_backup(backup_name: str):
    """Restore from a backup."""
    backup_dir = Path("backups")
    backup_path = backup_dir / backup_name
    
    if not backup_path.exists():
        print(f"❌ Backup not found: {backup_name}")
        return False
    
    manifest_path = backup_path / "manifest.json"
    if not manifest_path.exists():
        print(f"❌ Invalid backup: missing manifest")
        return False
    
    with open(manifest_path) as f:
        manifest = json.load(f)
    
    print(f"Restoring backup: {backup_name}")
    print(f"Timestamp: {manifest.get('timestamp', 'unknown')}")
    
    # Restore files
    restored = []
    for item in backup_path.iterdir():
        if item.name == "manifest.json":
            continue
        
        dest = Path(item.name) if not item.is_dir() else Path(item.name)
        
        if item.is_dir():
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(item, dest)
            restored.append(f"{item.name}/")
        else:
            shutil.copy2(item, dest)
            restored.append(item.name)
        print(f"✓ Restored {item.name}")
    
    print(f"\n✅ Restored {len(restored)} items from backup")
    return True


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python scripts/backup_config.py backup    - Create a backup")
        print("  python scripts/backup_config.py list      - List all backups")
        print("  python scripts/backup_config.py restore <name> - Restore a backup")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "backup":
        backup_config()
    elif command == "list":
        list_backups()
    elif command == "restore":
        if len(sys.argv) < 3:
            print("❌ Please specify backup name to restore")
            print("   Use 'list' to see available backups")
            sys.exit(1)
        restore_backup(sys.argv[2])
    else:
        print(f"❌ Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()

