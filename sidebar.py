from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QFont, QPixmap, QCursor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QFrame, QLabel, 
    QPushButton, QScrollArea, QCheckBox, QSpinBox, QComboBox, QSlider, QStackedWidget, QProgressBar
)
import qtawesome as qta
from login import get_stored_username, clear_api_key
from history import HistoryPanelComponent


class NonScrollableSlider(QSlider):
    def wheelEvent(self, event):
        # Ignore wheel events to prevent scrolling from changing the slider value
        event.ignore()


class SidebarPanelComponent(QWidget):
    def __init__(self, parent_window):
        super().__init__()
        self.parent = parent_window
        
        self._last_valid_client = ""
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        sidebar_frame = QFrame()
        sidebar_frame.setFixedWidth(400)
        sidebar_frame.setStyleSheet("""
            QFrame {
                background-color: #1e222b;
                border: 1px solid #2a2f3a;
                border-radius: 6px;
            }
            QLabel {
                border: none;
                background: transparent;
                color: #ffffff;
            }
            QCheckBox {
                color: #ffffff;
            }
        """)
        
        frame_layout = QVBoxLayout(sidebar_frame)
        frame_layout.setContentsMargins(0, 0, 0, 0)
        frame_layout.setSpacing(0)

        # Scroll Area for all settings
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical {
                background: #171a21;
                width: 6px;
                margin: 0px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical {
                background: #3a4150;
                border-radius: 3px;
                min-height: 20px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
        """)

        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: transparent;")
        sidebar_layout = QVBoxLayout(scroll_content)
        sidebar_layout.setContentsMargins(20, 8, 14, 8)
        sidebar_layout.setSpacing(8)

        # --- User Profile Section ---
        user_profile_layout = QVBoxLayout()
        user_profile_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        user_profile_layout.setSpacing(6)

        # Fetch actual username stored together with the API key
        actual_username = get_stored_username() or "User"

        lbl_username = QLabel(actual_username)
        lbl_username.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        lbl_username.setStyleSheet("color: #ffffff;")
        lbl_username.setAlignment(Qt.AlignmentFlag.AlignCenter)
        user_profile_layout.addWidget(lbl_username)

        self.btn_logout = QPushButton("Logout")
        self.btn_logout.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_logout.setStyleSheet("""
            QPushButton {
                background-color: #171a21;
                border: 1px solid #3a4150;
                color: #ef4444;
                border-radius: 4px;
                padding: 4px 14px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #3b1d24; border-color: #ef4444; }
        """)
        self.btn_logout.clicked.connect(self.handle_logout)
        
        logout_container = QHBoxLayout()
        logout_container.addStretch()
        logout_container.addWidget(self.btn_logout)
        logout_container.addStretch()
        user_profile_layout.addLayout(logout_container)

        sidebar_layout.addLayout(user_profile_layout)
        sidebar_layout.addSpacing(4)

        # --- Master Create Contact Sheets Toggle ---
        self.chk_create_contact_sheets = QCheckBox("Create Contact Sheets")
        self.chk_create_contact_sheets.setChecked(True)
        self.chk_create_contact_sheets.setStyleSheet("color: #ffffff; font-weight: bold;")
        sidebar_layout.addWidget(self.chk_create_contact_sheets)

        # --- Header ---
        sb_header_widget = QWidget()
        sb_header = QHBoxLayout(sb_header_widget)
        sb_header.setContentsMargins(0, 0, 0, 0)
        sb_icon = QLabel()
        sb_icon.setPixmap(qta.icon("fa6s.table", color="#ffffff").pixmap(QSize(16, 16)))
        sb_title = QLabel("Contact Sheet Preferences")
        sb_title.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        sb_title.setStyleSheet("color: #ffffff;")
        sb_header.addWidget(sb_icon)
        sb_header.addWidget(sb_title)
        sb_header.addStretch()
        sidebar_layout.addWidget(sb_header_widget)

        # --- Layout Grid Configuration Box ---
        config_box = QFrame()
        config_box.setStyleSheet("background-color: #14161c; border: none; border-radius: 4px;")
        config_layout = QGridLayout(config_box)
        config_layout.setContentsMargins(10, 10, 10, 10)
        config_layout.setSpacing(6)

        # X Tiles (Column 0 & 1 - Left aligned)
        self.spin_x_tiles = QSpinBox()
        self.spin_x_tiles.setRange(1, 10)
        self.spin_x_tiles.setValue(5)
        self.spin_x_tiles.setFixedWidth(45)
        self.apply_input_style(self.spin_x_tiles)
        config_layout.addWidget(self.spin_x_tiles, 0, 0)
        
        lbl_x_tiles = QLabel("Horizontal Tiles")
        lbl_x_tiles.setStyleSheet("color: #ffffff;")
        config_layout.addWidget(lbl_x_tiles, 0, 1)

        # Add a stretch factor to column 2 to create even spacing/push items apart
        config_layout.setColumnStretch(2, 1)

        # Y Tiles (Shifted to Column 3 & 4 - Right aligned)
        self.spin_y_tiles = QSpinBox()
        self.spin_y_tiles.setRange(1, 10)
        self.spin_y_tiles.setValue(4)
        self.spin_y_tiles.setFixedWidth(45)
        self.apply_input_style(self.spin_y_tiles)
        config_layout.addWidget(self.spin_y_tiles, 0, 3)
        
        lbl_y_tiles = QLabel("Vertical Tiles")
        lbl_y_tiles.setStyleSheet("color: #ffffff;")
        config_layout.addWidget(lbl_y_tiles, 0, 4)

        sidebar_layout.addWidget(config_box)

        # --- Tile Size Configuration Box ---
        size_box = QFrame()
        size_box.setStyleSheet("background-color: #14161c; border: none; border-radius: 4px;")
        size_layout = QGridLayout(size_box)
        size_layout.setContentsMargins(10, 10, 10, 10)
        size_layout.setSpacing(6)

        lbl_tile_size = QLabel("Tile Size (px):")
        lbl_tile_size.setStyleSheet("color: #ffffff;")
        size_layout.addWidget(lbl_tile_size, 0, 0)

        self.spin_tile_size = QSpinBox()
        self.spin_tile_size.setRange(64, 4096)
        self.spin_tile_size.setValue(512)
        self.spin_tile_size.setFixedWidth(75)
        self.apply_input_style(self.spin_tile_size)
        size_layout.addWidget(self.spin_tile_size, 0, 1, Qt.AlignmentFlag.AlignRight)

        # Swapped: Original is now placed first (Column 0)
        self.chk_original = QCheckBox("Original")
        self.chk_original.setStyleSheet("color: #ffffff;")
        size_layout.addWidget(self.chk_original, 1, 0)

        # Automatic is now placed second (Column 1)
        self.chk_automatic = QCheckBox("Automatic")
        self.chk_automatic.setChecked(True)
        self.chk_automatic.setStyleSheet("color: #ffffff;")
        size_layout.addWidget(self.chk_automatic, 1, 1, Qt.AlignmentFlag.AlignRight)

        def on_original_toggled(checked):
            if checked:
                self.chk_automatic.blockSignals(True)
                self.chk_automatic.setChecked(False)
                self.chk_automatic.blockSignals(False)
                self.spin_tile_size.setEnabled(False)
            elif not self.chk_automatic.isChecked():
                self.chk_original.blockSignals(True)
                self.chk_original.setChecked(True)
                self.chk_original.blockSignals(False)
                self.spin_tile_size.setEnabled(True)

        def on_automatic_toggled(checked):
            if checked:
                self.chk_original.blockSignals(True)
                self.chk_original.setChecked(False)
                self.chk_original.blockSignals(False)
                self.spin_tile_size.setEnabled(True)
            elif not self.chk_original.isChecked():
                self.chk_automatic.blockSignals(True)
                self.chk_automatic.setChecked(True)
                self.chk_automatic.blockSignals(False)

        self.chk_original.toggled.connect(on_original_toggled)
        self.chk_automatic.toggled.connect(on_automatic_toggled)

        sidebar_layout.addWidget(size_box)

        # --- Technical Details Stamping Box ---
        tech_box = QFrame()
        tech_box.setStyleSheet("background-color: #14161c; border: none; border-radius: 4px;")
        tech_layout = QVBoxLayout(tech_box)
        tech_layout.setContentsMargins(10, 10, 10, 10)
        tech_layout.setSpacing(6)

        self.chk_stamp_details = QCheckBox("Stamp Details")
        self.chk_stamp_details.setChecked(True)
        self.chk_stamp_details.setStyleSheet("color: #ffffff; font-weight: bold;")
        tech_layout.addWidget(self.chk_stamp_details)

        tech_grid = QGridLayout()
        tech_grid.setSpacing(6)
        self.chk_fname = QCheckBox("File name")
        self.chk_fname.setChecked(True)
        self.chk_fsize = QCheckBox("File Size")
        self.chk_fsize.setChecked(True)
        self.chk_res = QCheckBox("Resolution")
        self.chk_res.setChecked(True)
        self.chk_fps = QCheckBox("FPS")
        self.chk_fps.setChecked(True)
        self.chk_duration = QCheckBox("Duration")
        self.chk_duration.setChecked(True)

        tech_grid.addWidget(self.chk_fname, 0, 0, 1, 2)
        tech_grid.addWidget(self.chk_fsize, 1, 0, 1, 2)
        tech_grid.addWidget(self.chk_res, 2, 0)
        tech_grid.addWidget(self.chk_fps, 2, 1)
        tech_grid.addWidget(self.chk_duration, 3, 0, 1, 2)
        tech_layout.addLayout(tech_grid)

        def toggle_tech_options(checked):
            self.chk_fname.setEnabled(checked)
            self.chk_fsize.setEnabled(checked)
            self.chk_res.setEnabled(checked)
            self.chk_fps.setEnabled(checked)
            self.chk_duration.setEnabled(checked)

        self.chk_stamp_details.toggled.connect(toggle_tech_options)
        sidebar_layout.addWidget(tech_box)

        # --- Trim Limits Box ---
        trim_box = QFrame()
        trim_box.setStyleSheet("background-color: #14161c; border: none; border-radius: 4px;")
        trim_layout = QGridLayout(trim_box)
        trim_layout.setContentsMargins(10, 10, 10, 10)
        trim_layout.setSpacing(6)

        lbl_trim_title = QLabel("Trim Limits")
        lbl_trim_title.setStyleSheet("color: #ffffff; font-weight: bold;")
        trim_layout.addWidget(lbl_trim_title, 0, 0, 1, 2)

        self.spin_ignore_first = QSpinBox()
        self.spin_ignore_first.setRange(0, 49)
        self.spin_ignore_first.setValue(2)
        self.spin_ignore_first.setSuffix(" %")
        self.spin_ignore_first.setFixedWidth(65)
        self.apply_input_style(self.spin_ignore_first)

        self.spin_ignore_last = QSpinBox()
        self.spin_ignore_last.setRange(0, 49)
        self.spin_ignore_last.setValue(2)
        self.spin_ignore_last.setSuffix(" %")
        self.spin_ignore_last.setFixedWidth(65)
        self.apply_input_style(self.spin_ignore_last)

        lbl_ignore_first = QLabel("Ignore first:")
        lbl_ignore_first.setStyleSheet("color: #ffffff;")
        lbl_ignore_last = QLabel("Ignore last:")
        lbl_ignore_last.setStyleSheet("color: #ffffff;")

        trim_layout.addWidget(lbl_ignore_first, 1, 0)
        trim_layout.addWidget(self.spin_ignore_first, 1, 1, Qt.AlignmentFlag.AlignRight)
        trim_layout.addWidget(lbl_ignore_last, 2, 0)
        trim_layout.addWidget(self.spin_ignore_last, 2, 1, Qt.AlignmentFlag.AlignRight)

        sidebar_layout.addWidget(trim_box)

        # --- Output Format & Quality Box ---
        fmt_box = QFrame()
        fmt_box.setStyleSheet("background-color: #14161c; border: none; border-radius: 4px;")
        fmt_box_layout = QVBoxLayout(fmt_box)
        fmt_box_layout.setContentsMargins(10, 10, 10, 10)
        fmt_box_layout.setSpacing(6)

        lbl_fmt_title = QLabel("Output Options")
        lbl_fmt_title.setStyleSheet("color: #ffffff; font-weight: bold;")
        fmt_box_layout.addWidget(lbl_fmt_title)

        fmt_row = QHBoxLayout()
        lbl_format = QLabel("Format:")
        lbl_format.setStyleSheet("color: #ffffff;")
        self.combo_format = QComboBox()
        self.combo_format.addItems(["JPEG", "PNG", "WEBP"])
        self.combo_format.setCurrentText("JPEG")
        self.apply_input_style(self.combo_format)
        
        fmt_row.addWidget(lbl_format)
        fmt_row.addWidget(self.combo_format, 1)
        fmt_box_layout.addLayout(fmt_row)

        quality_label_layout = QHBoxLayout()
        self.lbl_quality_title = QLabel("Quality: 65%")
        self.lbl_quality_title.setStyleSheet("color: #ffffff;")
        quality_label_layout.addWidget(self.lbl_quality_title)
        quality_label_layout.addStretch()
        fmt_box_layout.addLayout(quality_label_layout)

        # Using NonScrollableSlider instead of standard QSlider
        self.slider_quality = NonScrollableSlider(Qt.Orientation.Horizontal)
        self.slider_quality.setRange(50, 100)
        self.slider_quality.setValue(65)
        self.slider_quality.setStyleSheet("""
            QSlider::groove:horizontal { border: 1px solid #2a2f3a; height: 4px; background: #171a21; border-radius: 2px; }
            QSlider::handle:horizontal { background: #3b82f6; border: none; width: 12px; margin: -4px 0; border-radius: 6px; }
        """)
        self.slider_quality.valueChanged.connect(lambda val: self.lbl_quality_title.setText(f"Quality: {val}%"))
        fmt_box_layout.addWidget(self.slider_quality)

        def on_format_changed(fmt):
            is_lossy = fmt in ("JPEG", "WEBP")
            self.slider_quality.setEnabled(is_lossy)
            self.lbl_quality_title.setEnabled(is_lossy)

        self.combo_format.currentTextChanged.connect(on_format_changed)

        self.chk_subfolders = QCheckBox("Save in 'contact_sheets' subfolder")
        fmt_box_layout.addWidget(self.chk_subfolders)

        self.chk_save_frames = QCheckBox("Save individual thumbnail frames")
        fmt_box_layout.addWidget(self.chk_save_frames)

        sidebar_layout.addWidget(fmt_box)

        # --- Preview Button ---
        self.btn_preview_sheet = QPushButton(" Preview ")
        self.btn_preview_sheet.setIcon(qta.icon("fa6s.eye", color="#d0d4dc"))
        self.btn_preview_sheet.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_preview_sheet.setStyleSheet("""
            QPushButton {
                background-color: #171a21;
                border: 1px solid #3a4150;
                color: #ffffff;
                border-radius: 4px;
                padding: 8px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #2a2f3d; border-color: #3b82f6; }
        """)
        
        if hasattr(self.parent, "generate_preview_from_sidebar"):
            self.btn_preview_sheet.clicked.connect(self.parent.generate_preview_from_sidebar)
            
        sidebar_layout.addWidget(self.btn_preview_sheet)

        # --- Dynamic Visibility Toggle Handler ---
        def toggle_contact_sheet_options(checked):
            sb_header_widget.setVisible(checked)
            config_box.setVisible(checked)
            size_box.setVisible(checked)
            tech_box.setVisible(checked)
            trim_box.setVisible(checked)
            fmt_box.setVisible(checked)
            self.btn_preview_sheet.setVisible(checked)

        self.chk_create_contact_sheets.toggled.connect(toggle_contact_sheet_options)

        # --- Seeding & Progress Status Section ---
        sidebar_layout.addSpacing(6)
        self.chk_seeding = QCheckBox("Start seeding automatically using:")
        self.chk_seeding.setChecked(True)
        sidebar_layout.addWidget(self.chk_seeding)

        self.combo_client = QComboBox()
        self.combo_client.addItems(["qBittorrent", "uTorrent"])
        # Insert a blank item at index 0 so it's the initial selection
        self.combo_client.insertItem(0, "")
        self.combo_client.setCurrentIndex(0)
        
        self.apply_input_style(self.combo_client)
        
        # Track the resolved path
        self.qbittorrent_path = ""
        self.utorrent_path = ""
        self.torrent_client_path = ""
        
        # Connect selection change to the validation handler
        self.combo_client.currentIndexChanged.connect(self.on_torrent_client_changed)
        
        sidebar_layout.addWidget(self.combo_client)

        self.sidebar_progress = QProgressBar()
        self.sidebar_progress.setRange(0, 100)
        self.sidebar_progress.setFixedHeight(14)
        self.sidebar_progress.setStyleSheet("""
            QProgressBar {
                background-color: #171a21;
                border: 1px solid #2a2f3a;
                border-radius: 7px;
                text-align: center;
                color: #ffffff;
                font-size: 10px;
            }
            QProgressBar::chunk {
                background-color: #22c55e;
                border-radius: 6px;
            }
        """)
        sidebar_layout.addWidget(self.sidebar_progress)

        self.lbl_file_status = QLabel("Ready")
        self.lbl_file_status.setWordWrap(True)
        self.lbl_file_status.setStyleSheet("color: #ffffff; font-size: 10px;")
        sidebar_layout.addWidget(self.lbl_file_status)

        sidebar_layout.addSpacing(6)

        # --- Start Button & History Button Layout ---
        start_container = QHBoxLayout()
        start_container.setSpacing(6)
        start_container.setContentsMargins(0, 0, 0, 0)

        self.btn_start = QPushButton("Start")
        self.btn_start.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_start.setEnabled(False)  # Start disabled by default
        
        # Initialize dynamic properties for states and modes
        self.btn_start.setProperty("active", False)
        self.btn_start.setProperty("mode", "normal")
        
        self.btn_start.setStyleSheet("""
            QPushButton[active="true"][mode="normal"] {
                background-color: #2ea44f;
                border: 1px solid #2ecc71;
                color: white;
                border-radius: 4px;
                padding: 8px;
                font-weight: bold;
            }
            QPushButton[active="true"][mode="normal"]:hover { 
                background-color: #27ae60; 
            }
            QPushButton[active="false"] {
                background-color: #14161c;
                border: 1px solid #2a2f3a;
                color: #4b5563;
                border-radius: 4px;
                padding: 8px;
                font-weight: bold;
            }
            QPushButton[mode="cancel"] {
                background-color: #171a21;
                border: 1px solid #ef4444;
                color: #ef4444;
                border-radius: 4px;
                padding: 8px;
                font-weight: bold;
            }
            QPushButton[mode="cancel"]:hover {
                background-color: #3b1d24;
                border-color: #ef4444;
            }
        """)
        start_container.addWidget(self.btn_start, 1)

        self.btn_history = QPushButton()
        self.btn_history.setIcon(qta.icon("fa6s.clock-rotate-left", color="#d0d4dc"))
        self.btn_history.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_history.setStyleSheet("""
            QPushButton {
                background-color: #171a21;
                border: 1px solid #3a4150;
                border-radius: 4px;
                padding: 8px;
            }
            QPushButton:hover { background-color: #2a2f3d; border-color: #3b82f6; }
            QPushButton:pressed { background-color: #1f242e; }
        """)
        start_container.addWidget(self.btn_history)

        sidebar_layout.addLayout(start_container)

        scroll_area.setWidget(scroll_content)
        frame_layout.addWidget(scroll_area)

        # --- QStackedWidget for View Switching ---
        self.stacked_widget = QStackedWidget()
        
        # Page 0: Main Sidebar Frame
        self.stacked_widget.addWidget(sidebar_frame)
        
        # Page 1: Separate History Panel Component
        self.history_panel = HistoryPanelComponent(self)
        self.stacked_widget.addWidget(self.history_panel)

        # Wire up view switching buttons
        self.btn_history.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(1))
        self.history_panel.back_requested.connect(lambda: self.stacked_widget.setCurrentIndex(0))

        main_layout.addWidget(self.stacked_widget)
        
        # Load saved preferences after UI components are fully created
        self.load_preferences()

    def handle_logout(self):
        """Forgets the stored API key and instructs main_ui to close the app."""
        print("[LOGOUT] Removing the stored API key...")
        if clear_api_key():
            print("[LOGOUT] Logout successful. The key stays valid on the site until you revoke it there.")

        if hasattr(self.parent, "close"):
            self.parent.close()
        
    def set_parameters_enabled(self, enabled: bool):
        """Enable or disable all sidebar parameter inputs during processing."""
        self.chk_create_contact_sheets.setEnabled(enabled)
        self.spin_x_tiles.setEnabled(enabled)
        self.spin_y_tiles.setEnabled(enabled)
        
        # Respect original size lock if active
        is_original = self.chk_original.isChecked()
        self.chk_automatic.setEnabled(enabled)
        self.chk_original.setEnabled(enabled)
        if enabled:
            self.spin_tile_size.setEnabled(not is_original)
        else:
            self.spin_tile_size.setEnabled(False)
            
        self.chk_stamp_details.setEnabled(enabled)
        
        # Tech options depend on stamp details master toggle
        stamp_checked = self.chk_stamp_details.isChecked() and enabled
        self.chk_fname.setEnabled(stamp_checked)
        self.chk_fsize.setEnabled(stamp_checked)
        self.chk_res.setEnabled(stamp_checked)
        self.chk_fps.setEnabled(stamp_checked)
        self.chk_duration.setEnabled(stamp_checked)
        
        self.spin_ignore_first.setEnabled(enabled)
        self.spin_ignore_last.setEnabled(enabled)
        self.combo_format.setEnabled(enabled)
        
        # Quality slider depends on format lossiness
        is_lossy = self.combo_format.currentText() in ("JPEG", "WEBP")
        self.slider_quality.setEnabled(enabled and is_lossy)
        
        self.chk_subfolders.setEnabled(enabled)
        self.chk_save_frames.setEnabled(enabled)
        self.chk_seeding.setEnabled(enabled)
        self.combo_client.setEnabled(enabled)
        self.btn_preview_sheet.setEnabled(enabled)
        self.btn_history.setEnabled(enabled)

    def set_start_button_enabled(self, enabled: bool):
        """Enable or disable the start processing button smoothly."""
        self.btn_start.setEnabled(enabled)
        self.btn_start.setProperty("active", enabled)
        self.btn_start.setProperty("mode", "normal")
        self.btn_start.setText("Start")
        
        self.btn_start.style().unpolish(self.btn_start)
        self.btn_start.style().polish(self.btn_start)
        
        if not enabled:
            self.btn_start.clearFocus()

    def set_cancel_mode(self):
        """Switch the start button into a Cancel button during processing."""
        self.btn_start.setEnabled(True)
        self.btn_start.setProperty("active", True)
        self.btn_start.setProperty("mode", "cancel")
        self.btn_start.setText("Cancel")
        
        self.btn_start.style().unpolish(self.btn_start)
        self.btn_start.style().polish(self.btn_start)

    def save_preferences(self):
        import configparser
        import os
        import sys

        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            
        ini_path = os.path.join(base_dir, "preferences.ini")

        config = configparser.ConfigParser()
        settings = self.get_sidebar_settings()
        current_client = settings['torrent_client']

        if current_client == "qBittorrent" and self.torrent_client_path:
            self.qbittorrent_path = self.torrent_client_path
        elif current_client == "uTorrent" and self.torrent_client_path:
            self.utorrent_path = self.torrent_client_path
            
        last_dir = getattr(self.parent, "last_browsed_dir", os.path.expanduser("~"))

        config['Preferences'] = {
            'create_contact_sheets': str(settings['create_contact_sheets']),
            'x_tiles': str(settings['x_tiles']),
            'y_tiles': str(settings['y_tiles']),
            'tile_size': str(settings['tile_size']),
            'auto_size': str(settings['auto_size']),
            'orig_size': str(settings['orig_size']),
            'stamp_details': str(settings['stamp_details']),
            'show_filename': str(settings['show_filename']),
            'show_size': str(settings['show_size']),
            'show_res': str(settings['show_res']),
            'show_fps': str(settings['show_fps']),
            'show_duration': str(settings['show_duration']),
            'ignore_first': str(settings['ignore_first']),
            'ignore_last': str(settings['ignore_last']),
            'format': str(settings['format']),
            'quality': str(settings['quality']),
            'save_subfolder': str(settings['save_subfolder']),
            'save_frames': str(settings['save_frames']),
            'save_seeding': str(settings['save_seeding']),
            'torrent_client': str(current_client),
            'qbittorrent_path': str(self.qbittorrent_path),
            'utorrent_path': str(self.utorrent_path),
            'last_browsed_dir': str(last_dir)
        }

        with open(ini_path, 'w') as configfile:
            config.write(configfile)

    def load_preferences(self):
        import configparser
        import os
        import sys

        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            
        ini_path = os.path.join(base_dir, "preferences.ini")
        if not os.path.exists(ini_path):
            return

        config = configparser.ConfigParser()
        config.read(ini_path)

        if "Preferences" not in config:
            return

        pref = config["Preferences"]

        try:
            self.chk_create_contact_sheets.setChecked(pref.getboolean('create_contact_sheets', True))
            self.spin_x_tiles.setValue(pref.getint('x_tiles', 5))
            self.spin_y_tiles.setValue(pref.getint('y_tiles', 4))
            self.spin_tile_size.setValue(pref.getint('tile_size', 512))
            self.chk_automatic.setChecked(pref.getboolean('auto_size', True))
            self.chk_original.setChecked(pref.getboolean('orig_size', False))
            self.chk_stamp_details.setChecked(pref.getboolean('stamp_details', True))
            self.chk_fname.setChecked(pref.getboolean('show_filename', True))
            self.chk_fsize.setChecked(pref.getboolean('show_size', True))
            self.chk_res.setChecked(pref.getboolean('show_res', True))
            self.chk_fps.setChecked(pref.getboolean('show_fps', True))
            self.chk_duration.setChecked(pref.getboolean('show_duration', True))
            self.spin_ignore_first.setValue(pref.getint('ignore_first', 2))
            self.spin_ignore_last.setValue(pref.getint('ignore_last', 0))
            self.combo_format.setCurrentText(pref.get('format', 'JPEG'))
            self.slider_quality.setValue(pref.getint('quality', 65))
            self.chk_subfolders.setChecked(pref.getboolean('save_subfolder', False))
            self.chk_save_frames.setChecked(pref.getboolean('save_frames', False))
            self.chk_seeding.setChecked(pref.getboolean('save_seeding', True))
            
            self.qbittorrent_path = pref.get('qbittorrent_path', '')
            self.utorrent_path = pref.get('utorrent_path', '')
            
            client = pref.get('torrent_client', '')
            if client:
                index = self.combo_client.findText(client)
                if index != -1:
                    self.combo_client.blockSignals(True)
                    self.combo_client.setCurrentIndex(index)
                    self.combo_client.blockSignals(False)
            
            if client == "qBittorrent":
                self.torrent_client_path = self.qbittorrent_path
            elif client == "uTorrent":
                self.torrent_client_path = self.utorrent_path
                
            saved_last_dir = pref.get('last_browsed_dir', '')
            if saved_last_dir and os.path.exists(saved_last_dir):
                if hasattr(self.parent, "last_browsed_dir"):
                    self.parent.last_browsed_dir = saved_last_dir

        except Exception as e:
            print(f"[DEBUG] Error loading preferences: {e}")

    def load_preferences(self):
        import configparser
        import os

        ini_path = os.path.join(os.getcwd(), "preferences.ini")
        if not os.path.exists(ini_path):
            return

        config = configparser.ConfigParser()
        config.read(ini_path)

        if "Preferences" not in config:
            return

        pref = config["Preferences"]

        try:
            self.chk_create_contact_sheets.setChecked(pref.getboolean('create_contact_sheets', True))
            self.spin_x_tiles.setValue(pref.getint('x_tiles', 5))
            self.spin_y_tiles.setValue(pref.getint('y_tiles', 4))
            self.spin_tile_size.setValue(pref.getint('tile_size', 512))
            self.chk_automatic.setChecked(pref.getboolean('auto_size', True))
            self.chk_original.setChecked(pref.getboolean('orig_size', False))
            self.chk_stamp_details.setChecked(pref.getboolean('stamp_details', True))
            self.chk_fname.setChecked(pref.getboolean('show_filename', True))
            self.chk_fsize.setChecked(pref.getboolean('show_size', True))
            self.chk_res.setChecked(pref.getboolean('show_res', True))
            self.chk_fps.setChecked(pref.getboolean('show_fps', True))
            self.chk_duration.setChecked(pref.getboolean('show_duration', True))
            self.spin_ignore_first.setValue(pref.getint('ignore_first', 2))
            self.spin_ignore_last.setValue(pref.getint('ignore_last', 0))
            self.combo_format.setCurrentText(pref.get('format', 'JPEG'))
            self.slider_quality.setValue(pref.getint('quality', 65))
            self.chk_subfolders.setChecked(pref.getboolean('save_subfolder', False))
            self.chk_save_frames.setChecked(pref.getboolean('save_frames', False))
            self.chk_seeding.setChecked(pref.getboolean('save_seeding', True))
            
            # Load individual paths
            self.qbittorrent_path = pref.get('qbittorrent_path', '')
            self.utorrent_path = pref.get('utorrent_path', '')
            
            client = pref.get('torrent_client', '')
            if client:
                index = self.combo_client.findText(client)
                if index != -1:
                    self.combo_client.blockSignals(True)
                    self.combo_client.setCurrentIndex(index)
                    self.combo_client.blockSignals(False)
            
            # Assign active path based on chosen client
            if client == "qBittorrent":
                self.torrent_client_path = self.qbittorrent_path
            elif client == "uTorrent":
                self.torrent_client_path = self.utorrent_path
                
            saved_last_dir = pref.get('last_browsed_dir', '')
            if saved_last_dir and os.path.exists(saved_last_dir):
                if hasattr(self.parent, "last_browsed_dir"):
                    self.parent.last_browsed_dir = saved_last_dir

        except Exception as e:
            print(f"[DEBUG] Error loading preferences: {e}")

    def get_sidebar_settings(self):
        return {
            'create_contact_sheets': self.chk_create_contact_sheets.isChecked(),
            'x_tiles': self.spin_x_tiles.value(),
            'y_tiles': self.spin_y_tiles.value(),
            'tile_size': self.spin_tile_size.value(),
            'auto_size': self.chk_automatic.isChecked(),
            'orig_size': self.chk_original.isChecked(),
            'stamp_details': self.chk_stamp_details.isChecked(),
            'show_filename': self.chk_fname.isChecked(),
            'show_size': self.chk_fsize.isChecked(),
            'show_res': self.chk_res.isChecked(),
            'show_fps': self.chk_fps.isChecked(),
            'show_duration': self.chk_duration.isChecked(),
            'ignore_first': self.spin_ignore_first.value(),
            'ignore_last': self.spin_ignore_last.value(),
            'format': self.combo_format.currentText(),
            'quality': self.slider_quality.value(),
            'save_subfolder': self.chk_subfolders.isChecked(),
            'save_frames': self.chk_save_frames.isChecked(),
            'save_seeding': self.chk_seeding.isChecked(),
            'torrent_client': self.combo_client.currentText(),
            'torrent_client_path': self.torrent_client_path,
            'overwrite': True
        }

    def apply_input_style(self, widget: QWidget):
        widget.setStyleSheet("""
            QWidget {
                background-color: #171a21;
                border: 1px solid #2a2f3a;
                border-radius: 4px;
                padding: 4px;
                color: #d0d4dc;
            }
            QWidget:focus {
                border: 1px solid #3b82f6;
            }
        """)

    def on_torrent_client_changed(self, index):
        client_name = self.combo_client.currentText()
        
        # If blank item is selected
        if not client_name:
            self.torrent_client_path = ""
            self.lbl_file_status.setText("Ready")
            self._last_valid_client = ""
            return

        if client_name in ("qBittorrent", "uTorrent"):
            success = self.resolve_torrent_executable(client_name)
            if success:
                self._last_valid_client = client_name
            else:
                self.combo_client.blockSignals(True)
                if self._last_valid_client:
                    idx = self.combo_client.findText(self._last_valid_client)
                    if idx != -1:
                        self.combo_client.setCurrentIndex(idx)
                else:
                    self.combo_client.setCurrentIndex(0)
                    self.torrent_client_path = ""
                    self.lbl_file_status.setText("No torrent client selected.")
                self.combo_client.blockSignals(False)
                
    def resolve_torrent_executable(self, client_name):
        import os
        from PyQt6.QtWidgets import QFileDialog, QMessageBox

        found_path = ""
        
        if client_name == "qBittorrent" and self.qbittorrent_path and os.path.exists(self.qbittorrent_path):
            found_path = self.qbittorrent_path
        elif client_name == "uTorrent" and self.utorrent_path and os.path.exists(self.utorrent_path):
            found_path = self.utorrent_path

        if not found_path:
            program_files = os.environ.get("ProgramFiles", "C:\\Program Files")
            program_files_x86 = os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")
            app_data = os.environ.get("AppData", os.path.expanduser("~\\AppData\\Roaming"))

            folder_name = "qBittorrent" if client_name == "qBittorrent" else "uTorrent"
            exe_name = "qBittorrent.exe" if client_name == "qBittorrent" else "uTorrent.exe"

            paths_to_check = [
                os.path.join(program_files, folder_name, exe_name),
                os.path.join(program_files_x86, folder_name, exe_name),
                os.path.join(app_data, folder_name, exe_name)
            ]

            for path in paths_to_check:
                if os.path.exists(path):
                    found_path = path
                    break

        if not found_path:
            program_files = os.environ.get("ProgramFiles", "C:\\Program Files")
            exe_name = "qBittorrent.exe" if client_name == "qBittorrent" else "uTorrent.exe"
            QMessageBox.information(
                self, 
                f"{client_name} Not Found", 
                f"Could not locate {exe_name}. Please select it manually."
            )
            file_path, _ = QFileDialog.getOpenFileName(
                self, 
                f"Select {exe_name}", 
                program_files, 
                f"Executables ({exe_name})"
            )
            if file_path:
                found_path = file_path

        if found_path:
            self.torrent_client_path = found_path
            if client_name == "qBittorrent":
                self.qbittorrent_path = found_path
            elif client_name == "uTorrent":
                self.utorrent_path = found_path
                
            self.lbl_file_status.setText(f"Ready")
            return True
        else:
            return False