from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPixmap, QCursor, QFont
from PyQt6.QtWidgets import QApplication, QDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea, QVBoxLayout
from styles import apply_input_style

class ContactSheetPreviewDialog(QDialog):
    def __init__(self, pil_image, parent=None):
        super().__init__(
            parent,
            Qt.WindowType.Window
            | Qt.WindowType.WindowMaximizeButtonHint
            | Qt.WindowType.WindowMinimizeButtonHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        self.setWindowTitle("Contact Sheet Preview")

        if pil_image.mode == "RGBA":
            img_format = QImage.Format.Format_RGBA8888
        else:
            img_format = QImage.Format.Format_RGB888
            
        w, h = pil_image.size
        bytes_data = pil_image.tobytes("raw", pil_image.mode)
        q_img = QImage(bytes_data, w, h, w * len(pil_image.mode), img_format)
        self.original_pixmap = QPixmap.fromImage(q_img)

        screen_geo = QApplication.primaryScreen().availableGeometry()
        self.resize(int(screen_geo.width() * 0.85), int(screen_geo.height() * 0.85))
        self.is_fit_mode = False
        self.init_ui()
        self.show_original_size()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(10, 8, 10, 8)
        toolbar.setSpacing(8)
        
        self.btn_fit = QPushButton("Scale to Fit")
        self.btn_fit.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_fit.setStyleSheet(self.get_toolbar_btn_style())
        self.btn_fit.clicked.connect(self.scale_to_fit)

        self.btn_orig = QPushButton("Original Size")
        self.btn_orig.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_orig.setStyleSheet(self.get_toolbar_btn_style())
        self.btn_orig.clicked.connect(self.show_original_size)

        toolbar.addWidget(self.btn_fit)
        toolbar.addWidget(self.btn_orig)
        toolbar.addStretch()

        toolbar_frame = QFrame()
        toolbar_frame.setLayout(toolbar)
        toolbar_frame.setStyleSheet("background-color: #171a21; border-bottom: 1px solid #2a2f3a;")
        layout.addWidget(toolbar_frame)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_area.setStyleSheet("background-color: #0d0f12; border: none;")

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_area.setWidget(self.image_label)

        layout.addWidget(self.scroll_area)

    def get_toolbar_btn_style(self):
        return """
            QPushButton {
                background-color: #1e222b;
                border: 1px solid #3a4150;
                color: #d0d4dc;
                border-radius: 4px;
                padding: 5px 12px;
                font-size: 11px;
            }
            QPushButton:hover { background-color: #2a2f3d; border-color: #3b82f6; }
        """

    def scale_to_fit(self):
        self.is_fit_mode = True
        viewport_size = self.scroll_area.viewport().size()
        scaled = self.original_pixmap.scaled(
            viewport_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.image_label.setPixmap(scaled)

    def show_original_size(self):
        self.is_fit_mode = False
        self.image_label.setPixmap(self.original_pixmap)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if getattr(self, "is_fit_mode", False):
            self.scale_to_fit()

class ApiKeyDialog(QDialog):
    """Asks for a personal API key.

    `verify` is called with the entered key and returns None once the key has
    been accepted and saved, or a message explaining what went wrong.
    """

    def __init__(self, verify, notice="", prefill=None, parent=None):
        super().__init__(parent)
        self.verify = verify
        self.setWindowTitle("Gaytor.rent Uploader")
        self.setMinimumWidth(480)
        self.setStyleSheet("""
            QDialog { background-color: #17191e; }
            QLabel { color: #d0d4dc; background: transparent; }
        """)
        self.init_ui(notice, prefill)

    def init_ui(self, notice, prefill):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)

        title = QLabel("Log in with an API key")
        title.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        title.setStyleSheet("color: #ffffff;")
        layout.addWidget(title)

        info = QLabel(
            "Paste a personal API key to connect the uploader to your account. "
            "You can create one on gaytor.rent under "
            "<b>Settings \u2192 Account \u2192 API keys</b>.<br><br>"
            "The key can only be used for uploads, and you can revoke it there "
            "at any time."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("gtk_...")
        self.key_input.setEchoMode(QLineEdit.EchoMode.Password)
        apply_input_style(self.key_input)
        if prefill:
            self.key_input.setText(prefill)
            self.key_input.selectAll()
        layout.addWidget(self.key_input)

        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        self.status_label.setVisible(False)
        layout.addWidget(self.status_label)
        if notice:
            self.show_status(notice, is_error=True)

        buttons = QHBoxLayout()
        buttons.addStretch()

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_cancel.setAutoDefault(False)
        self.btn_cancel.setStyleSheet("""
            QPushButton { background-color: #1e222b; border: 1px solid #3a4150; color: #d0d4dc; border-radius: 4px; padding: 6px 12px; }
            QPushButton:hover { background-color: #2a2f3d; }
        """)
        self.btn_cancel.clicked.connect(self.reject)

        # Default button, so pressing Enter in the key field logs in
        self.btn_login = QPushButton("Log in")
        self.btn_login.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_login.setDefault(True)
        self.btn_login.setStyleSheet("""
            QPushButton { background-color: #2ea44f; border: 1px solid #2ecc71; color: white; border-radius: 4px; padding: 6px 12px; font-weight: bold; }
            QPushButton:hover { background-color: #27ae60; }
            QPushButton:disabled { background-color: #14161c; border: 1px solid #2a2f3a; color: #4b5563; }
        """)
        self.btn_login.clicked.connect(self.submit)

        buttons.addWidget(self.btn_cancel)
        buttons.addWidget(self.btn_login)
        layout.addLayout(buttons)

    def show_status(self, text, is_error=False):
        color = "#ef4444" if is_error else "#7b8394"
        self.status_label.setStyleSheet(f"color: {color}; font-size: 11px;")
        self.status_label.setText(text)
        self.status_label.setVisible(True)

    def set_busy(self, busy):
        self.key_input.setEnabled(not busy)
        self.btn_login.setEnabled(not busy)
        self.btn_cancel.setEnabled(not busy)
        if busy:
            self.show_status("Checking the key...")
            QApplication.setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor))
            QApplication.processEvents()
        else:
            QApplication.restoreOverrideCursor()

    def submit(self):
        api_key = self.key_input.text().strip()
        if not api_key:
            self.show_status("Please paste your API key first.", is_error=True)
            return

        self.set_busy(True)
        try:
            error = self.verify(api_key)
        except Exception as e:
            error = f"Unexpected error: {e}"
        finally:
            self.set_busy(False)

        if error:
            self.show_status(error, is_error=True)
            self.key_input.setFocus()
            self.key_input.selectAll()
        else:
            self.accept()
