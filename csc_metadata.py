"""
CSC Metadata Manager

Stores contact sheet generation fingerprints and metadata in a temporary directory.
Metadata is keyed by source video file path and includes:
  - fingerprint (hash of source file stats + CSC settings)
  - source file size and mtime
  - output paths that were generated
  - timestamp of generation

Metadata is cleared when:
  - The content file list is cleared
  - The application closes
"""

import os
import sys
import json
import hashlib
import tempfile
import shutil
from pathlib import Path
from typing import Optional, Dict, Any


class CSCMetadataManager:
    """Manages contact sheet generation metadata."""

    def __init__(self):
        """Initialize metadata manager with a temp directory."""
        self.temp_dir = self._init_temp_dir()
        self.metadata_cache = {}  # In-memory cache for quick lookups

    def _init_temp_dir(self) -> str:
        """Create and return the metadata temp directory."""
        if getattr(sys, "frozen", False):
            app_dir = os.path.dirname(sys.executable)
        else:
            app_dir = os.path.dirname(os.path.abspath(__file__))

        temp_base = os.path.join(app_dir, ".gtupl_csc_metadata")
        os.makedirs(temp_base, exist_ok=True)
        return temp_base

    def _get_source_key(self, file_path: str) -> str:
        """Generate a unique key for a source video file."""
        abs_path = os.path.abspath(file_path)
        return hashlib.md5(abs_path.encode()).hexdigest()

    def _get_metadata_path(self, file_path: str) -> str:
        """Get the path to the metadata file for a given source."""
        key = self._get_source_key(file_path)
        return os.path.join(self.temp_dir, f"{key}.json")

    def _relevant_settings_for_fingerprint(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        """Extract only the CSC settings that affect output."""
        return {
            "x_tiles": int(settings.get("x_tiles", 5)),
            "y_tiles": int(settings.get("y_tiles", 4)),
            "tile_size": int(settings.get("tile_size", 512)),
            "auto_size": bool(settings.get("auto_size", True)),
            "orig_size": bool(settings.get("orig_size", False)),
            "ignore_first": int(settings.get("ignore_first", 0)),
            "ignore_last": int(settings.get("ignore_last", 0)),
            "stamp_details": bool(settings.get("stamp_details", True)),
            "show_filename": bool(settings.get("show_filename", True)),
            "show_size": bool(settings.get("show_size", True)),
            "show_res": bool(settings.get("show_res", True)),
            "show_fps": bool(settings.get("show_fps", True)),
            "show_duration": bool(settings.get("show_duration", True)),
            "format": str(settings.get("format", "JPEG")).upper(),
            "quality": int(settings.get("quality", 65)),
            "save_frames": bool(settings.get("save_frames", False)),
            "save_subfolder": bool(settings.get("save_subfolder", True)),
        }

    def compute_fingerprint(self, file_path: str, settings: Dict[str, Any]) -> Optional[str]:
        """
        Compute a fingerprint for a source video given the current CSC settings.
        
        Returns:
            SHA256 hex digest or None if source file is unreadable.
        """
        try:
            stat = os.stat(file_path)
        except OSError as e:
            print(f"[CSC Metadata] Error accessing {file_path}: {e}")
            return None

        payload = {
            "source_path": os.path.abspath(file_path),
            "source_size": stat.st_size,
            "source_mtime_ns": stat.st_mtime_ns,
            "settings": self._relevant_settings_for_fingerprint(settings),
        }

        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def write_metadata(
        self, file_path: str, settings: Dict[str, Any], output_paths: list
    ) -> bool:
        """
        Write metadata for a source file after successful generation.
        
        Args:
            file_path: Path to the source video file
            settings: Current CSC settings dict
            output_paths: List of generated output file paths
        
        Returns:
            True if successful, False otherwise.
        """
        fingerprint = self.compute_fingerprint(file_path, settings)
        if fingerprint is None:
            return False

        meta_path = self._get_metadata_path(file_path)
        payload = {
            "source_path": os.path.abspath(file_path),
            "fingerprint": fingerprint,
            "output_paths": [os.path.abspath(p) for p in output_paths],
            "generated_at": int(__import__("time").time()),
        }

        try:
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, sort_keys=True, indent=2)
            # Update in-memory cache
            self.metadata_cache[self._get_source_key(file_path)] = payload
            return True
        except OSError as e:
            print(f"[CSC Metadata] Error writing metadata for {file_path}: {e}")
            return False

    def read_metadata(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Read metadata for a source file.
        
        Returns:
            Metadata dict or None if file does not exist or is invalid.
        """
        key = self._get_source_key(file_path)

        # Check cache first
        if key in self.metadata_cache:
            return self.metadata_cache[key]

        meta_path = self._get_metadata_path(file_path)
        if not os.path.exists(meta_path):
            return None

        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Validate structure
            if isinstance(data, dict) and "fingerprint" in data:
                self.metadata_cache[key] = data
                return data
        except (OSError, json.JSONDecodeError, ValueError) as e:
            print(f"[CSC Metadata] Error reading metadata for {file_path}: {e}")
            return None

        return None

    def is_output_valid(self, file_path: str, settings: Dict[str, Any]) -> tuple[bool, str]:
        """
        Check if a previously generated output is still valid for the current settings.
        
        Returns:
            (is_valid, reason_if_invalid)
            Reasons: "missing_metadata", "source_unreadable", "fingerprint_mismatch", "valid"
        """
        meta = self.read_metadata(file_path)
        if not meta:
            return False, "missing_metadata"

        fingerprint = self.compute_fingerprint(file_path, settings)
        if fingerprint is None:
            return False, "source_unreadable"

        if meta.get("fingerprint") != fingerprint:
            return False, "fingerprint_mismatch"

        return True, "valid"

    def clear_metadata_for_file(self, file_path: str) -> bool:
        """
        Delete metadata for a specific source file.
        
        Returns:
            True if successful or file did not exist, False on error.
        """
        meta_path = self._get_metadata_path(file_path)
        key = self._get_source_key(file_path)

        try:
            if os.path.exists(meta_path):
                os.remove(meta_path)
            if key in self.metadata_cache:
                del self.metadata_cache[key]
            return True
        except OSError as e:
            print(f"[CSC Metadata] Error clearing metadata for {file_path}: {e}")
            return False

    def clear_all_metadata(self) -> bool:
        """
        Clear all metadata in the temp directory.
        Called when the content file list is cleared or app closes.
        
        Returns:
            True if successful, False on error.
        """
        try:
            if os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
                os.makedirs(self.temp_dir, exist_ok=True)
            self.metadata_cache.clear()
            print("[CSC Metadata] All metadata cleared.")
            return True
        except OSError as e:
            print(f"[CSC Metadata] Error clearing all metadata: {e}")
            return False

    def cleanup(self) -> None:
        """
        Final cleanup when app closes.
        Removes the temp directory entirely.
        """
        try:
            if os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
            print("[CSC Metadata] Temp directory cleaned up.")
        except OSError as e:
            print(f"[CSC Metadata] Error cleaning up temp directory: {e}")


# Global singleton instance
_metadata_manager: Optional[CSCMetadataManager] = None


def get_metadata_manager() -> CSCMetadataManager:
    """Get the global metadata manager instance."""
    global _metadata_manager
    if _metadata_manager is None:
        _metadata_manager = CSCMetadataManager()
    return _metadata_manager
