#!/usr/bin/env python3
"""
Atomic File Operations with Backup

Per Council Decree (Diamond Debate 2026-02-07):
All file writes MUST use atomic operations with backup before every change.

This module provides:
- Safe YAML reading with error handling
- Atomic writes using temp file + rename
- Automatic backups before modifications
- Validated rollback (only to known-good states)
"""

import yaml
import shutil
import tempfile
import os
from pathlib import Path
from datetime import datetime
from typing import Tuple, Optional, List

from config_validator import config_validator, ValidationResult


class ConfigFileManager:
    """
    Safe file operations with atomic writes and backup.

    Every write operation:
    1. Validates the path (whitelist only)
    2. Creates backup of existing file
    3. Writes to temp file
    4. Validates new content
    5. Atomic rename to final location
    """

    BACKUP_DIR = Path(__file__).parent.parent / "backups"
    MAX_BACKUPS = 10

    def __init__(self):
        """Initialize file manager and create backup directory."""
        self.BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    def read_config(self, config_type: str) -> Tuple[bool, dict, str]:
        """
        Safely read a configuration file.

        Args:
            config_type: Type of config ('litellm' or 'council')

        Returns:
            (success, data_dict, error_message)
        """
        # Validate path first (prevents traversal)
        valid, path = config_validator.validate_path(config_type)
        if not valid:
            return False, {}, f"Invalid config type: {config_type}"

        if not path.exists():
            # File doesn't exist - return empty config
            return True, {}, ""

        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
            return True, data, ""
        except yaml.YAMLError as e:
            return False, {}, f"YAML parse error: {e}"
        except Exception as e:
            return False, {}, f"Read error: {e}"

    def write_config(self, config_type: str, data: dict, validate: bool = True) -> Tuple[bool, str]:
        """
        Safely write configuration with atomic operation and backup.

        Args:
            config_type: Type of config ('litellm' or 'council')
            data: Configuration data to write
            validate: Whether to validate before writing (default: True)

        Returns:
            (success, error_message)
        """
        # Validate path first
        valid, path = config_validator.validate_path(config_type)
        if not valid:
            return False, f"Invalid config type: {config_type}"

        # Validate config data before writing
        if validate:
            validation = config_validator.validate_config(config_type, data)
            if not validation.valid:
                return False, f"Config validation failed: {'; '.join(validation.errors)}"

        # Create backup first if file exists
        if path.exists():
            backup_path = self._create_backup(config_type, path)
            if not backup_path:
                return False, "Failed to create backup"

        # Atomic write using temp file
        try:
            # Write to temp file in same directory (for atomic rename)
            fd, temp_path = tempfile.mkstemp(
                dir=path.parent,
                prefix=f'.{path.stem}_',
                suffix='.tmp'
            )

            try:
                with os.fdopen(fd, 'w', encoding='utf-8') as f:
                    yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

                # Atomic rename (overwrites target if exists)
                os.replace(temp_path, path)
                return True, ""

            except Exception as e:
                # Clean up temp file on error
                if os.path.exists(temp_path):
                    try:
                        os.unlink(temp_path)
                    except:
                        pass
                raise e

        except Exception as e:
            return False, f"Write error: {e}"

    def _create_backup(self, config_type: str, source_path: Path) -> Optional[Path]:
        """
        Create timestamped backup of config file.

        Args:
            config_type: Type of config ('litellm' or 'council')
            source_path: Path to file to backup

        Returns:
            Path to backup file, or None if failed
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_name = f"{config_type}_{timestamp}.yaml"
        backup_path = self.BACKUP_DIR / backup_name

        try:
            shutil.copy2(source_path, backup_path)
            self._cleanup_old_backups(config_type)
            return backup_path
        except Exception:
            return None

    def _cleanup_old_backups(self, config_type: str):
        """
        Keep only the most recent backups for a config type.

        Args:
            config_type: Type of config ('litellm' or 'council')
        """
        backups = sorted(
            self.BACKUP_DIR.glob(f"{config_type}_*.yaml"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )

        # Remove old backups beyond MAX_BACKUPS
        for old_backup in backups[self.MAX_BACKUPS:]:
            try:
                old_backup.unlink()
            except Exception:
                pass

    def list_backups(self, config_type: str) -> List[dict]:
        """
        List available backups for rollback.

        Args:
            config_type: Type of config ('litellm' or 'council')

        Returns:
            List of backup info dicts
        """
        backups = []

        for backup_path in sorted(
            self.BACKUP_DIR.glob(f"{config_type}_*.yaml"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        ):
            try:
                stat = backup_path.stat()
                backups.append({
                    'filename': backup_path.name,
                    'timestamp': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    'size': stat.st_size
                })
            except Exception:
                continue

        return backups[:self.MAX_BACKUPS]

    def restore_backup(self, config_type: str, backup_filename: str, validate: bool = True) -> Tuple[bool, str]:
        """
        Restore a specific backup after validation.

        Args:
            config_type: Type of config ('litellm' or 'council')
            backup_filename: Name of backup file to restore
            validate: Whether to validate backup content before restoring

        Returns:
            (success, error_message)
        """
        # Validate backup filename (prevent path traversal)
        if '/' in backup_filename or '\\' in backup_filename:
            return False, "Invalid backup filename"

        if not backup_filename.startswith(f"{config_type}_"):
            return False, "Backup does not match config type"

        backup_path = self.BACKUP_DIR / backup_filename
        if not backup_path.exists():
            return False, "Backup not found"

        # Read and validate backup content before restoring
        try:
            with open(backup_path, 'r', encoding='utf-8') as f:
                backup_data = yaml.safe_load(f) or {}

            # Validate backup content
            if validate:
                validation = config_validator.validate_config(config_type, backup_data)
                if not validation.valid:
                    return False, f"Backup validation failed: {'; '.join(validation.errors)}"

            # Get target path
            valid, target_path = config_validator.validate_path(config_type)
            if not valid:
                return False, f"Invalid config type: {config_type}"

            # Create backup of current state before restoring
            if target_path.exists():
                self._create_backup(config_type, target_path)

            # Copy backup to target location
            shutil.copy2(backup_path, target_path)
            return True, ""

        except yaml.YAMLError as e:
            return False, f"YAML parse error in backup: {e}"
        except Exception as e:
            return False, f"Restore error: {e}"


# Singleton instance
config_file_manager = ConfigFileManager()


if __name__ == "__main__":
    # Test the file manager
    print("Testing ConfigFileManager...")

    # Test reading
    success, data, error = config_file_manager.read_config('litellm')
    print(f"Read litellm config: {success}")
    if success:
        print(f"  Models: {len(data.get('model_list', []))} found")
    else:
        print(f"  Error: {error}")

    # Test backups
    backups = config_file_manager.list_backups('litellm')
    print(f"Backups: {len(backups)} found")
    for backup in backups[:3]:
        print(f"  - {backup['filename']}")
