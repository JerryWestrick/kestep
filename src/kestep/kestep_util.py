import os
import re
from typing import Optional

from rich.console import Console

console = Console()




def versioned_file(filepath: str, backup_dir: Optional[str] = None, extension: Optional[str] = None) -> str:
    """Version files with numbered backups.

    Args:
        filepath: Path to the file to version
        backup_dir: Directory for backups (defaults to file's directory)
        extension: Override extension for backup files (defaults to original extension)
    """
    base_dir = os.path.dirname(filepath)
    filename, file_ext = os.path.splitext(os.path.basename(filepath))

    backup_dir = backup_dir or base_dir
    backup_ext = extension or file_ext

    os.makedirs(backup_dir, exist_ok=True)

    backup_pattern = re.compile(f'{filename}\\.~(\\d+)~\\.{backup_ext}')
    versions = [
        int(match.group(1))
        for match in (backup_pattern.match(f) for f in os.listdir(backup_dir))
        if match
    ]

    for version in sorted(versions, reverse=True):
        old_file = f'{backup_dir}/{filename}.~{version:02d}~{backup_ext}'
        new_file = f'{backup_dir}/{filename}.~{version + 1:02d}~{backup_ext}'
        os.rename(old_file, new_file)

    target_file = f'{backup_dir}/{filename}{backup_ext}'
    if os.path.exists(target_file):
        os.rename(target_file, f'{backup_dir}/{filename}.~01~{backup_ext}')

    return target_file
