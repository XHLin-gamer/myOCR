import re
import os
import requests


def clean_and_format_layout(text: str) -> str:
    """
    Remove page numbers and perform deterministic layout cleaning on the text.
    """
    cleaned_lines = []
    for line in text.splitlines():
        trimmed = line.strip()
        # Strip lines containing only page numbers (e.g. "- 1 -", "• 1 -", "1", etc.)
        if re.match(r"^\s*[-•・★]?\s*\d+\s*[-•・★]?\s*$", trimmed):
            continue
        cleaned_lines.append(line)
    return "\n".join(cleaned_lines)


def update_env_file(key: str, value: str, env_path: str = ".env") -> None:
    """
    Update or insert a key=value pair in the local .env file.
    """
    lines = []
    key_exists = False
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

    new_lines = []
    for line in lines:
        if line.strip().startswith(f"{key}="):
            new_lines.append(f"{key}={value}\n")
            key_exists = True
        else:
            new_lines.append(line)

    if not key_exists:
        if new_lines and not new_lines[-1].endswith("\n"):
            new_lines[-1] += "\n"
        new_lines.append(f"{key}={value}\n")

    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
