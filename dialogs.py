from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
)

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
