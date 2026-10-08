import re
import base64
from PyQt6.QtCore import QPoint, QSize, Qt, QUrl, QByteArray, QBuffer, QIODevice
from PyQt6.QtGui import QIcon, QCursor, QTextCursor, QMovie, QTextDocument, QPixmap
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame, QPushButton, QTextEdit, QMenu, QLabel
)
import qtawesome as qta
from constants import FORUM_EMOTICONS
from utils import bbcode_to_html
from widgets import ColorPickerPopup

# Import in-memory assets dictionary
try:
    from assets import ASSETS
except ImportError:
    ASSETS = {}
    
def get_icon_from_asset(path):
    """Loads a QIcon directly from the in-memory ASSETS dictionary."""
    clean_path = path.replace("\\", "/")
    
    if not clean_path.startswith("smilies/") and not clean_path.startswith("assets/"):
        clean_path = f"smilies/{clean_path}"
    
    clean_path = clean_path.replace("assets/", "")

    if clean_path in ASSETS:
        image_bytes = base64.b64decode(ASSETS[clean_path])
        q_bytes = QByteArray(image_bytes)
        pixmap = QPixmap()
        pixmap.loadFromData(q_bytes)
        return QIcon(pixmap)
        
    print(f"Asset not found in ASSETS for icon: {clean_path} (original path: {path})")
    return QIcon()

def get_movie_from_asset(path):
    """Loads a QMovie directly from the in-memory ASSETS dictionary using QBuffer."""
    clean_path = path.replace("\\", "/")
    
    if not clean_path.startswith("smilies/") and not clean_path.startswith("assets/"):
        clean_path = f"smilies/{clean_path}"
    
    clean_path = clean_path.replace("assets/", "")

    if clean_path in ASSETS:
        image_bytes = base64.b64decode(ASSETS[clean_path])
        q_bytes = QByteArray(image_bytes)
        buffer = QBuffer(q_bytes)
        buffer.open(QIODevice.OpenModeFlag.ReadOnly)
        movie = QMovie(buffer)
        movie._buffer = buffer  # Keep buffer alive in memory
        movie.jumpToFrame(0)    # Forces loading the first frame for menu icons
        return movie
        
    print(f"Asset not found in ASSETS: {clean_path} (original path: {path})")
    return None


