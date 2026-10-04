# file_manager.py

import os
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton

class FileManagerComponent(QObject):
    def __init__(self, parent_window):
        super().__init__()
        self.parent = parent_window
        self.file_data_list = []
        self.worker = None

    def clear_all(self):
        self.file_data_list.clear()
        self.refresh_ui()
        if hasattr(self.parent, "sync_pictures_from_files"):
            self.parent.sync_pictures_from_files()
        elif hasattr(self.parent, "clear_all_pictures"):
            self.parent.clear_all_pictures()
        self.parent.update_progress()

    def add_paths(self, paths: list[str]):
        # Display loading state immediately on the UI thread
        self.parent.summary_label.setText("(Loading files...)")
        self.parent.file_list_card.setVisible(True)

        # Launch the background thread worker to prevent UI freezing
        self.worker = FileScanWorker(paths)
        self.worker.finished.connect(self.on_scan_finished)
        self.worker.start()

    def on_scan_finished(self, scanned_file_data_list: list):
        existing_paths = {item["display_path"] for item in self.file_data_list}

        for item in scanned_file_data_list:
            if item["display_path"] not in existing_paths:
                self.file_data_list.append(item)
                existing_paths.add(item["display_path"])

        self.refresh_ui()
        if hasattr(self.parent, "sync_pictures_from_files"):
            self.parent.sync_pictures_from_files()
        self.parent.update_progress()

    def remove_file(self, display_path: str):
        self.file_data_list = [
            item for item in self.file_data_list if item["display_path"] != display_path
        ]
        self.refresh_ui()
        if hasattr(self.parent, "sync_pictures_from_files"):
            self.parent.sync_pictures_from_files()
        self.parent.update_progress()

    def refresh_ui(self):
        while self.parent.file_items_layout.count():
            item = self.parent.file_items_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

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

        calculated_height = (total_files * 28) + 10
        final_height = max(36, min(calculated_height, 250))
        self.parent.file_scroll.setFixedHeight(final_height)

        for item in self.file_data_list:
            disp_path = item["display_path"]
            file_size = item["size"]

            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(4, 2, 4, 2)

            path_lbl = QLabel(disp_path)
            path_lbl.setStyleSheet("color: #9aa1b1; font-size: 11px; font-family: Consolas, monospace;")

            size_lbl = QLabel(self.format_bytes(file_size))
            size_lbl.setStyleSheet("color: #7b8394; font-size: 11px; font-family: Consolas, monospace;")

            remove_btn = QPushButton("×")
            remove_btn.setFixedSize(18, 18)
            remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            remove_btn.setStyleSheet("""
                QPushButton { background: transparent; color: #7b8394; font-weight: bold; border: none; font-size: 14px; }
                QPushButton:hover { color: #ef4444; }
            """)
            remove_btn.clicked.connect(lambda checked, dp=disp_path: self.remove_file(dp))

            row_layout.addWidget(path_lbl)
            row_layout.addStretch()
            row_layout.addWidget(size_lbl)
            row_layout.addWidget(remove_btn)

            self.parent.file_items_layout.addWidget(row_widget)

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
                    key=lambda x: (x["display_path"].count(os.sep), x["display_path"]), 
                    reverse=True
                )
                file_data_list.extend(folder_items)

        self.finished.emit(file_data_list)