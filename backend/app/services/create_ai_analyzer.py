#!/usr/bin/env python3
"""
Script to create the ai_analyzer directory structure and files.
"""

import os
import sys
from pathlib import Path

# Directory structure
STRUCTURE = {
    "ai_analyzer": {
        "__init__.py": "",
        "analyzer.py": "",
        "models.py": "",
        "patterns.py": "",
        "transaction_parser.py": "",
        "utils.py": "",
        "deterministic": {
            "__init__.py": "",
            "metrics.py": "",
            "categories.py": "",
            "income.py": "",
            "fuliza.py": "",
            "health.py": "",
            "recurring.py": "",
            "anomalies.py": "",
            "insights.py": "",
        },
        "ai_providers": {
            "__init__.py": "",
            "base.py": "",
            "gemini.py": "",
            "claude.py": "",
            "deepseek.py": "",
            "openai.py": "",
        },
    }
}


def create_structure(base_path: str):
    """Create the directory structure and files."""
    base = Path(base_path)

    def create_recursive(structure: dict, current_path: Path):
        for name, content in structure.items():
            path = current_path / name
            if isinstance(content, dict):
                # Create directory
                path.mkdir(parents=True, exist_ok=True)
                create_recursive(content, path)
            else:
                # Create file
                # The content would be the actual file content from the code above
                # For this script, we'll create empty files with a placeholder
                path.write_text(f"# {name} - Auto-generated file\n# Add content here\n")
                print(f"Created: {path}")

    create_recursive(STRUCTURE, base)
    print(f"✅ Created ai_analyzer structure in: {base}")


if __name__ == "__main__":
    # Use the current directory or specify a path
    target_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    create_structure(target_dir)
