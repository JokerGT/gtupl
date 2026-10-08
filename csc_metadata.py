import os
import json
import hashlib
from typing import Optional, Dict, Any

from PIL import Image
from PIL.PngImagePlugin import PngInfo


class CSCMetadataManager:
    """Stores CSC fingerprint directly in the generated output image metadata."""

    def __init__(self):
        pass

    @staticmethod
    def _relevant_settings_for_fingerprint(settings: Dict[str, Any]) -> Dict[str, Any]:
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
        """Compute a deterministic fingerprint from the source file and current CSC settings."""
        try:
            stat = os.stat(file_path)
        except OSError:
            return None

        payload = {
            "source_path": os.path.abspath(file_path),
            "source_size": stat.st_size,
            "source_mtime_ns": stat.st_mtime_ns,
            "settings": self._relevant_settings_for_fingerprint(settings),
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def _decode_exif_user_comment(value) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, bytes):
            try:
                return value.decode("utf-8", errors="strict")
            except UnicodeDecodeError:
                try:
                    return value.decode("latin-1", errors="strict")
                except Exception:
                    return None
        if isinstance(value, str):
            return value
        return None

    def write_output_fingerprint(self, source_file: str, output_path: str, settings: Dict[str, Any]) -> bool:
        """Embed the fingerprint into the generated output image file itself."""
        fingerprint = self.compute_fingerprint(source_file, settings)
        if fingerprint is None:
            return False

        payload = {
            "source_path": os.path.abspath(source_file),
            "fingerprint": fingerprint,
            "version": 1,
        }
        serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))

        try:
            with Image.open(output_path) as img:
                extension = os.path.splitext(output_path)[1].lower()

                if extension == ".png":
                    pnginfo = PngInfo()
                    pnginfo.add_text("gtupl_csc", serialized)
                    img.save(output_path, pnginfo=pnginfo)
                    return True

                exif = img.getexif()
                exif[0x9286] = serialized.encode("utf-8")
                img.save(output_path, exif=exif)
                return True
        except Exception:
            try:
                with Image.open(output_path) as img:
                    img.info["comment"] = serialized
                    img.save(output_path)
                return True
            except Exception:
                return False

    def read_output_fingerprint(self, output_path: str) -> Optional[str]:
        """Read the embedded fingerprint from an output image file."""
        if not os.path.exists(output_path):
            return None

        try:
            with Image.open(output_path) as img:
                extension = os.path.splitext(output_path)[1].lower()

                if extension == ".png":
                    raw = img.info.get("gtupl_csc")
                    if raw is None:
                        return None
                    try:
                        obj = json.loads(raw)
                        return obj.get("fingerprint")
                    except Exception:
                        return None

                exif = img.getexif()
                if exif:
                    raw = exif.get(0x9286)
                    value = self._decode_exif_user_comment(raw)
                    if value is None:
                        raw = img.info.get("comment")
                        value = self._decode_exif_user_comment(raw)
                    if value is None:
                        return None
                    try:
                        obj = json.loads(value)
                        return obj.get("fingerprint")
                    except Exception:
                        return None

                raw = img.info.get("comment")
                if raw is None:
                    return None
                try:
                    obj = json.loads(raw)
                    return obj.get("fingerprint")
                except Exception:
                    return None
        except Exception:
            return None

    def is_output_valid(self, source_file: str, output_path: str, settings: Dict[str, Any]) -> tuple[bool, str]:
        """Check whether the existing output file is valid for the current source and CSC settings."""
        if not os.path.exists(output_path):
            return False, "missing_output"

        expected = self.compute_fingerprint(source_file, settings)
        if expected is None:
            return False, "source_unreadable"

        actual = self.read_output_fingerprint(output_path)
        if actual is None:
            return False, "missing_metadata"

        if actual != expected:
            return False, "fingerprint_mismatch"

        return True, "valid"

    def clear_all_metadata(self) -> bool:
        """No-op for in-file metadata. Kept for compatibility with the existing app logic."""
        return True

    def cleanup(self) -> None:
        """No-op for in-file metadata. Kept for compatibility with the existing app logic."""
        return None


_metadata_manager: Optional[CSCMetadataManager] = None


def get_metadata_manager() -> CSCMetadataManager:
    global _metadata_manager
    if _metadata_manager is None:
        _metadata_manager = CSCMetadataManager()
    return _metadata_manager
