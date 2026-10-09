import sys
import multiprocessing
import os
import traceback
from PyQt6.QtCore import QSize, Qt, QTimer, QThread, QObject, QEvent, QByteArray
from PyQt6.QtGui import QIcon, QFont, QPixmap
from PyQt6.QtWidgets import (
    QApplication, QDialog, QGridLayout, QFileDialog, QFrame, QHBoxLayout,
    QLabel, QLineEdit, QListView, QMainWindow, QPushButton, QProgressBar,
    QScrollArea, QSizePolicy, QVBoxLayout, QWidget, QMessageBox
)
import qtawesome as qta

from constants import CATEGORIES, SPECIAL_CATS
from widgets import (
    CategoryDropdown,
    MultiCategoryDropdown,
    DragDropArea,
    DraggablePictureTile,
    PicturesContainerWidget,
)

from styles import GLOBAL_STYLESHEET, apply_input_style
from file_manager import FileManagerComponent
from editor_panel import EditorPanelComponent
from sidebar import SidebarPanelComponent
from csc import PreviewWorker, ProcessingWorker
from pipeline_worker import TorrentPipelineWorker
from dialogs import ContactSheetPreviewDialog
from history import HistoryPanelComponent
from datetime import datetime
import tempfile
import shutil

import ctypes
import base64
import io
from assets import ASSETS
from csc_metadata import get_metadata_manager
from torrent_pictures_dialog import AddFromTorrentDialog, TorrentPicturesProcessingWorker, VALID_VIDEO_EXTENSIONS


def get_asset_bytes(relative_path):
    clean_path = relative_path.replace("assets/", "").replace("assets\\", "")

    if clean_path not in ASSETS:
        raise FileNotFoundError(f"Asset '{relative_path}' not found in assets.py")

    return base64.b64decode(ASSETS[clean_path])


def get_asset_stream(relative_path):
    return io.BytesIO(get_asset_bytes(relative_path))


class Tee:
    def __init__(self, log_dir="logs", max_files=15):
        from paths import data_dir
        logs_path = os.path.join(data_dir(), log_dir)
        os.makedirs(logs_path, exist_ok=True)

        self._cleanup_old_logs(logs_path, max_files)

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        log_filename = f"gtupl_{timestamp}.log"
        log_filepath = os.path.join(logs_path, log_filename)

        self.terminal = sys.stdout
        self.log = open(log_filepath, "w", encoding="utf-8")

    def _cleanup_old_logs(self, logs_path, max_files):
        try:
            log_files = [
                os.path.join(logs_path, f) for f in os.listdir(logs_path)
                if f.startswith("gtupl_") and f.endswith(".log")
            ]
            log_files.sort(key=os.path.getmtime)

            while len(log_files) >= max_files:
                oldest_file = log_files.pop(0)
                os.remove(oldest_file)
        except Exception:
            pass

    def write(self, message):
        self.terminal.write(message)
        self.terminal.flush()
        self.log.write(message)
        self.log.flush()

    def flush(self):
        self.terminal.flush()
        self.log.flush()


class ImageDropFilter(QObject):
    def __init__(self, parent_app):
        super().__init__()
        self.parent_app = parent_app

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.DragEnter or event.type() == QEvent.Type.DragMove:
            if event.mimeData().hasUrls():
                event.acceptProposedAction()
                return True
        elif event.type() == QEvent.Type.Drop:
            if event.mimeData().hasUrls():
                paths = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
                image_paths = [p for p in paths if self.parent_app.is_image_file(p)]
                if image_paths:
                    self.parent_app.add_pictures(image_paths)
                    event.acceptProposedAction()
                    return True
        return super().eventFilter(obj, event)


class DarkFormApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GayTorrent Uploader")

        screen_geometry = QApplication.primaryScreen().availableGeometry()

        target_width = int(screen_geometry.width() * 0.8)
        target_height = int(screen_geometry.height() * 0.9)

        self.resize(target_width, target_height)
        self.setMinimumWidth(1100)
        self.setMinimumHeight(750)

        x = (screen_geometry.width() - target_width) // 2
        y = (screen_geometry.height() - target_height) // 2
        self.move(x, y)

        self.selected_folder_path = None
        self.picture_data_list = []
        self.auto_synced_pictures = set()
        self.pixmap_cache = {}
        self.generated_contact_sheets = []
        self._last_validation_errors = []

        # Initialize file manager here before using it
        self.file_manager = FileManagerComponent(self)
        self.setStyleSheet(GLOBAL_STYLESHEET)

        central_widget = QWidget()
        root_layout = QHBoxLayout(central_widget)
        root_layout.setContentsMargins(15, 15, 15, 15)
        root_layout.setSpacing(15)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("border: none; background: transparent;")

        container = QWidget()
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(10)

        left_column_layout = QVBoxLayout()
        left_column_layout.setContentsMargins(0, 0, 0, 0)
        left_column_layout.setSpacing(10)

        cloud_upload_icon = qta.icon("fa6s.upload", color="#ffffff")
        header_title = QLabel(" Upload a torrent")
        header_title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        header_title.setStyleSheet("color: #ffffff;")

        title_box = QHBoxLayout()
        icon_lbl = QLabel()
        icon_lbl.setPixmap(cloud_upload_icon.pixmap(QSize(22, 22)))
        title_box.addWidget(icon_lbl)
        title_box.addWidget(header_title)
        title_box.addStretch()

        check_icon = qta.icon("fa6s.check", color="#22c55e")
        self.header_status = QLabel(" 0 of 5 required fields done")
        self.header_status.setFont(QFont("Arial", 10))
        self.header_status.setStyleSheet("color: #7b8394;")

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 5)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.progress_bar.setStyleSheet("""
            QProgressBar { background-color: #343840; border-radius: 4px; }
            QProgressBar::chunk { background-color: #79d279; border-radius: 3px; }
        """)

        status_box = QHBoxLayout()
        self.check_lbl = QLabel()
        self.check_lbl.setPixmap(check_icon.pixmap(QSize(14, 14)))
        self.check_lbl.setVisible(False)

        status_box.addWidget(self.check_lbl)
        status_box.addWidget(self.header_status)
        status_box.addWidget(self.progress_bar)

        header_vbox = QVBoxLayout()
        header_vbox.setContentsMargins(10, 10, 10, 10)
        header_vbox.setSpacing(8)
        header_vbox.addLayout(title_box)
        header_vbox.addLayout(status_box)

        header_frame = QFrame()
        header_frame.setLayout(header_vbox)
        header_frame.setStyleSheet("background-color: #1e222b; border-radius: 6px;")

        left_column_layout.addWidget(header_frame)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("border: none; background: transparent;")

        container = QWidget()
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(10)

        cat_box = self.create_card("Category", icon_name="fa6s.folder-open")
        cat_layout = QVBoxLayout()

        cat_layout.addWidget(QLabel("Main category", styleSheet="color: #9aa1b1; font-size: 11px;"))
        self.main_cat_combo = CategoryDropdown(CATEGORIES, "Select category...", special_cats=SPECIAL_CATS)
        cat_layout.addWidget(self.main_cat_combo)

        cat_layout.addWidget(QLabel("Subcategories (up to 4)", styleSheet="color: #9aa1b1; font-size: 11px; margin-top: 6px;"))
        self.sub_cat_combo = MultiCategoryDropdown(CATEGORIES, "Select category...", special_cats=SPECIAL_CATS)
        cat_layout.addWidget(self.sub_cat_combo)

        def on_main_category_changed():
            if self.main_cat_combo.selected_id in self.sub_cat_combo.selected_items:
                del self.sub_cat_combo.selected_items[self.main_cat_combo.selected_id]
                self.sub_cat_combo.update_display_text()
            self.update_progress()

        self.main_cat_combo.on_selection_changed = on_main_category_changed
        self.main_cat_combo.get_excluded_id = lambda: (
            list(self.sub_cat_combo.selected_items.keys())[0]
            if len(self.sub_cat_combo.selected_items) == 1 else None
        )
        self.sub_cat_combo.get_excluded_id = lambda: self.main_cat_combo.selected_id

        cat_box.layout().addLayout(cat_layout)
        main_layout.addWidget(cat_box)

        files_box = self.create_card("Files", icon_name="fa6s.cloud-arrow-up")
        files_layout = QVBoxLayout()

        self.drop_zone = DragDropArea(self.handle_dropped_paths)
        self.drop_zone.reset_style()

        drop_layout = QVBoxLayout(self.drop_zone)
        drop_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        cloud_big_icon = QLabel()
        cloud_big_icon.setPixmap(qta.icon("fa6s.cloud-arrow-up", color="#7b8394").pixmap(QSize(64, 48)))
        cloud_big_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

        drop_label = QLabel("Drop a file or folder here as part of the torrent content.")
        drop_label.setStyleSheet("color: #7b8394; font-size: 12px;")
        drop_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        drop_layout.addWidget(cloud_big_icon)
        drop_layout.addWidget(drop_label)
        files_layout.addWidget(self.drop_zone)

        btn_row = QHBoxLayout()
        btn_row.setAlignment(Qt.AlignmentFlag.AlignRight)

        self.btn_clear = QPushButton(" Clear list")
        self.btn_clear.setIcon(qta.icon("fa6s.trash-can", color="#ef4444"))
        self.btn_clear.setStyleSheet("""
            QPushButton { background-color: #1e222b; border: 1px solid #ef4444; color: #ef4444; border-radius: 4px; padding: 6px 12px; }
            QPushButton:hover { background-color: #3b1d24; }
        """)
        self.btn_clear.clicked.connect(self.file_manager.clear_all)
        self.btn_clear.setVisible(False)

        self.btn_file = QPushButton(" Pick files")
        self.btn_file.setIcon(qta.icon("fa6s.file-lines", color="#d0d4dc"))
        self.btn_file.clicked.connect(self.browse_files)

        self.btn_folder = QPushButton(" Pick a folder")
        self.btn_folder.setIcon(qta.icon("fa6s.folder-open", color="#d0d4dc"))
        self.btn_folder.clicked.connect(self.browse_folder)

        btn_row.addWidget(self.btn_clear)
        for btn in (self.btn_file, self.btn_folder):
            btn.setStyleSheet("""
                QPushButton { background-color: #1e222b; border: 1px solid #3a4150; color: #d0d4dc; border-radius: 4px; padding: 6px 12px; }
                QPushButton:hover { background-color: #2a2f3d; }
            """)
            btn_row.addWidget(btn)

        files_layout.addLayout(btn_row)

        self.file_list_card = QFrame()
        self.file_list_card.setStyleSheet("""
            QFrame { background-color: #14161c; border: 1px solid #2a2f3a; border-radius: 6px; }
            QLabel { border: none; background: transparent; }
        """)
        preview_card_layout = QVBoxLayout(self.file_list_card)
        preview_card_layout.setContentsMargins(12, 10, 12, 10)

        list_header_layout = QHBoxLayout()
        list_icon = QLabel()
        list_icon.setPixmap(qta.icon("fa6s.list-check", color="#ffffff").pixmap(QSize(14, 14)))

        list_title = QLabel(" File list preview")
        list_title.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        list_title.setStyleSheet("color: #ffffff;")

        self.summary_label = QLabel("(0 · 0 B)")
        self.summary_label.setStyleSheet("color: #7b8394; font-size: 11px;")

        list_header_layout.addWidget(list_icon)
        list_header_layout.addWidget(list_title)
        list_header_layout.addStretch()
        list_header_layout.addWidget(self.summary_label)

        preview_card_layout.addLayout(list_header_layout)

        self.file_list_view = QListView()
        self.file_list_view.setStyleSheet("""
            QListView {
                border: none;
                background-color: #14161c;
                border: 1px solid #2a2f3a;
                border-radius: 6px;
            }
            QListView::item {
                color: #9aa1b1;
                font-size: 11px;
                font-family: Consolas, monospace;
                padding: 4px 8px;
                border-radius: 3px;
            }
            QListView::item:hover {
                background-color: #2a2f3a;
            }
            QListView::item:selected {
                background-color: #3a4150;
            }
        """)
        self.file_list_view.setUniformItemSizes(True)

        from file_manager import FileListModel
        self.file_list_model = FileListModel([])
        self.file_list_view.setModel(self.file_list_model)

        self.file_manager.list_model = self.file_list_model

        preview_card_layout.addWidget(self.file_list_view)

        self.file_list_card.setVisible(False)
        self.file_list_view.setFixedHeight(200)
        files_layout.addWidget(self.file_list_card)

        files_box.layout().addLayout(files_layout)
        main_layout.addWidget(files_box)

        pics_box = QFrame()
        pics_box.setStyleSheet("""
            QFrame { background-color: #1e222b; border: 1px solid #2a2f3a; border-radius: 6px; }
            QFrame QLabel { border: none; background: transparent; }
        """)
        pics_box_layout = QVBoxLayout(pics_box)
        pics_box_layout.setContentsMargins(15, 12, 15, 15)

        pics_header_row = QHBoxLayout()
        pics_header_row.setSpacing(8)

        pics_icon_lbl = QLabel()
        pics_icon_lbl.setPixmap(qta.icon("fa6s.images", color="#ffffff").pixmap(QSize(16, 16)))

        pics_title = QLabel(" Pictures")
        pics_title.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        pics_title.setStyleSheet("color: #ffffff;")

        self.pics_summary_label = QLabel("(0 images)")
        self.pics_summary_label.setStyleSheet("color: #7b8394; font-size: 11px;")

        pics_header_row.addWidget(pics_icon_lbl)
        pics_header_row.addWidget(pics_title)
        pics_header_row.addStretch()
        pics_header_row.addWidget(self.pics_summary_label)

        pics_box_layout.addLayout(pics_header_row)

        pics_layout = QVBoxLayout()

        self.pics_scroll = QScrollArea()
        self.pics_scroll.setWidgetResizable(True)
        self.pics_scroll.setFixedHeight(250)
        self.pics_scroll.setStyleSheet("""
            QScrollArea { background-color: #14161c; border: 1px solid #2a2f3a; border-radius: 6px; }
        """)

        self.pics_container = PicturesContainerWidget(self, self.reorder_pictures)
        self.pics_items_layout = QHBoxLayout(self.pics_container)
        self.pics_items_layout.setContentsMargins(2, 2, 2, 2)
        self.pics_items_layout.setSpacing(2)
        self.pics_items_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self.pics_scroll.setWidget(self.pics_container)

        self.last_browsed_dir = os.path.expanduser("~")

        self.pics_scroll.setAcceptDrops(True)
        self.pics_container.setAcceptDrops(True)
        self.image_drop_filter = ImageDropFilter(self)
        self.pics_scroll.installEventFilter(self.image_drop_filter)
        self.pics_container.installEventFilter(self.image_drop_filter)

        pics_layout.addWidget(self.pics_scroll)

        pics_btn_row = QHBoxLayout()
        pics_btn_row.setAlignment(Qt.AlignmentFlag.AlignRight)

        self.btn_clear_pics = QPushButton(" Clear pictures")
        self.btn_clear_pics.setIcon(qta.icon("fa6s.trash-can", color="#ef4444"))
        self.btn_clear_pics.setStyleSheet("""
            QPushButton { background-color: #1e222b; border: 1px solid #ef4444; color: #ef4444; border-radius: 4px; padding: 4px 4px; }
            QPushButton:hover { background-color: #3b1d24; }
        """)
        self.btn_clear_pics.clicked.connect(self.clear_all_pictures)
        self.btn_clear_pics.setVisible(False)

        self.torrent_derived_pictures = set()

        self.btn_add_from_torrent = QPushButton("Add from torrent files")
        self.btn_add_from_torrent.setIcon(qta.icon("fa6s.film", color="#d0d4dc"))
        self.btn_add_from_torrent.setStyleSheet("""
            QPushButton { background-color: #1e222b; border: 1px solid #3a4150; color: #d0d4dc; border-radius: 4px; padding: 6px 12px; }
            QPushButton:hover { background-color: #2a2f3d; }
        """)
        self.btn_add_from_torrent.clicked.connect(self.open_add_from_torrent_dialog)
        self.btn_add_from_torrent.setVisible(False)

        self.btn_add_pics = QPushButton(" Add pictures")
        self.btn_add_pics.setIcon(qta.icon("fa6s.image", color="#d0d4dc"))
        self.btn_add_pics.setStyleSheet("""
            QPushButton { background-color: #1e222b; border: 1px solid #3a4150; color: #d0d4dc; border-radius: 4px; padding: 6px 12px; }
            QPushButton:hover { background-color: #2a2f3d; }
        """)
        self.btn_add_pics.clicked.connect(self.browse_pictures)

        pics_btn_row.addWidget(self.btn_clear_pics)
        pics_btn_row.addWidget(self.btn_add_from_torrent)
        pics_btn_row.addWidget(self.btn_add_pics)
        pics_layout.addLayout(pics_btn_row)

        pics_box_layout.addLayout(pics_layout)
        main_layout.addWidget(pics_box)
        self.refresh_pictures_ui()

        title_card = self.create_card(" Title", icon_name="fa6s.font")
        title_layout = QVBoxLayout()

        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("Enter Torrent name here")
        apply_input_style(self.title_input)
        self.title_input.textChanged.connect(self.update_progress)
        title_layout.addWidget(self.title_input)
        title_layout.addWidget(QLabel("Please use descriptive names (at least 5 characters).", styleSheet="color: #7b8394; font-size: 11px;"))

        title_card.layout().addLayout(title_layout)
        main_layout.addWidget(title_card)

        desc_box = self.create_card(" Description", icon_name="fa6s.pen")
        self.editor_panel = EditorPanelComponent(self)
        desc_box.layout().addWidget(self.editor_panel)
        main_layout.addWidget(desc_box)

        scroll_area.setWidget(container)
        left_column_layout.addWidget(scroll_area)
        root_layout.addLayout(left_column_layout, stretch=3)

        self.is_processing = False
        self.is_generating_torrent_pics = False

        self.sidebar_panel = SidebarPanelComponent(self)
        self.history_panel = self.sidebar_panel.history_panel

        if hasattr(self.sidebar_panel, 'btn_start'):
            self.sidebar_panel.btn_start.clicked.connect(self.handle_start_button_clicked)

        root_layout.addWidget(self.sidebar_panel)

        self.setCentralWidget(central_widget)
        self.update_progress()

    def set_main_parameters_enabled(self, enabled: bool):
        self.main_cat_combo.setEnabled(enabled)
        self.sub_cat_combo.setEnabled(enabled)
        self.drop_zone.setEnabled(enabled)
        self.btn_clear.setEnabled(enabled)
        self.pics_scroll.setEnabled(enabled)
        if hasattr(self, 'btn_file'):
            self.btn_file.setEnabled(enabled)
        if hasattr(self, 'btn_folder'):
            self.btn_folder.setEnabled(enabled)

        self.title_input.setEnabled(enabled)

        self.btn_clear_pics.setEnabled(enabled)
        if hasattr(self, 'btn_add_pics'):
            self.btn_add_pics.setEnabled(enabled)

        self.editor_panel.setEnabled(enabled)

    def handle_start_button_clicked(self):
        if self.sidebar_panel.btn_start.text() == "Cancel":
            self.cancel_processing()
        else:
            self.start_processing_from_sidebar()

    def has_compressed_file(self) -> bool:
        compressed_extensions = (
            '.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz',
            '.iso', '.dmg', '.apk', '.pkg'
        )
        for item in self.file_manager.file_data_list:
            full_path = item.get("full_path", "").lower()
            for ext in compressed_extensions:
                if full_path.endswith(ext):
                    return True
        return False

    def has_executable_file(self) -> bool:
        executable_extensions = ('.exe', '.bat', '.cmd', '.com', '.scr', '.msi', '.app', '.deb', '.rpm', '.apk')
        for item in self.file_manager.file_data_list:
            full_path = item.get("full_path", "").lower()
            for ext in executable_extensions:
                if full_path.endswith(ext):
                    return True
        return False

    def has_media_programs_with_compressed(self) -> bool:
        media_programs_id = CATEGORIES.get("Media Programs")

        if media_programs_id is None:
            return False

        is_media_programs = str(self.main_cat_combo.selected_id) == media_programs_id
        return is_media_programs and self.has_compressed_file()

    def validate_before_processing(self) -> tuple[bool, list[str]]:
        errors = []

        if self.has_media_programs_with_compressed():
            errors.append("Compressed files cannot be added to Media Programs category.")

        if self.has_executable_file():
            errors.append("The tracker does not accept torrents containing .exe files.")

        return len(errors) == 0, errors

    def cancel_processing(self):
        if hasattr(self, 'preparation_timer') and self.preparation_timer.isActive():
            self.preparation_timer.stop()
        if hasattr(self, 'processing_worker') and self.processing_worker.isRunning():
            self.processing_worker.cancel()
        if hasattr(self, 'pipeline_worker') and self.pipeline_worker.isRunning():
            self.pipeline_worker.cancel()

        self.is_processing = False
        self.sidebar_panel.lbl_file_status.setText("Canceled.")
        self.sidebar_panel.sidebar_progress.setValue(0)
        self.sidebar_panel.set_start_button_enabled(False)
        self.sidebar_panel.set_parameters_enabled(True)
        self.set_main_parameters_enabled(True)
        self.update_progress()

    def closeEvent(self, event):
        if hasattr(self, 'sidebar_panel') and hasattr(self.sidebar_panel, 'save_preferences'):
            self.sidebar_panel.save_preferences()
        get_metadata_manager().cleanup()
        self.cleanup_temp_pics()
        event.accept()

    def update_tile_progress(self, current_tile: int, total_tiles: int, elapsed: float):
        if total_tiles <= 0:
            percentage = 0
        else:
            percentage = int((current_tile / total_tiles) * 50)

        self.sidebar_panel.sidebar_progress.setValue(percentage)

    def update_progress(self):
        if getattr(self, 'is_processing', False) or getattr(self, 'is_generating_torrent_pics', False):
            if hasattr(self.sidebar_panel, 'set_start_button_enabled'):
                self.sidebar_panel.set_start_button_enabled(False)
            return

        is_valid, error_messages = self.validate_before_processing()

        if error_messages != self._last_validation_errors:
            self._last_validation_errors = error_messages

            if error_messages:
                self.sidebar_panel.lbl_file_status.setText(error_messages[0])

                for idx in range(1, len(error_messages)):
                    delay = idx * 3000
                    QTimer.singleShot(
                        delay,
                        lambda msg=error_messages[idx]: self.sidebar_panel.lbl_file_status.setText(msg)
                    )
            else:
                self.sidebar_panel.lbl_file_status.setText("Ready")

        cond1 = self.main_cat_combo.selected_id is not None
        cond2 = len(self.file_manager.file_data_list) > 0
        title_text = self.title_input.text()
        cond3 = len(title_text) >= 5
        cond4 = len(self.picture_data_list) > 0
        desc_text = self.editor_panel.editor.toPlainText().strip()
        cond5 = len(desc_text) >= 5

        completed_count = sum([cond1, cond2, cond3, cond4, cond5])

        self.header_status.setText(f" {completed_count} of 5 required fields done")
        self.progress_bar.setValue(completed_count)

        is_complete = (completed_count == 5) and is_valid
        if hasattr(self.sidebar_panel, 'set_start_button_enabled'):
            self.sidebar_panel.set_start_button_enabled(is_complete)

        if is_complete:
            self.header_status.setStyleSheet("color: #22c55e; font-weight: bold;")
            self.check_lbl.setVisible(True)
        else:
            self.header_status.setStyleSheet("color: #7b8394;")
            self.check_lbl.setVisible(False)

    def browse_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Files to Include",
            self.last_browsed_dir,
            "Images and Videos (*.avif *.bmp *.gif *.heic *.heif *.jpeg *.jpg *.png *.psd *.tif *.tiff *.webp *.3gp *.asf *.asx *.avi *.bik *.divx *.flv *.m2t *.m2ts *.m2v *.m4v *.mkv *.mp4 *.mpeg *.mpg *.mov *.mts *.ogm *.ogv *.rm *.rmvb *.ts *.vob *.webm *.wmv);;"
            "Images (*.avif *.bmp *.gif *.heic *.heif *.jpeg *.jpg *.png *.psd *.tif *.tiff *.webp );;"
            "Videos (*.3gp *.asf *.asx *.avi *.bik *.divx *.flv *.m2t *.m2ts *.m2v *.m4v *.mkv *.mp4 *.mpeg *.mpg *.mov *.mts *.ogm *.ogv *.rm *.rmvb *.ts *.vob *.webm *.wmv);;"
            "All Files (*)"
        )
        if files:
            self.last_browsed_dir = os.path.dirname(files[0])
            self.selected_folder_path = None
            self.file_manager.clear_all()
            self.clear_torrent_derived_pictures()
            self.cleanup_temp_pics()
            self.file_manager.add_paths(files)
            self.update_torrent_video_button_visibility()

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Select Folder to Include", self.last_browsed_dir
        )
        if folder:
            self.last_browsed_dir = folder
            self.selected_folder_path = folder
            self.file_manager.clear_all()
            self.clear_torrent_derived_pictures()
            self.cleanup_temp_pics()
            self.file_manager.add_paths([folder])
            self.update_torrent_video_button_visibility()

    def clear_file_list(self):
        self.selected_folder_path = None
        self.file_manager.clear_all()
        self.clear_torrent_derived_pictures()
        self.cleanup_temp_pics()
        self.sync_pictures_from_files()
        self.update_torrent_video_button_visibility()
        
    def cleanup_temp_pics(self):
        temp_dir = os.path.join(tempfile.gettempdir(), "gtupl_temp_pics")
        if os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
            except Exception as e:
                print(f"[DEBUG] Failed to delete temporary pics directory: {e}")

    def handle_dropped_paths(self, paths: list[str]):
        if not paths:
            return

        incoming_bases = set()
        for p in paths:
            if os.path.isdir(p):
                incoming_bases.add(os.path.abspath(p))
            else:
                incoming_bases.add(os.path.abspath(os.path.dirname(p)))

        if len(incoming_bases) > 1:
            QMessageBox.warning(
                self,
                "Invalid Drop Selection",
                "All dropped items must belong to the same folder or relative path structure."
            )
            return

        incoming_base = list(incoming_bases)[0]

        if self.file_manager.file_data_list:
            existing_item = self.file_manager.file_data_list[0]
            existing_full_path = existing_item.get("full_path")

            if existing_full_path:
                existing_base = os.path.abspath(os.path.dirname(existing_full_path))
                if incoming_base != existing_base:
                    QMessageBox.warning(
                        self,
                        "Path Mismatch",
                        "Files must be on the same path. Clear the list to add this file, or use folder mode."
                    )
                    return

        self.file_manager.add_paths(paths)

    def browse_pictures(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select Pictures", self.last_browsed_dir, "Images (*.png *.jpg *.jpeg *.bmp *.webp)"
        )
        if files:
            self.last_browsed_dir = os.path.dirname(files[0])
            self.add_pictures(files)

    def is_image_file(self, path: str) -> bool:
        valid_extensions = (".png", ".jpg", ".jpeg", ".bmp", ".webp")
        return path.lower().endswith(valid_extensions)

    def sync_pictures_from_files(self):
        current_file_images = set()
        for item in self.file_manager.file_data_list:
            full_path = item.get("full_path")
            if full_path and os.path.isfile(full_path) and self.is_image_file(full_path):
                current_file_images.add(full_path)

        for p in list(self.auto_synced_pictures):
            if p not in current_file_images:
                if p in self.picture_data_list:
                    self.picture_data_list.remove(p)
                if p in self.pixmap_cache:
                    del self.pixmap_cache[p]
                self.auto_synced_pictures.remove(p)

        for p in current_file_images:
            if p not in self.picture_data_list and p not in self.auto_synced_pictures:
                if len(self.auto_synced_pictures) < 100:
                    self.picture_data_list.append(p)
                    self.auto_synced_pictures.add(p)
                    if p not in self.pixmap_cache:
                        pixmap = QPixmap(p)
                        if not pixmap.isNull():
                            self.pixmap_cache[p] = pixmap.scaledToHeight(206, Qt.TransformationMode.SmoothTransformation)

        self.refresh_pictures_ui()
        self.update_progress()

    def add_pictures(self, paths: list[str]):
        existing = set(self.picture_data_list)
        target_height = 206
        for p in paths:
            if os.path.isfile(p) and p not in existing:
                self.picture_data_list.append(p)
                if p not in self.pixmap_cache:
                    pixmap = QPixmap(p)
                    if not pixmap.isNull():
                        self.pixmap_cache[p] = pixmap.scaledToHeight(target_height, Qt.TransformationMode.SmoothTransformation)
        self.refresh_pictures_ui()
        self.update_progress()

    def clear_all_pictures(self):
        self.picture_data_list.clear()
        self.auto_synced_pictures.clear()
        self.pixmap_cache.clear()
        self.torrent_derived_pictures.clear()
        self.cleanup_temp_pics()
        self.refresh_pictures_ui()
        self.update_progress()

    def remove_picture(self, path: str):
        if path in self.picture_data_list:
            self.picture_data_list.remove(path)
        if path in self.pixmap_cache:
            del self.pixmap_cache[path]
        self.refresh_pictures_ui()
        self.update_progress()

    def reorder_pictures(self, path: str, target_index: int):
        if path in self.picture_data_list:
            old_index = self.picture_data_list.index(path)
            self.picture_data_list.pop(old_index)
            if old_index < target_index:
                target_index -= 1
            self.picture_data_list.insert(target_index, path)
            self.refresh_pictures_ui()
            self.update_progress()

    def refresh_pictures_ui(self):
        count = len(self.picture_data_list)
        if hasattr(self, 'pics_summary_label'):
            self.pics_summary_label.setText(f"({count} image{'s' if count != 1 else ''})")

        while self.pics_items_layout.count():
            item = self.pics_items_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        if not self.picture_data_list:
            self.btn_clear_pics.setVisible(False)

            placeholder_widget = QWidget()
            placeholder_widget.setStyleSheet("background: transparent;")
            placeholder_layout = QVBoxLayout(placeholder_widget)
            placeholder_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            placeholder_layout.setSpacing(8)

            cloud_big_icon = QLabel()
            cloud_big_icon.setPixmap(qta.icon("fa6s.cloud-arrow-up", color="#7b8394").pixmap(QSize(48, 36)))
            cloud_big_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

            drop_label = QLabel("Drop pictures for torrent presentation here.")
            drop_label.setStyleSheet("color: #7b8394; font-size: 12px; background: transparent;")
            drop_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

            placeholder_layout.addWidget(cloud_big_icon)
            placeholder_layout.addWidget(drop_label)

            placeholder_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            self.pics_items_layout.addWidget(placeholder_widget)
            return

        self.btn_clear_pics.setVisible(True)

        for path in self.picture_data_list:
            scaled_pixmap = self.pixmap_cache.get(path)
            if scaled_pixmap and not scaled_pixmap.isNull():
                tile = DraggablePictureTile(
                    path, scaled_pixmap, self.remove_picture, self.reorder_pictures
                )
                self.pics_items_layout.addWidget(tile)

    def create_card(self, title_text: str, icon_name: str | None = None) -> QFrame:
        card = QFrame()
        card.setStyleSheet("""
            QFrame { background-color: #1e222b; border: 1px solid #2a2f3a; border-radius: 6px; }
            QFrame QLabel { border: none; background: transparent; }
        """)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(15, 12, 15, 15)

        header_row = QHBoxLayout()
        header_row.setSpacing(8)

        if icon_name:
            icon_lbl = QLabel()
            icon_lbl.setPixmap(qta.icon(icon_name, color="#ffffff").pixmap(QSize(16, 16)))
            header_row.addWidget(icon_lbl)

        title = QLabel(title_text)
        title.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        title.setStyleSheet("color: #ffffff;")

        header_row.addWidget(title)
        header_row.addStretch()

        layout.addLayout(header_row)
        return card

    def get_custom_sidebar_settings(self):
        return {
            'x_tiles': int(self.sidebar_panel.spin_x_tiles.text() or 5),
            'y_tiles': int(self.sidebar_panel.spin_y_tiles.text() or 4),
            'tile_size': self.sidebar_panel.spin_tile_size.value(),
            'auto_size': self.sidebar_panel.chk_automatic.isChecked(),
            'orig_size': self.sidebar_panel.chk_original.isChecked(),
            'format': self.sidebar_panel.combo_format.currentText(),
            'quality': self.sidebar_panel.slider_quality.value(),
            'save_subfolder': self.sidebar_panel.chk_subfolders.isChecked(),
            'stamp_details': True,
            'show_filename': True,
            'show_size': True,
            'show_res': True,
            'show_fps': True,
            'show_duration': True,
            'ignore_first': 2,
            'ignore_last': 0,
            'save_frames': False,
            'overwrite': False
        }

    def generate_preview_from_sidebar(self):
        live_settings = self.sidebar_panel.get_sidebar_settings()
        self.preview_worker = PreviewWorker(settings=live_settings)
        self.preview_worker.finished.connect(self.on_preview_finished)
        self.preview_worker.start()

    def on_preview_finished(self, pil_image):
        self.sidebar_panel.btn_preview_sheet.setEnabled(True)
        self.sidebar_panel.btn_preview_sheet.setText("  Preview")

        if pil_image is None:
            return

        self.preview_dlg = ContactSheetPreviewDialog(pil_image, self)
        self.preview_dlg.exec()

    def display_validation_errors(self, error_messages: list[str]):
        self._last_validation_errors = error_messages
        self.sidebar_panel.lbl_file_status.setText("Validation error:")

        for idx, error in enumerate(error_messages):
            delay = (idx + 1) * 3000
            QTimer.singleShot(
                delay,
                lambda msg=error: self.sidebar_panel.lbl_file_status.setText(msg)
            )

        total_delay = len(error_messages) * 3000 + 1000
        QTimer.singleShot(
            total_delay,
            lambda: (
                self.sidebar_panel.lbl_file_status.setText("Ready"),
                setattr(self, '_last_validation_errors', [])
            )
        )

    def start_processing_from_sidebar(self):
        cond1 = self.main_cat_combo.selected_id is not None
        cond2 = len(self.file_manager.file_data_list) > 0
        cond3 = len(self.title_input.text()) >= 5
        cond4 = len(self.picture_data_list) > 0
        cond5 = len(self.editor_panel.editor.toPlainText().strip()) >= 5

        if not all([cond1, cond2, cond3, cond4, cond5]):
            return

        is_valid, error_messages = self.validate_before_processing()
        if not is_valid:
            self.display_validation_errors(error_messages)
            return

        indexed_items = []
        self.generated_contact_sheets = []
        valid_extensions = ('.mp4', '.mkv', '.avi', '.mov', '.webm', '.m4v')

        for idx, item in enumerate(self.file_manager.file_data_list):
            file_path = item.get("full_path") or item.get("path")
            if file_path and file_path.lower().endswith(valid_extensions):
                indexed_items.append((idx, file_path))

        settings = self.sidebar_panel.get_sidebar_settings()
        create_sheets = self.sidebar_panel.chk_create_contact_sheets.isChecked()

        self.is_processing = True
        self.sidebar_panel.set_cancel_mode()

        self.sidebar_panel.set_parameters_enabled(False)
        self.set_main_parameters_enabled(False)

        if create_sheets and indexed_items:
            self.processing_worker = ProcessingWorker(indexed_items, settings)
            self.processing_worker.progress_updated.connect(self.update_sidebar_progress)
            self.processing_worker.progress_signal.connect(self.update_tile_progress)
            self.processing_worker.finished_all.connect(self.on_processing_finished)
            self.processing_worker.start()
        else:
            self.run_torrent_pipeline(create_sheets, settings)

    def run_torrent_pipeline(self, create_sheets: bool, settings: dict):
        additional_assets = getattr(self, 'generated_contact_sheets', [])

        if hasattr(sys.stdout, 'log') and hasattr(sys.stdout.log, 'name'):
            settings["log_filepath"] = sys.stdout.log.name

        if getattr(self, 'selected_folder_path', None) and os.path.isdir(self.selected_folder_path):
            file_input = self.selected_folder_path
            mode = "folder"
        else:
            file_input = [
                item.get("full_path") or item.get("path")
                for item in self.file_manager.file_data_list
                if item.get("full_path") or item.get("path")
            ]
            mode = "files"

        main_category = self.main_cat_combo.selected_id
        sub_categories = list(self.sub_cat_combo.selected_items.keys())
        torrent_title = self.title_input.text()
        torrent_descr = self.editor_panel.editor.toPlainText()

        contact_sheet_set = set(additional_assets)
        filtered_pictures = [
            p for p in self.picture_data_list
            if p and p not in contact_sheet_set
        ]
        pictures = list(dict.fromkeys(filtered_pictures))

        print(f"[DEBUG] TORRENT CREATION PROCESS STARTED FOR TORRENT \"{torrent_title}\"")
        print(f"[DEBUG] Pictures to upload for torrent presentation ({len(pictures)}):")
        for idx, p in enumerate(pictures):
            print(f"  ({idx}) {p}")

        self.pipeline_worker = TorrentPipelineWorker(
            file_input=file_input,
            settings=settings,
            create_sheets=create_sheets,
            mode=mode,
            additional_assets=additional_assets,
            main_category=main_category,
            sub_categories=sub_categories,
            torrent_title=torrent_title,
            torrent_descr=torrent_descr,
            pictures=pictures
        )
        self.pipeline_worker.progress_signal.connect(self.update_sidebar_progress)
        self.pipeline_worker.finished_signal.connect(self.on_pipeline_finished)
        self.pipeline_worker.history_signal.connect(self.history_panel.add_run)
        self.pipeline_worker.start()

    def on_processing_finished(self, was_cancelled: bool = False):
        if was_cancelled:
            self.is_processing = False
            self.sidebar_panel.lbl_file_status.setText("Processing cancelled.")
            self.sidebar_panel.sidebar_progress.setValue(0)
            self.sidebar_panel.set_start_button_enabled(False)
            self.sidebar_panel.set_parameters_enabled(True)
            self.set_main_parameters_enabled(True)
            self.update_progress()
        else:
            settings = self.sidebar_panel.get_sidebar_settings()

            if hasattr(self, 'processing_worker'):
                self.generated_contact_sheets = getattr(self.processing_worker, 'generated_files', [])
            else:
                self.generated_contact_sheets = []

            self.sidebar_panel.lbl_file_status.setText("Contact sheets created. Preparing torrent...")
            create_sheets = self.sidebar_panel.chk_create_contact_sheets.isChecked()

            self.preparation_timer = QTimer(self)
            self.preparation_timer.setSingleShot(True)
            self.preparation_timer.timeout.connect(lambda: self.run_torrent_pipeline(create_sheets, settings))
            self.preparation_timer.start(3000)

    def on_pipeline_finished(self, success: bool, data=None):
        self.is_processing = False

        if success:
            self.sidebar_panel.lbl_file_status.setText("Upload completed successfully!")
            self.sidebar_panel.sidebar_progress.setValue(100)
            self.sidebar_panel.set_start_button_enabled(True)

            if isinstance(data, dict):
                self.generated_torrent_path = data.get("output_file")
                torrent_id = data.get("torrent_id")
                encrypted_id = data.get("encrypted_id")
                redirect_path = data.get("redirect")
            else:
                if hasattr(self.pipeline_worker, 'temp_torrent_path'):
                    self.generated_torrent_path = self.pipeline_worker.temp_torrent_path

        elif getattr(self.pipeline_worker, 'is_canceled', False):
            self.sidebar_panel.lbl_file_status.setText("Upload was canceled.")
            self.sidebar_panel.sidebar_progress.setValue(0)
            self.sidebar_panel.set_start_button_enabled(True)

        else:
            self.sidebar_panel.lbl_file_status.setText("Upload failed.")
            self.sidebar_panel.sidebar_progress.setValue(0)
            self.sidebar_panel.set_start_button_enabled(True)

        self.sidebar_panel.set_parameters_enabled(True)
        self.set_main_parameters_enabled(True)
        self.update_progress()

    def update_sidebar_progress(self, value: int, status_text: str):
        self.sidebar_panel.lbl_file_status.setText(status_text)
        self.sidebar_panel.sidebar_progress.setValue(value)
        
    def update_torrent_video_button_visibility(self):
        has_valid = any(
            (item.get("full_path") or item.get("path") or "").lower().endswith(VALID_VIDEO_EXTENSIONS)
            for item in self.file_manager.file_data_list
        )
        self.btn_add_from_torrent.setVisible(has_valid)

    def open_add_from_torrent_dialog(self):
        valid_items = [
            item for item in self.file_manager.file_data_list
            if (item.get("full_path") or item.get("path") or "").lower().endswith(VALID_VIDEO_EXTENSIONS)
        ]
        
        dlg = AddFromTorrentDialog(valid_items, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            selected_paths = dlg.get_selected_items()
            options = dlg.get_options()
            if not selected_paths:
                return
            
            indexed_items = [
                (idx, item.get("full_path") or item.get("path"))
                for idx, item in enumerate(self.file_manager.file_data_list)
                if (item.get("full_path") or item.get("path")) in selected_paths
            ]
            
            settings = self.sidebar_panel.get_sidebar_settings()
            # Enable safeguard flag and update UI button state immediately
            self.is_generating_torrent_pics = True
            self.update_progress()
            
            self.sidebar_panel.lbl_file_status.setText("Generating pictures from torrent files...")
            self.torrent_worker = TorrentPicturesProcessingWorker(indexed_items, settings, options)
            self.torrent_worker.finished.connect(self.on_torrent_pictures_finished)
            self.torrent_worker.start()

    def on_torrent_pictures_finished(self, generated_paths: list):
        self.is_generating_torrent_pics = False  # Clear safeguard flag
        self.sidebar_panel.lbl_file_status.setText("Ready")
        if generated_paths:
            for p in generated_paths:
                self.torrent_derived_pictures.add(p)
            self.add_pictures(generated_paths)
        
        self.update_progress()

    def clear_torrent_derived_pictures(self):
        for p in list(self.torrent_derived_pictures):
            if p in self.picture_data_list:
                self.picture_data_list.remove(p)
            if p in self.pixmap_cache:
                del self.pixmap_cache[p]
        self.torrent_derived_pictures.clear()
        self.refresh_pictures_ui()
        self.update_progress()


def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    tb_lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
    tb_text = "".join(tb_lines)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"\n=== CRASH REPORT [{timestamp}] ===\n{tb_text}\n"

    print(log_entry, file=sys.stderr)

    if hasattr(sys.stdout, 'flush'):
        sys.stdout.flush()

    try:
        app = QApplication.instance()
        if app is not None:
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Icon.Critical)
            msg.setWindowTitle("GTUpl has Crashed")
            msg.setText("The application has encountered a fatal error and needs to close.")
            msg.setDetailedText(tb_text)
            msg.exec()
    except Exception:
        pass

    sys.exit(1)


if __name__ == "__main__":
    # Required for the frozen app: the pipeline runs in a child process
    # (spawn start method on macOS and Windows).
    multiprocessing.freeze_support()
    sys.excepthook = handle_exception

    tee_instance = Tee()
    sys.stdout = tee_instance
    sys.stderr = tee_instance

    if sys.platform == "win32":
        gtupl = "gaytorrentuploader.app.1.0"
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(gtupl)

    app = QApplication(sys.argv)

    app_icon = QIcon()
    if "icon.png" in ASSETS:
        asset_stream = get_asset_stream("icon.png")
        icon_bytes = asset_stream.read()

        pixmap = QPixmap()
        pixmap.loadFromData(QByteArray(icon_bytes))
        app_icon = QIcon(pixmap)
        app.setWindowIcon(app_icon)

    from login import ensure_logged_in

    if ensure_logged_in():
        window = DarkFormApp()

        if not app_icon.isNull():
            window.setWindowIcon(app_icon)

        window.show()
        sys.exit(app.exec())
    else:
        print("[ERROR] Login failed or cancelled. Exiting application.")
        sys.exit(1)