class EditorPanelComponent(QWidget):
    def __init__(self, parent_window):
        super().__init__()
        self.parent = parent_window
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        editor_container = QWidget()
        editor_layout = QVBoxLayout(editor_container)
        editor_layout.setContentsMargins(4, 4, 4, 4)

        toolbar_frame = QFrame()
        toolbar_frame.setStyleSheet(
            "background-color: #171a21; border-top-left-radius: 6px; border-top-right-radius: 6px;"
        )
        tb_layout = QHBoxLayout(toolbar_frame)
        tb_layout.setContentsMargins(5, 5, 5, 5)

        tool_actions = [
            ("fa6s.bold", "Bold [b]", lambda: self.wrap_selected_text("b")),
            ("fa6s.italic", "Italic [i]", lambda: self.wrap_selected_text("i")),
            ("fa6s.underline", "Underline [u]", lambda: self.wrap_selected_text("u")),
            ("fa6s.strikethrough", "Strikethrough [s]", lambda: self.wrap_selected_text("s")),
            ("fa6s.text-height", "Font Size [size=...]", self.show_size_menu),
            ("fa6s.palette", "Color [color=...]", self.show_color_popup),
            ("fa6s.text-slash", "Clear Format", self.clear_formatting),
            ("fa6s.list-ul", "Bullet List [ul]", lambda: self.wrap_selected_text("ul", is_block=True)),
            ("fa6s.list-ol", "Numbered List [ol]", lambda: self.wrap_selected_text("ol", is_block=True)),
            ("fa6s.quote-left", "Quote [quote]", lambda: self.wrap_selected_text("quote", is_block=True)),
            ("fa6s.file-code", "Code [code]", lambda: self.wrap_selected_text("code", is_block=True)),
            ("fa6s.link", "URL Link [url]", self.insert_url_tag),
            ("fa6s.image", "Image [img]", self.insert_image_tag),
            ("fa6s.align-left", "Align Left [left]", lambda: self.wrap_selected_text("left", is_block=True)),
            ("fa6s.align-center", "Align Center [center]", lambda: self.wrap_selected_text("center", is_block=True)),
            ("fa6s.align-right", "Align Right [right]", lambda: self.wrap_selected_text("right", is_block=True)),
            ("fa6s.face-smile", "Emoticon", self.show_emoticon_popup),
        ]

        for icon_key, tooltip, callback in tool_actions:
            btn = QPushButton()
            btn.setIcon(qta.icon(icon_key, color="#a0a6b5"))
            btn.setIconSize(QSize(14, 14))
            btn.setFixedWidth(26)
            btn.setToolTip(tooltip)
            # Prevent toolbar buttons from capturing tab focus
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.setStyleSheet(
                "QPushButton { background: transparent; border: none; } "
                "QPushButton:hover { background: #2a2f3a; border-radius: 3px; }"
            )
            btn.clicked.connect(callback)
            tb_layout.addWidget(btn)

        tb_layout.addStretch()

        self.editor = QTextEdit()
        self.editor.setMinimumHeight(200)
        self.editor.setStyleSheet("""
            QTextEdit {
                background-color: #0d0f12;
                border: 1px solid #2a2f3a;
                border-bottom-left-radius: 6px;
                border-bottom-right-radius: 6px;
                color: #d0d4dc;
            }
        """)
        
        self.editor.textChanged.connect(self.parent.update_progress)
        self.editor.textChanged.connect(self.update_live_preview)

        editor_layout.addWidget(toolbar_frame)
        editor_layout.addWidget(self.editor)

        preview_container = QWidget()
        preview_layout = QVBoxLayout(preview_container)
        preview_layout.setContentsMargins(4, 4, 4, 4)

        prev_header = QHBoxLayout()
        eye_lbl = QLabel()
        eye_lbl.setPixmap(qta.icon("fa6s.eye", color="#ffffff").pixmap(QSize(14, 14)))
        prev_title = QLabel(" Live preview")
        prev_title.setStyleSheet("color: #ffffff; font-weight: bold;")
        prev_header.addWidget(eye_lbl)
        prev_header.addWidget(prev_title)
        prev_header.addStretch()

        self.preview_box = QTextEdit()
        self.preview_box.setReadOnly(True)
        self.preview_box.setMinimumHeight(200)
        self.preview_box.setPlaceholderText("The rendered description will appear here.")
        self.preview_box.setStyleSheet("""
            QTextEdit {
                background-color: #171a21;
                border: 1px solid #2a2f3a;
                border-radius: 6px;
                color: #d0d4dc;
            }
        """)

        preview_layout.addLayout(prev_header)
        preview_layout.addWidget(self.preview_box)

        layout.addWidget(editor_container)
        layout.addWidget(preview_container)
        
        self._active_movies = []

    def keyPressEvent(self, event):
        # Handle custom shortcuts for bold, italic, and underline formatting tags
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            key = event.key()
            if key == Qt.Key.Key_B:
                self.toggle_formatting_tag("b")
                event.accept()
                return
            elif key == Qt.Key.Key_I:
                self.toggle_formatting_tag("i")
                event.accept()
                return
            elif key == Qt.Key.Key_U:
                self.toggle_formatting_tag("u")
                event.accept()
                return
        
        super().keyPressEvent(event)

    def toggle_formatting_tag(self, tag):
        cursor = self.editor.textCursor()
        selected_text = cursor.selectedText().replace("\u2029", "\n")
        
        open_tag = f"[{tag}]"
        close_tag = f"[/{tag}]"
        
        if selected_text.startswith(open_tag) and selected_text.endswith(close_tag):
            # Remove tags if already wrapped
            unwrapped = selected_text[len(open_tag):-len(close_tag)]
            cursor.insertText(unwrapped)
            cursor.movePosition(QTextCursor.MoveOperation.Left, QTextCursor.MoveMode.MoveAnchor, len(unwrapped))
            cursor.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor, len(unwrapped))
        else:
            # Add tags if not wrapped
            replacement = f"{open_tag}{selected_text}{close_tag}"
            cursor.insertText(replacement)
            if selected_text:
                cursor.movePosition(QTextCursor.MoveOperation.Left, QTextCursor.MoveMode.MoveAnchor, len(close_tag) + len(selected_text))
                cursor.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor, len(selected_text))
            else:
                cursor.movePosition(QTextCursor.MoveOperation.Left, QTextCursor.MoveMode.MoveAnchor, len(close_tag))
                
        self.editor.setTextCursor(cursor)
        self.editor.setFocus()

    def update_live_preview(self):
        raw_text = self.editor.toPlainText()

        for m in self._active_movies:
            m.stop()
        self._active_movies.clear()

        document = self.preview_box.document()
        html_content = bbcode_to_html(raw_text)

        # Process forum emoticons and load their base64 GIFs from ASSETS
        for code, path in FORUM_EMOTICONS.items():
            if code in raw_text or code in html_content:
                clean_path = path.replace("\\", "/")
                if not clean_path.startswith("smilies/") and not clean_path.startswith("assets/"):
                    clean_path = f"smilies/{clean_path}"
                clean_path = clean_path.replace("assets/", "")

                if clean_path in ASSETS:
                    b64_str = ASSETS[clean_path]
                    try:
                        image_bytes = base64.b64decode(b64_str)
                        q_bytes = QByteArray(image_bytes)
                        
                        buffer = QBuffer(q_bytes)
                        buffer._q_bytes = q_bytes 
                        buffer.open(QIODevice.OpenModeFlag.ReadOnly)
                        
                        movie = QMovie(buffer, b"gif")
                        movie._buffer = buffer
                        
                        if movie.isValid():
                            resource_url = QUrl(clean_path)
                            document.addResource(
                                QTextDocument.ResourceType.ImageResource,
                                resource_url,
                                movie.currentPixmap()
                            )
                            movie.frameChanged.connect(lambda _, m=movie, u=resource_url: (
                                document.addResource(QTextDocument.ResourceType.ImageResource, u, m.currentPixmap()),
                                self.preview_box.viewport().update()
                            ))
                            movie.start()
                            self._active_movies.append(movie)

                            img_tag = f'<img src="{clean_path}" style="height: 20px; vertical-align: middle;" />'
                            html_content = html_content.replace(code, img_tag)
                        else:
                            print(f"[DEBUG] QMovie still invalid for: {clean_path}")
                    except Exception as e:
                        print(f"[DEBUG] Failed to decode asset {clean_path}: {e}")
                else:
                    print(f"[DEBUG] Asset NOT FOUND: {clean_path}")

        self.preview_box.setHtml(f'<html><body style="color: #d0d4dc; font-family: sans-serif; font-size: 11pt;">{html_content}</body></html>')

    def wrap_selected_text(self, tag, is_block=False):
        cursor = self.editor.textCursor()
        selected_text = cursor.selectedText().replace("\u2029", "\n")
        has_selection = bool(selected_text)
        
        if tag in ("ul", "ol"):
            lines = selected_text.splitlines() if selected_text else [""]
            items = "".join(f"[li]{line}[/li]" for line in lines)
            replacement = f"[{tag}]{items}[/{tag}]"
            cursor.insertText(replacement)
            move_back = len(f"[/{tag}]") + (len("[/li]") if not has_selection else 0)
        elif is_block:
            replacement = f"[{tag}]\n{selected_text}\n[/{tag}]"
            cursor.insertText(replacement)
            move_back = len(f"[/{tag}]") if not has_selection else len(f"\n[/{tag}]")
        else:
            replacement = f"[{tag}]{selected_text}[/{tag}]"
            cursor.insertText(replacement)
            move_back = len(f"[/{tag}]")
            
        if has_selection:
            cursor.movePosition(QTextCursor.MoveOperation.Left, QTextCursor.MoveMode.MoveAnchor, move_back + len(selected_text))
            cursor.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor, len(selected_text))
        else:
            cursor.movePosition(QTextCursor.MoveOperation.Left, QTextCursor.MoveMode.MoveAnchor, move_back)
            
        self.editor.setTextCursor(cursor)
        self.editor.setFocus()

    def show_size_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet("background-color: #14161c; color: #d0d4dc; border: 1px solid #3a4150;")
        for i in range(1, 8):
            action = menu.addAction(f"Size {i}")
            action.triggered.connect(lambda checked, sz=i: self.insert_size_tag(sz))
        button = self.sender()
        if button:
            menu.exec(button.mapToGlobal(button.rect().bottomLeft()))
        else:
            menu.exec(QCursor.pos())

    def insert_size_tag(self, size_num):
        cursor = self.editor.textCursor()
        selected_text = cursor.selectedText()
        has_selection = bool(selected_text)
        replacement = f"[size={size_num}]{selected_text}[/size]"
        cursor.insertText(replacement)
        
        if has_selection:
            cursor.movePosition(QTextCursor.MoveOperation.Left, QTextCursor.MoveMode.MoveAnchor, len("[/size]") + len(selected_text))
            cursor.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor, len(selected_text))
        else:
            cursor.movePosition(QTextCursor.MoveOperation.Left, QTextCursor.MoveMode.MoveAnchor, len("[/size]"))
            
        self.editor.setTextCursor(cursor)
        self.editor.setFocus()

    def show_color_popup(self):
        btn = self.sender()
        pos = btn.mapToGlobal(QPoint(0, btn.height()))
        self.color_popup = ColorPickerPopup(self.apply_color_tag, self)
        self.color_popup.move(pos)
        self.color_popup.show()

    def apply_color_tag(self, hex_color):
        cursor = self.editor.textCursor()
        selected_text = cursor.selectedText()
        has_selection = bool(selected_text)
        replacement = f"[color={hex_color}]{selected_text}[/color]"
        cursor.insertText(replacement)
        
        if has_selection:
            cursor.movePosition(QTextCursor.MoveOperation.Left, QTextCursor.MoveMode.MoveAnchor, len("[/color]") + len(selected_text))
            cursor.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor, len(selected_text))
        else:
            cursor.movePosition(QTextCursor.MoveOperation.Left, QTextCursor.MoveMode.MoveAnchor, len("[/color]"))
            
        self.editor.setTextCursor(cursor)
        self.editor.setFocus()

    def show_emoticon_popup(self):
        menu = QMenu(self)
        menu.setStyleSheet("background-color: #14161c; color: #d0d4dc; border: 1px solid #3a4150;")
        for code, path in sorted(FORUM_EMOTICONS.items(), key=lambda x: x[0]):
            icon = get_icon_from_asset(path)
            action = menu.addAction(icon, code)
            action.triggered.connect(lambda checked, c=code: self.insert_emoticon_code(c))
        button = self.sender()
        if button:
            menu.exec(button.mapToGlobal(button.rect().bottomLeft()))
        else:
            menu.exec(QCursor.pos())

    def insert_emoticon_code(self, code):
        cursor = self.editor.textCursor()
        cursor.insertText(f" {code} ")
        self.editor.setFocus()

    def insert_url_tag(self):
        cursor = self.editor.textCursor()
        selected_text = cursor.selectedText()
        has_selection = bool(selected_text)
        url_text = selected_text if selected_text else "url"
        replacement = f"[url=https://example.com]{url_text}[/url]"
        cursor.insertText(replacement)
        
        if has_selection:
            cursor.movePosition(QTextCursor.MoveOperation.Left, QTextCursor.MoveMode.MoveAnchor, len("[/url]") + len(url_text))
            cursor.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor, len(url_text))
        else:
            cursor.movePosition(QTextCursor.MoveOperation.Left, QTextCursor.MoveMode.MoveAnchor, len("[/url]"))
            cursor.movePosition(QTextCursor.MoveOperation.Left, QTextCursor.MoveMode.KeepAnchor, len(url_text))
            
        self.editor.setTextCursor(cursor)
        self.editor.setFocus()

    def insert_image_tag(self):
        cursor = self.editor.textCursor()
        selected_text = cursor.selectedText()
        has_selection = bool(selected_text)
        img_url = selected_text if selected_text else "https://example.com/image.jpg"
        replacement = f"[img=]{img_url}[/img]"
        cursor.insertText(replacement)
        
        if has_selection:
            cursor.movePosition(QTextCursor.MoveOperation.Left, QTextCursor.MoveMode.MoveAnchor, len("[/img]") + len(img_url))
            cursor.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor, len(img_url))
        else:
            cursor.movePosition(QTextCursor.MoveOperation.Left, QTextCursor.MoveMode.MoveAnchor, len("[/img]") + len(img_url) + len("[/img]"))
            cursor.movePosition(QTextCursor.MoveOperation.Left, QTextCursor.MoveMode.MoveAnchor, len("[/img="))
            
        self.editor.setTextCursor(cursor)
        self.editor.setFocus()

    def clear_formatting(self):
        cursor = self.editor.textCursor()
        selected_text = cursor.selectedText()
        clean_text = re.sub(r"\[/?\w+(?:=[^\]]+)?\]", "", selected_text)
        cursor.insertText(clean_text)
        self.editor.setFocus()