import os
import tempfile
import shutil
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox, 
    QPushButton, QScrollArea, QFrame, QWidget
)
from csc import ProcessingWorker

VALID_VIDEO_EXTENSIONS = (
    '.3gp', '.asf', '.asx', '.avi', '.bik', '.divx', '.flv',
    '.m2t', '.m2ts', '.m2v', '.m4v', '.mkv', '.mp4', '.mpeg',
    '.mpg', '.mov', '.mts', '.ogm', '.ogv', '.rm', '.rmvb',
    '.ts', '.vob', '.webm', '.wmv'
)

class AddFromTorrentDialog(QDialog):
    def __init__(self, valid_items, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Pictures from Torrent Files")
        self.resize(500, 450)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)
        
        warning_frame = QFrame()
        warning_frame.setObjectName("warningFrame")
        warning_frame.setStyleSheet("#warningFrame { background-color: #3b1d24; border: 1px solid #ef4444; border-radius: 6px; }")
        
        warn_layout = QVBoxLayout(warning_frame)
        warn_layout.setContentsMargins(12, 10, 12, 10)
        warn_lbl = QLabel("Be advised that the pictures will be added ONLY to torrent presentation, if you also want to include them to the torrent content you must enable Contact Sheets in the sidebar.")
        warn_lbl.setWordWrap(True)
        warn_lbl.setStyleSheet("color: #fca5a5; font-weight: bold; font-size: 11px;")
        warn_layout.addWidget(warn_lbl)
        layout.addWidget(warning_frame)
        
        # Evaluate total files and check limit
        total_files = len(valid_items)
        self.exceeds_limit = total_files > 100
        
        # Show message below the warning header if count > 100
        if self.exceeds_limit:
            limit_lbl = QLabel(f"Found {total_files} files. Only the first 100 have been selected (maximum limit is 100).")
            limit_lbl.setWordWrap(True)
            limit_lbl.setStyleSheet("color: #fbbf24; font-weight: bold; font-size: 11px; margin-top: 2px;")
            layout.addWidget(limit_lbl)
        
        # Select All Checkbox
        select_all_text = "Select All Files (First 100)" if self.exceeds_limit else "Select All Files"
        self.chk_select_all = QCheckBox(select_all_text)
        self.chk_select_all.setChecked(True)
        self.chk_select_all.setStyleSheet("color: #ffffff; font-weight: bold; font-size: 11px; margin-left: 2px;")
        layout.addWidget(self.chk_select_all)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { background-color: #14161c; border: 1px solid #2a2f3a; border-radius: 6px; }")
        
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        cont_layout = QVBoxLayout(container)
        cont_layout.setContentsMargins(10, 10, 10, 10)
        cont_layout.setSpacing(6)
        
        def update_checked_count():
            checked_boxes = [chk for chk in self.checkboxes if chk.isChecked()]
            
            # Hard enforce max 100 limit if someone checks manually past the limit
            if len(checked_boxes) > 100:
                # Uncheck the sender or the excess items
                for chk in checked_boxes[100:]:
                    chk.blockSignals(True)
                    chk.setChecked(False)
                    chk.blockSignals(False)
                checked_boxes = checked_boxes[:100]

            print(f"Total checked items: {len(checked_boxes)}")
        
        self.checkboxes = []
        for index, item in enumerate(valid_items):
            full_path = item.get("full_path") or item.path
            display_path = item.get("display_path") or os.path.basename(full_path)
            chk = QCheckBox(display_path)
            
            if self.exceeds_limit:
                chk.setChecked(index < 100)
            else:
                chk.setChecked(True)
                
            chk.setStyleSheet("color: #d0d4dc; font-size: 11px;")
            chk.setProperty("full_path", full_path)
            
            # Connect each checkbox toggle to print the count
            chk.toggled.connect(update_checked_count)
            
            cont_layout.addWidget(chk)
            self.checkboxes.append(chk)
            
        cont_layout.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll, stretch=1)
        
        # Initial print to show the starting count when dialog opens
        update_checked_count()

        def toggle_all_files(checked):
            target_checkboxes = self.checkboxes[:100] if self.exceeds_limit else self.checkboxes
            for chk in target_checkboxes:
                chk.blockSignals(True)
                chk.setChecked(checked)
                chk.blockSignals(False)
            update_checked_count() # Print the final count once
                
        self.chk_select_all.toggled.connect(toggle_all_files)
        
        options_frame = QFrame()
        options_frame.setStyleSheet("background-color: #1e222b; border: 1px solid #2a2f3a; border-radius: 6px;")
        opt_layout = QVBoxLayout(options_frame)
        opt_layout.setContentsMargins(12, 10, 12, 10)
        opt_layout.setSpacing(8)
        
        self.chk_individual_frames = QCheckBox("Individual Frames")
        self.chk_individual_frames.setChecked(True)
        self.chk_individual_frames.setStyleSheet("color: #ffffff; font-weight: bold;")
        
        self.chk_contact_sheets = QCheckBox("Contact Sheets")
        self.chk_contact_sheets.setChecked(False)
        self.chk_contact_sheets.setStyleSheet("color: #ffffff; font-weight: bold;")
        
        opt_layout.addWidget(self.chk_individual_frames)
        opt_layout.addWidget(self.chk_contact_sheets)
        layout.addWidget(options_frame)
        
        # Mutually exclusive condition so only one can be checked at a time
        def on_individual_toggled(checked):
            if checked:
                self.chk_contact_sheets.blockSignals(True)
                self.chk_contact_sheets.setChecked(False)
                self.chk_contact_sheets.blockSignals(False)
            elif not self.chk_contact_sheets.isChecked():
                self.chk_individual_frames.blockSignals(True)
                self.chk_individual_frames.setChecked(True)
                self.chk_individual_frames.blockSignals(False)
                
        def on_contact_toggled(checked):
            if checked:
                self.chk_individual_frames.blockSignals(True)
                self.chk_individual_frames.setChecked(False)
                self.chk_individual_frames.blockSignals(False)
            elif not self.chk_individual_frames.isChecked():
                self.chk_contact_sheets.blockSignals(True)
                self.chk_contact_sheets.setChecked(True)
                self.chk_contact_sheets.blockSignals(False)
                
        self.chk_individual_frames.toggled.connect(on_individual_toggled)
        self.chk_contact_sheets.toggled.connect(on_contact_toggled)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setStyleSheet("QPushButton { background-color: #1e222b; border: 1px solid #3a4150; color: #d0d4dc; border-radius: 4px; padding: 6px 16px; font-weight: bold; } QPushButton:hover { background-color: #2a2f3d; }")
        self.btn_cancel.clicked.connect(self.reject)
        
        self.btn_start = QPushButton("Start")
        self.btn_start.setStyleSheet("QPushButton { background-color: #2ea44f; border: 1px solid #2ecc71; color: white; border-radius: 4px; padding: 6px 16px; font-weight: bold; } QPushButton:hover { background-color: #27ae60; }")
        self.btn_start.clicked.connect(self.accept)
        
        self.btn_start.setEnabled(True)
        
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_start)
        layout.addLayout(btn_layout)

    def get_selected_items(self):
        return [chk.property("full_path") for chk in self.checkboxes if chk.isChecked()]

    def get_options(self):
        return {
            "individual_frames": self.chk_individual_frames.isChecked(),
            "contact_sheets": self.chk_contact_sheets.isChecked()
        }


