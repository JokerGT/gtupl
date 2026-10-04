import re
from PyQt6.QtCore import QPoint, QSize, Qt
from PyQt6.QtGui import QIcon, QCursor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame, QPushButton, QTextEdit, QMenu, QLabel
)
import qtawesome as qta
from constants import FORUM_EMOTICONS
from utils import bbcode_to_html
from widgets import ColorPickerPopup

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

    def update_live_preview(self):
        raw_text = self.editor.toPlainText()
        html_content = bbcode_to_html(raw_text)
        self.preview_box.setHtml(f'<html><body style="color: #d0d4dc; font-family: sans-serif; font-size: 11pt;">{html_content}</body></html>')

    def wrap_selected_text(self, tag, is_block=False):
        cursor = self.editor.textCursor()
        # Normalize QTextEdit paragraph separators to standard newlines
        selected_text = cursor.selectedText().replace("\u2029", "\n")
        
        if tag in ("ul", "ol"):
            lines = selected_text.splitlines() if selected_text else [""]
            items = "".join(f"[li]{line}[/li]" for line in lines)
            replacement = f"[{tag}]{items}[/{tag}]"
        elif is_block:
            replacement = f"[{tag}]\n{selected_text}\n[/{tag}]"
        else:
            replacement = f"[{tag}]{selected_text}[/tag]"
            
        cursor.insertText(replacement)

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
        cursor.insertText(f"[size={size_num}]{selected_text}[/size]")

    def show_color_popup(self):
        btn = self.sender()
        pos = btn.mapToGlobal(QPoint(0, btn.height()))
        self.color_popup = ColorPickerPopup(self.apply_color_tag, self)
        self.color_popup.move(pos)
        self.color_popup.show()

    def apply_color_tag(self, hex_color):
        cursor = self.editor.textCursor()
        selected_text = cursor.selectedText()
        cursor.insertText(f"[color={hex_color}]{selected_text}[/color]")

    def show_emoticon_popup(self):
        menu = QMenu(self)
        menu.setStyleSheet("background-color: #14161c; color: #d0d4dc; border: 1px solid #3a4150;")
        for code, path in sorted(FORUM_EMOTICONS.items(), key=lambda x: x[0]):
            icon = QIcon(path)
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

    def insert_url_tag(self):
        cursor = self.editor.textCursor()
        selected_text = cursor.selectedText()
        url_text = selected_text if selected_text else "url"
        cursor.insertText(f"[url=https://example.com]{url_text}[/url]")

    def insert_image_tag(self):
        cursor = self.editor.textCursor()
        selected_text = cursor.selectedText()
        img_url = selected_text if selected_text else "https://example.com/image.jpg"
        cursor.insertText(f"[img=]{img_url}[/img]")

    def clear_formatting(self):
        cursor = self.editor.textCursor()
        selected_text = cursor.selectedText()
        clean_text = re.sub(r"\[/?\w+(?:=[^\]]+)?\]", "", selected_text)
        cursor.insertText(clean_text)