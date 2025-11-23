#!/usr/bin/env python3
"""
Create a zip file of the bot code for distribution.
Excludes sensitive files like .env, logs, etc.
"""
import os
import zipfile
import tempfile
from pathlib import Path
from typing import Set

# Files and directories to exclude
EXCLUDE_PATTERNS: Set[str] = {
    # Environment and secrets
    ".env",
    ".env.local",
    ".env.*.local",
    ".env.encrypted",
    ".encryption_key",
    ".env.backup*",
    # Python
    "__pycache__",
    "*.pyc",
    "*.pyo",
    ".pytest_cache",
    ".mypy_cache",
    ".venv",
    "venv",
    "ENV",
    "env",
    # Ruby
    ".bundle",
    "vendor",
    "Gemfile.lock",
    ".ruby-gemset",
    # Logs and data
    "logs",
    "*.log",
    "data",
    "backups",
    # IDE
    ".vscode",
    ".idea",
    "*.swp",
    "*.swo",
    # OS
    ".DS_Store",
    "Thumbs.db",
    # Build artifacts
    "build",
    "dist",
    "*.egg-info",
    # Git
    ".git",
    ".gitignore",
    # Docker
    "*.dockerignore",
    # Temporary
    "*.tmp",
    "*.temp",
    "*.bak",
    # Coverage
    "htmlcov",
    ".coverage",
    "coverage.xml",
    # Node (for dashboard-nextjs)
    "node_modules",
    ".next",
    # iOS (if present)
    "ios",
}


def should_exclude(path: Path, root: Path) -> bool:
    """Check if a path should be excluded from the zip."""
    rel_path = path.relative_to(root)
    
    # Check each part of the path
    for part in rel_path.parts:
        # Check exact matches
        if part in EXCLUDE_PATTERNS:
            return True
        
        # Check patterns
        for pattern in EXCLUDE_PATTERNS:
            if pattern.startswith("*") and part.endswith(pattern[1:]):
                return True
            if pattern.endswith("*") and part.startswith(pattern[:-1]):
                return True
            if "*" in pattern:
                # Simple glob matching
                import fnmatch
                if fnmatch.fnmatch(part, pattern):
                    return True
    
    # Check file extensions
    if path.is_file():
        for pattern in EXCLUDE_PATTERNS:
            if pattern.startswith("*.") and path.suffix == pattern[1:]:
                return True
    
    return False


def create_bot_zip(version: str = "python", output_path: Path = None) -> Path:
    """
    Create a zip file of the bot code.
    
    Args:
        version: "python" or "ruby" - determines which files to include
        output_path: Optional path for the output zip file
    
    Returns:
        Path to the created zip file
    """
    root_dir = Path(__file__).parent.parent
    if output_path is None:
        output_path = tempfile.mktemp(suffix=f"-uplove-{version}.zip", dir=tempfile.gettempdir())
    output_path = Path(output_path)
    
    # Files/directories to include based on version
    if version == "python":
        include_dirs = [
            "src",
            "scripts",
            "tests",
            "docs",
            "dashboard",
            "dashboard-nextjs",  # Include but note it's optional
        ]
        include_files = [
            "requirements.txt",
            "README.md",
            "README_RUBY.md",
            "QUICK_START.md",
            "example.env",
            "LICENSE",
            "Dockerfile",
            "docker-compose.yml",
            "DEPLOYMENT_GUIDE.md",
            "DEPLOYMENT_STEPS.md",
            "CHOOSING_LANGUAGE.md",
            "NEXT_STEPS.md",
            "RUBY_BOT_STRUCTURE.md",
            ".gitignore",
        ]
    elif version == "ruby":
        include_dirs = [
            "lib",
            "bin",
            "spec",
        ]
        include_files = [
            "Gemfile",
            "README.md",
            "README_RUBY.md",
            "QUICK_START.md",
            "example.env",
            "LICENSE",
            "RUBY_BOT_STRUCTURE.md",
        ]
    else:
        raise ValueError(f"Unknown version: {version}. Use 'python' or 'ruby'")
    
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        # Add included directories
        for dir_name in include_dirs:
            dir_path = root_dir / dir_name
            if dir_path.exists() and dir_path.is_dir():
                for file_path in dir_path.rglob("*"):
                    if file_path.is_file() and not should_exclude(file_path, root_dir):
                        arcname = file_path.relative_to(root_dir)
                        zipf.write(file_path, arcname)
        
        # Add included files
        for file_name in include_files:
            file_path = root_dir / file_name
            if file_path.exists() and file_path.is_file():
                if not should_exclude(file_path, root_dir):
                    zipf.write(file_path, file_name)
        
        # Add a README for the zip
        readme_content = f"""# UpLove Bot - {version.capitalize()} Version

This is a distribution package of the UpLove Discord/IRC relay bot ({version} version).

## Quick Start

### Python Version:
1. Create virtual environment: `python3 -m venv .venv && source .venv/bin/activate`
2. Install dependencies: `pip install -r requirements.txt`
3. Copy `example.env` to `.env` and configure it
4. Run: `python -m src.main`

### Ruby Version:
1. Install dependencies: `bundle install`
2. Copy `example.env` to `.env` and configure it
3. Run: `ruby -Ilib bin/ruby_bot`

## Configuration

See `example.env` for all configuration options. At minimum you need:
- DISCORD_TOKEN
- DISCORD_CHANNEL_ID
- IRC_SERVER (or IRC_SERVERS)
- IRC_CHANNEL (or IRC_CHANNELS)
- IRC_NICK (or IRC_NICKS)

## Documentation

See README.md for full documentation.

## License

See LICENSE file for license information.
"""
        zipf.writestr("ZIP_README.txt", readme_content)
    
    return output_path


if __name__ == "__main__":
    import sys
    
    version = sys.argv[1] if len(sys.argv) > 1 else "python"
    if version not in ("python", "ruby"):
        print(f"Usage: {sys.argv[0]} [python|ruby]")
        sys.exit(1)
    
    output = create_bot_zip(version)
    print(f"Created zip file: {output}")
    print(f"Size: {output.stat().st_size / 1024 / 1024:.2f} MB")

