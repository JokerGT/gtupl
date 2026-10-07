from PyQt6.QtCore import Qt, pyqtSignal, QSize, QUrl
from PyQt6.QtGui import QFont, QDesktopServices
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QListWidget, QListWidgetItem, QFrame
)
import qtawesome as qta
import json
import base64
import os

class HistoryCipher:
    def __init__(self, secret_key: bytes = b"gtupl_secure_history_key_2026"):
        self.secret_key = secret_key

    def encrypt(self, plain_text: str) -> str:
        data = plain_text.encode("utf-8")
        key_len = len(self.secret_key)
        encrypted_bytes = bytearray(
            data[i] ^ self.secret_key[i % key_len] for i in range(len(data))
        )
        return base64.b64encode(encrypted_bytes).decode("utf-8")

    def decrypt(self, cipher_text: str) -> str:
        try:
            decoded_bytes = base64.b64decode(cipher_text.encode("utf-8"))
            key_len = len(self.secret_key)
            decrypted_bytes = bytearray(
                decoded_bytes[i] ^ self.secret_key[i % key_len] for i in range(len(decoded_bytes))
            )
            return decrypted_bytes.decode("utf-8")
        except Exception:
            return "[]"


class HistoryPanelComponent(QWidget):
    # Custom signal to notify sidebar to switch back to the main view
    back_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cipher = HistoryCipher()
        self.history_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "history.enc")
        self.runs_data = []

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        history_frame = QFrame()
        history_frame.setStyleSheet("""
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
        """)
        
        frame_layout = QVBoxLayout(history_frame)
        frame_layout.setContentsMargins(10, 30, 10, 30)
        frame_layout.setSpacing(8)

        # --- Header (Back Button + Title) ---
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)

        self.btn_back = QPushButton()
        self.btn_back.setIcon(qta.icon("fa6s.arrow-left", color="#d0d4dc"))
        self.btn_back.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_back.setFixedSize(32, 32)
        self.btn_back.setStyleSheet("""
            QPushButton {
                background-color: #171a21;
                border: 1px solid #3a4150;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #2a2f3d; border-color: #3b82f6; }
        """)
        self.btn_back.clicked.connect(self.back_requested.emit)
        header_layout.addWidget(self.btn_back)

        lbl_title = QLabel("Previous Runs")
        lbl_title.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        header_layout.addWidget(lbl_title)
        header_layout.addStretch()

        frame_layout.addLayout(header_layout)

        # --- History List Widget ---
        self.list_history = QListWidget()
        self.list_history.setStyleSheet("""
            QListWidget {
                background-color: #14161c;
                border: 1px solid #2a2f3a;
                border-radius: 4px;
                color: #d0d4dc;
                padding: 4px;
            }
            QListWidget::item {
                padding: 4px;
                border-bottom: 1px solid #1e222b;
            }
        """)
        frame_layout.addWidget(self.list_history)

        # Load encrypted history from disk
        self.load_history()

        main_layout.addWidget(history_frame)

    def load_history(self):
        """Loads and decrypts execution history from local storage."""
        self.runs_data = []
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    encrypted_content = f.read()
                decrypted_json = self.cipher.decrypt(encrypted_content)
                self.runs_data = json.loads(decrypted_json)
            except Exception as e:
                print(f"[HISTORY ERROR] Failed to load/decrypt history: {e}")
                self.runs_data = []

        self.list_history.clear()
        for run in self.runs_data:
            # FIX: Pass redirect_url from the stored run dictionary
            self._add_item_to_ui(
                run.get("start_time"), 
                run.get("title"), 
                run.get("status"), 
                run.get("redirect_url", "")
            )

    def save_history(self):
        """Encrypts and saves execution history to local storage."""
        try:
            raw_json = json.dumps(self.runs_data)
            encrypted_content = self.cipher.encrypt(raw_json)
            with open(self.history_file, "w", encoding="utf-8") as f:
                f.write(encrypted_content)
        except Exception as e:
            print(f"[HISTORY ERROR] Failed to save/encrypt history: {e}")

    def add_run(self, start_time: str, torrent_title: str, status: str, redirect_url: str = ""):
        run_entry = {
            "start_time": start_time,
            "title": torrent_title,
            "status": status.lower(),
            "redirect_url": redirect_url
        }
        self.runs_data.insert(0, run_entry)
        self.save_history()
        self._add_item_to_ui(start_time, torrent_title, status, redirect_url, prepend=True)

    def _add_item_to_ui(self, start_time: str, torrent_title: str, status: str, redirect_url: str = "", prepend: bool = False):
        """Constructs the custom widget matching: {task start time and torrent title} {status icon} {remove button}"""
        item_widget = QWidget()
        
        # --- Add Tooltip to the custom item widget ---
        item_widget.setToolTip(f"Status: {status.capitalize()}")
        
        row_layout = QHBoxLayout(item_widget)
        row_layout.setContentsMargins(6, 6, 6, 6)
        row_layout.setSpacing(8)

        # 1. Task Start Time and Torrent Title Label
        # Insert zero-width spaces (\u200b) between characters so long unbroken words wrap anywhere
        wrapped_title = "\u200b".join(torrent_title)
        display_text = f"{start_time} - {wrapped_title}"
        
        lbl_info = QLabel(display_text)
        lbl_info.setFont(QFont("Arial", 9))
        lbl_info.setStyleSheet("color: #d0d4dc; background: transparent;")
        lbl_info.setWordWrap(True)
        
        # Determine width ensuring it scales with the list widget but NEVER goes beyond 350px
        max_allowed_width = 350
        list_width = self.list_history.width()
        if list_width <= 90:
            list_width = 400  # Fallback width when the history panel is hidden
        available_width = list_width - 90
        if available_width <= 0 or available_width > max_allowed_width:
            available_width = max_allowed_width
            
        lbl_info.setMaximumWidth(available_width)
        
        row_layout.addWidget(lbl_info, stretch=1)

        # 2. Status Icon
        lbl_status = QLabel()
        lbl_status.setFixedSize(20, 20)
        lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        if status == "success":
            btn_status = QPushButton()
            btn_status.setIcon(qta.icon("fa6s.download", color="#22c55e"))
            btn_status.setFixedSize(24, 24)
            btn_status.setCursor(Qt.CursorShape.PointingHandCursor)
            
            # Construct the full URL using the base domain and relative redirect_url
            base_domain = "https://www.gaytor.rent"
            full_url = redirect_url
            if redirect_url:
                if redirect_url.startswith("/"):
                    full_url = base_domain + redirect_url
                elif not redirect_url.startswith(("http://", "https://")):
                    full_url = base_domain + "/" + redirect_url

            tooltip_text = "Status: Success"
            if full_url:
                tooltip_text += f" (Click to open download page)\n{full_url}"
                
                def handle_click(checked=False, u=full_url):
                    print(f"[HISTORY DEBUG] Button clicked! Opening full URL: {u}")
                    qurl = QUrl(u)
                    success = QDesktopServices.openUrl(qurl)
                    # print(f"[HISTORY DEBUG] QDesktopServices.openUrl result: {success}")
                
                btn_status.clicked.connect(handle_click)
            
            btn_status.setToolTip(tooltip_text)
            btn_status.setStyleSheet("""
                QPushButton { background-color: transparent; border: none; border-radius: 4px; }
                QPushButton:hover { background-color: #2a2f3d; }
            """)
                
            row_layout.addWidget(btn_status)
        else:
            lbl_status = QLabel()
            lbl_status.setFixedSize(20, 20)
            lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            if status == "failed":
                lbl_status.setPixmap(qta.icon("fa6s.triangle-exclamation", color="#ef4444").pixmap(QSize(16, 16)))
                lbl_status.setToolTip("Status: Failed")
            else:
                lbl_status.setPixmap(qta.icon("fa6s.ban", color="#dddddd").pixmap(QSize(16, 16)))
                lbl_status.setToolTip("Status: Canceled")
                
            row_layout.addWidget(lbl_status)

        # 3. Remove Button
        btn_remove = QPushButton()
        btn_remove.setIcon(qta.icon("fa6s.trash-can", color="#ef4444"))
        btn_remove.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_remove.setFixedSize(28, 28)
        btn_remove.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #2a2f3d;
            }
        """)
        
        list_item = QListWidgetItem()
        
        # Force layout adjustment so the item size hint accommodates the full wrapped height
        item_widget.adjustSize()
        list_item.setSizeHint(item_widget.sizeHint())

        def remove_self():
            row = self.list_history.row(list_item)
            if row != -1:
                self.list_history.takeItem(row)
                if row < len(self.runs_data):
                    self.runs_data.pop(row)
                    self.save_history()

        btn_remove.clicked.connect(remove_self)
        row_layout.addWidget(btn_remove)

        if prepend:
            self.list_history.insertItem(0, list_item)
        else:
            self.list_history.addItem(list_item)

        self.list_history.setItemWidget(list_item, item_widget)