class TorrentPicturesProcessingWorker(QThread):
    finished = pyqtSignal(list)

    def __init__(self, indexed_items, settings, options):
        super().__init__()
        self.indexed_items = indexed_items
        self.settings = settings
        self.options = options
        self.generated_files = []

    def run(self):
        output_dir = os.path.join(tempfile.gettempdir(), "gtupl_temp_pics")
        os.makedirs(output_dir, exist_ok=True)
        all_generated = []

        if self.options.get("contact_sheets"):
            cs_settings = self.settings.copy()
            cs_settings["save_frames"] = False
            cs_settings["create_contact_sheet"] = True
            cs_settings['custom_output_dir'] = output_dir

            worker = ProcessingWorker(self.indexed_items, cs_settings)
            worker.start()
            worker.wait()
            if hasattr(worker, 'generated_files'):
                for f in worker.generated_files:
                    if os.path.exists(f):
                        dest = os.path.join(output_dir, os.path.basename(f))
                        try:
                            if f != dest:
                                shutil.copy2(f, dest)
                            all_generated.append(dest)
                        except Exception:
                            all_generated.append(f)

        if self.options.get("individual_frames"):
            if_settings = self.settings.copy()
            if_settings['orig_size'] = True
            if_settings['auto_size'] = False
            if_settings['save_frames'] = True
            if_settings['ignore_last'] = 5
            if_settings['create_contact_sheet'] = False
            if_settings['custom_output_dir'] = output_dir
            if_settings['torrent_frames_naming'] = True

            valid_count = len(self.indexed_items)
            if valid_count == 1:
                if_settings['x_tiles'] = 5
                if_settings['y_tiles'] = 1
                if_settings['ignore_first'] = 5
            elif 2 <= valid_count <= 5:
                if_settings['x_tiles'] = 3
                if_settings['y_tiles'] = 1
                if_settings['ignore_first'] = 5
            else:
                if_settings['x_tiles'] = 1
                if_settings['y_tiles'] = 1
                if_settings['ignore_first'] = 49

            worker_if = ProcessingWorker(self.indexed_items, if_settings)
            worker_if.start()
            worker_if.wait()
            if hasattr(worker_if, 'generated_files'):
                for f in worker_if.generated_files:
                    if os.path.exists(f):
                        all_generated.append(f)

        self.generated_files = list(dict.fromkeys(all_generated))
        self.finished.emit(self.generated_files)