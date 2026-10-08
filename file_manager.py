import os
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject, QAbstractListModel, QModelIndex
from PyQt6.QtWidgets import QListView

from csc_metadata import get_metadata_manager

class FileListModel(QAbstractListModel):
    def __init__(self, file_data_list):
        super().__init__()
        self.file_data = file_data_list

    def rowCount(self, parent=QModelIndex()):
        if parent.isValid():
            return 0
        return len(self.file_data)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        item = self.file_data[index.row()]

        if role == Qt.ItemDataRole.DisplayRole:
            return f"{item['display_path']}  ({self.format_bytes(item['size'])})"

        if role == Qt.ItemDataRole.ToolTipRole:
            return item["full_path"]

        return None

    def update_data(self, new_file_data):
        self.beginResetModel()
        self.file_data = new_file_data
        self.endResetModel()

    @staticmethod
    def format_bytes(size: int) -> str:
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024.0:
                return f"{size:.1f} {unit}" if unit != "B" else f"{size} B"
            size /= 1024.0
        return f"{size:.1f} PB"


class FileManagerComponent(QObject):
    def __init__(self, parent_window):
        super().__init__()
        self.parent = parent_window
        self.file_data_list = []
        self.worker = None
        self.list_model = None

    @staticmethod
    def sort_key(item):
        display = item["display_path"]
        depth = display.count(os.sep)
        return (-depth, display.lower())

    def clear_all(self):
        self.file_data_list.clear()
        if self.list_model:
            self.list_model.update_data([])
        self.refresh_ui()
        if hasattr(self.parent, "sync_pictures_from_files"):
            self.parent.sync_pictures_from_files()
        if hasattr(self.parent, "clear_torrent_derived_pictures"):
            self.parent.clear_torrent_derived_pictures()
        if hasattr(self.parent, "update_torrent_video_button_visibility"):
            self.parent.update_torrent_video_button_visibility()
        get_metadata_manager().clear_all_metadata()
        self.parent.update_progress()

    def add_paths(self, paths: list[str]):
        self.parent.summary_label.setText("(Loading files...)")
        self.parent.file_list_card.setVisible(True)
        self.worker = FileScanWorker(paths)
        self.worker.finished.connect(self.on_scan_finished)
        self.worker.start()

    def on_scan_finished(self, scanned_file_data_list: list):
        existing_paths = {item["display_path"] for item in self.file_data_list}

        for item in scanned_file_data_list:
            if item["display_path"] not in existing_paths:
                self.file_data_list.append(item)
                existing_paths.add(item["display_path"])

        self.file_data_list.sort(key=self.sort_key)

        if self.list_model:
            self.list_model.update_data(self.file_data_list)

        self.refresh_ui()
        if hasattr(self.parent, "sync_pictures_from_files"):
            self.parent.sync_pictures_from_files()
        if hasattr(self.parent, "update_torrent_video_button_visibility"):
            self.parent.update_torrent_video_button_visibility()

        self.parent.update_progress()

    def refresh_ui(self):
        if not self.file_data_list:
            self.parent.file_list_card.setVisible(False)
            self.parent.btn_clear.setVisible(False)
            return

        self.parent.file_list_card.setVisible(True)
        self.parent.btn_clear.setVisible(True)

        total_files = len(self.file_data_list)
        total_size_bytes = sum(item["size"] for item in self.file_data_list)
        self.parent.summary_label.setText(
            f"({total_files} · {self.format_bytes(total_size_bytes)})"
        )

    @staticmethod
    def format_bytes(size: int) -> str:
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024.0:
                return f"{size:.1f} {unit}" if unit != "B" else f"{size} B"
            size /= 1024.0
        return f"{size:.1f} PB"


class FileScanWorker(QThread):
    finished = pyqtSignal(list)

    def __init__(self, paths):
        super().__init__()
        self.paths = paths

    def run(self):
        file_data_list = []
        existing_paths = set()

        for path in self.paths:
            if os.path.isfile(path):
                file_name = os.path.basename(path)
                if file_name not in existing_paths:
                    try:
                        file_data_list.append({
                            "full_path": path,
                            "display_path": file_name,
                            "size": os.path.getsize(path),
                        })
                        existing_paths.add(file_name)
                    except OSError:
                        pass

            elif os.path.isdir(path):
                folder_items = []
                for root, _, files in os.walk(path):
                    for file in files:
                        full_path = os.path.join(root, file)
                        rel_path = os.path.relpath(full_path, start=path)

                        if rel_path not in existing_paths:
                            try:
                                folder_items.append({
                                    "full_path": full_path,
                                    "display_path": rel_path,
                                    "size": os.path.getsize(full_path),
                                })
                                existing_paths.add(rel_path)
                            except OSError:
                                pass

                folder_items.sort(
                    key=lambda x: (-x["display_path"].count(os.sep), x["display_path"].lower())
                )
                file_data_list.extend(folder_items)

        self.finished.emit(file_data_list)
