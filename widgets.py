import os
import time
import base64
import io

from PyQt6.QtCore import QByteArray, QMimeData, QPoint, QSize, Qt
from PyQt6.QtGui import QCursor, QDrag, QDragEnterEvent, QDragMoveEvent, QDropEvent, QIcon, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from constants import SCEEDITOR_COLORS

try:
    from assets import ASSETS
except ImportError:
    ASSETS = {}

def get_pixmap_from_asset(filename):
    """Loads a QPixmap directly from the in-memory ASSETS dictionary without disk access."""
    clean_name = filename.replace("assets/", "").replace("assets\\", "")
    if clean_name in ASSETS:
        image_bytes = base64.b64decode(ASSETS[clean_name])
        q_bytes = QByteArray(image_bytes)
        pixmap = QPixmap()
        pixmap.loadFromData(q_bytes)
        return pixmap
    return None

class PopupWidget(QWidget):
    def __init__(self, parent_dropdown, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.parent_dropdown = parent_dropdown

    def closeEvent(self, event):
        self.parent_dropdown._last_closed_time = time.time()
        super().closeEvent(event)


class CustomHintWidget(QLabel):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setWindowFlags(Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setStyleSheet("""
            background-color: #1e222b;
            color: #d0d4dc;
            border: 1px solid #3a4150;
            padding: 5px 8px;
            border-radius: 4px;
            font-size: 11px;
        """)


class CategoryTile(QFrame):
    def __init__(
        self, cat_name, cat_id, callback, is_selected=False, is_disabled=False, is_special=False, parent=None
    ):
        super().__init__(parent)
        self.cat_name = cat_name
        self.cat_id = cat_id
        self.callback = callback
        self.is_disabled = is_disabled
        self.is_special = is_special
        self.hint_widget = None

        if is_disabled:
            self.setCursor(Qt.CursorShape.ForbiddenCursor)
        else:
            self.setCursor(Qt.CursorShape.PointingHandCursor)

        if is_special:
            self.setMouseTracking(True)

        self.setFixedSize(110, 92)

        if is_disabled:
            base_style = """
                QFrame {
                    background: rgba(20, 22, 28, 0.6);
                    border-radius: 4px;
                }
            """
        elif is_selected:
            base_style = """
                QFrame {
                    background-color: #1e3a8a;
                    border: 1px solid #3b82f6;
                    border-radius: 4px;
                }
            """
        elif is_special:
            base_style = """
                QFrame {
                    background-color: #231c18;
                    border: 1px solid #583423;
                    border-radius: 4px;
                }
                QFrame:hover {
                    background-color: #2b2420;
                }
            """
        else:
            base_style = """
                QFrame {
                    background: transparent;
                    border-radius: 4px;
                }
                QFrame:hover {
                    background-color: #222733;
                }
            """
        self.setStyleSheet(base_style)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        img_lbl = QLabel()
        img_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        img_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        pixmap = get_pixmap_from_asset(f"{cat_id}.jpg")

        if pixmap and not pixmap.isNull():
            scaled_pixmap = pixmap.scaled(
                40,
                40,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            if is_disabled:
                img_lbl.setPixmap(scaled_pixmap)
                img_lbl.setStyleSheet("opacity: 0.3;")
            else:
                img_lbl.setPixmap(scaled_pixmap)
        else:
            img_lbl.setText("No Img")
            img_lbl.setStyleSheet(
                "color: #7b8394; font-size: 9px; background: #2a2f3a;"
            )
            img_lbl.setFixedSize(40, 40)

        text_color = "#4b5563" if is_disabled else ("#ffffff" if is_selected else "#d0d4dc")
        text_lbl = QLabel(cat_name)
        text_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        text_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        text_lbl.setStyleSheet(
            f"color: {text_color}; font-size: 10px; background: transparent; border: none;"
        )

        layout.addWidget(img_lbl, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(text_lbl, alignment=Qt.AlignmentFlag.AlignCenter)

    def enterEvent(self, event):
        super().enterEvent(event)
        if self.is_special and not self.hint_widget:
            hint_text = "Categories that are obligatory if your torrent contains that type of content"
            self.hint_widget = CustomHintWidget(hint_text)
            self.hint_widget.move(QCursor.pos() + QPoint(12, 12))
            self.hint_widget.show()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        if self.hint_widget:
            self.hint_widget.close()
            self.hint_widget = None

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        if self.is_special and self.hint_widget:
            self.hint_widget.move(QCursor.pos() + QPoint(12, 12))

    def mousePressEvent(self, event):
        if not self.is_disabled and event.button() == Qt.MouseButton.LeftButton:
            if self.hint_widget:
                self.hint_widget.close()
                self.hint_widget = None
            self.callback(self.cat_name, self.cat_id)


class CategoryDropdown(QPushButton):
    def __init__(self, categories_dict, placeholder="Select category...", special_cats=None, parent=None):
        super().__init__(parent)
        self.special_cats = special_cats or {}
        sorted_special = sorted(self.special_cats.items(), key=lambda x: x[0])
        sorted_regular = sorted([item for item in categories_dict.items() if item[0] not in self.special_cats], key=lambda x: x[0])
        self.sorted_categories = sorted_special + sorted_regular
        
        self.selected_name = None
        self.selected_id = None
        self.placeholder = placeholder
        self.on_selection_changed = None
        self.popup = None
        self._last_closed_time = 0

        self.setText(f"  {placeholder}")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("""
            QPushButton {
                background-color: #171a21;
                border: 1px solid #2a2f3a;
                border-radius: 4px;
                padding: 4px 4px;
                color: #d0d4dc;
                text-align: left;
            }
            QPushButton:hover {
                border: 1px solid #3b82f6;
            }
        """)
        self.clicked.connect(self.on_button_clicked)

    def get_excluded_id(self):
        return None

    def on_button_clicked(self):
        if time.time() - self._last_closed_time < 0.2:
            return
        if self.popup and self.popup.isVisible():
            self.popup.close()
            self.popup = None
        else:
            self.show_popup()

    def show_popup(self):
        if self.popup and self.popup.isVisible():
            self.popup.close()

        self.popup = PopupWidget(
            self,
            None,
            Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint,
        )
        self.popup.setStyleSheet(
            "background-color: #14161c; border: 1px solid #3a4150; border-radius: 6px;"
        )

        layout = QVBoxLayout(self.popup)
        layout.setContentsMargins(4, 4, 4, 4)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical { border: none; background-color: transparent; width: 8px; margin: 0px; }
            QScrollBar::handle:vertical { background-color: #3a4150; min-height: 20px; border-radius: 4px; }
            QScrollBar::handle:vertical:hover { background-color: #4b5563; }
            QScrollBar::handle:vertical:pressed { background-color: #3b82f6; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { border: none; background: none; height: 0px; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
        """)
        scroll.setFixedHeight(600)

        grid_widget = QWidget()
        grid_widget.setStyleSheet("background: transparent;")
        grid_layout = QGridLayout(grid_widget)
        grid_layout.setSpacing(2)

        excluded_id = self.get_excluded_id()
        col_count = 8
        for index, (cat_name, cat_id) in enumerate(self.sorted_categories):
            row = index // col_count
            col = index % col_count
            is_sel = (cat_id == self.selected_id)
            is_dis = (cat_id == excluded_id)
            is_spec = (cat_name in self.special_cats)
            
            tile = CategoryTile(
                cat_name, cat_id, self.on_tile_selected, is_selected=is_sel, is_disabled=is_dis, is_special=is_spec
            )
            grid_layout.addWidget(tile, row, col)

        scroll.setWidget(grid_widget)
        layout.addWidget(scroll)

        btn_width = self.width()
        popup_width = max(btn_width, 740)
        global_pos = self.mapToGlobal(QPoint(0, self.height() + 4))
        self.popup.setGeometry(global_pos.x(), global_pos.y(), popup_width, 305)
        self.popup.show()

    def on_tile_selected(self, cat_name, cat_id):
        parent_window = self.window()
        if hasattr(parent_window, "sub_cat_combo") and cat_id in parent_window.sub_cat_combo.selected_items:
            del parent_window.sub_cat_combo.selected_items[cat_id]
            parent_window.sub_cat_combo.update_display_text()

        self.selected_name = cat_name
        self.selected_id = cat_id

        pixmap = get_pixmap_from_asset(f"{cat_id}.jpg")
        if pixmap and not pixmap.isNull():
            self.setIcon(QIcon(pixmap))
            self.setIconSize(QSize(20, 20))
        self.setText(f"  {cat_name}")

        if self.popup:
            self.popup.close()
            self.popup = None

        if self.on_selection_changed:
            self.on_selection_changed()


class MultiCategoryDropdown(QPushButton):
    def __init__(self, categories_dict, placeholder="Select category...", special_cats=None, parent=None):
        super().__init__(parent)
        self.special_cats = special_cats or {}
        sorted_special = sorted(self.special_cats.items(), key=lambda x: x[0])
        sorted_regular = sorted([item for item in categories_dict.items() if item[0] not in self.special_cats], key=lambda x: x[0])
        self.sorted_categories = sorted_special + sorted_regular
        
        self.selected_items = {}
        self.placeholder = placeholder
        self.on_selection_changed = None
        self.popup = None
        self._last_closed_time = 0

        self.update_display_text()
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("""
            QPushButton {
                background-color: #171a21;
                border: 1px solid #2a2f3a;
                border-radius: 4px;
                padding: 4px 4px;
                color: #d0d4dc;
                text-align: left;
            }
            QPushButton:hover {
                border: 1px solid #3b82f6;
            }
        """)
        self.clicked.connect(self.on_button_clicked)

    def get_excluded_id(self):
        return None

    def update_display_text(self):
        if not self.selected_items:
            self.setText(f"  {self.placeholder}")
            self.setIcon(QIcon())
        else:
            names = list(self.selected_items.values())
            self.setText(f"  {', '.join(names)}")
            first_id = list(self.selected_items.keys())[0]
            
            pixmap = get_pixmap_from_asset(f"{first_id}.jpg")
            if pixmap and not pixmap.isNull():
                self.setIcon(QIcon(pixmap))
                self.setIconSize(QSize(20, 20))

    def on_button_clicked(self):
        if time.time() - self._last_closed_time < 0.2:
            return
        if self.popup and self.popup.isVisible():
            self.popup.close()
            self.popup = None
        else:
            self.show_popup()

    def show_popup(self):
        if self.popup and self.popup.isVisible():
            self.popup.close()

        self.popup = PopupWidget(
            self,
            None,
            Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint,
        )
        self.popup.setStyleSheet(
            "background-color: #14161c; border: 1px solid #3a4150; border-radius: 6px;"
        )

        self.popup_layout = QVBoxLayout(self.popup)
        self.popup_layout.setContentsMargins(4, 4, 4, 4)

        self.refresh_popup_content()

        btn_width = self.width()
        popup_width = max(btn_width, 740)
        global_pos = self.mapToGlobal(QPoint(0, self.height() + 4))
        self.popup.setGeometry(global_pos.x(), global_pos.y(), popup_width, 305)
        self.popup.show()

    def refresh_popup_content(self):
        while self.popup_layout.count():
            item = self.popup_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical { border: none; background-color: transparent; width: 8px; margin: 0px; }
            QScrollBar::handle:vertical { background-color: #3a4150; min-height: 20px; border-radius: 4px; }
            QScrollBar::handle:vertical:hover { background-color: #4b5563; }
            QScrollBar::handle:vertical:pressed { background-color: #3b82f6; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { border: none; background: none; height: 0px; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
        """)
        scroll.setFixedHeight(600)

        grid_widget = QWidget()
        grid_widget.setStyleSheet("background: transparent;")
        grid_layout = QGridLayout(grid_widget)
        grid_layout.setSpacing(2)

        excluded_id = self.get_excluded_id()
        col_count = 8
        for index, (cat_name, cat_id) in enumerate(self.sorted_categories):
            row = index // col_count
            col = index % col_count
            is_sel = (cat_id in self.selected_items)
            is_dis = (cat_id == excluded_id) or (not is_sel and len(self.selected_items) >= 4)
            is_spec = (cat_name in self.special_cats)
            
            tile = CategoryTile(
                cat_name, cat_id, self.on_tile_clicked, is_selected=is_sel, is_disabled=is_dis, is_special=is_spec
            )
            grid_layout.addWidget(tile, row, col)

        scroll.setWidget(grid_widget)
        self.popup_layout.addWidget(scroll)

    def on_tile_clicked(self, cat_name, cat_id):
        if cat_id in self.selected_items:
            del self.selected_items[cat_id]
        else:
            if len(self.selected_items) < 4:
                self.selected_items[cat_id] = cat_name

        self.update_display_text()
        self.refresh_popup_content()

        if self.on_selection_changed:
            self.on_selection_changed()


class ColorPickerPopup(QWidget):
    def __init__(self, callback, parent=None):
        super().__init__(parent, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.callback = callback
        self.setStyleSheet("background-color: #14161c; border: 1px solid #3a4150; border-radius: 6px;")
        
        layout = QGridLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(2)

        for r_idx, row in enumerate(SCEEDITOR_COLORS):
            for c_idx, hex_color in enumerate(row):
                btn = QPushButton()
                btn.setFixedSize(20, 20)
                btn.setStyleSheet(f"background-color: {hex_color}; border: 1px solid #2a2f3a; border-radius: 2px;")
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.clicked.connect(lambda checked, c=hex_color: self.select_color(c))
                layout.addWidget(btn, r_idx, c_idx)

    def select_color(self, hex_color):
        self.callback(hex_color)
        self.close()


class DragDropArea(QFrame):
    def __init__(self, on_files_dropped_callback, parent=None):
        super().__init__(parent)
        self.on_files_dropped_callback = on_files_dropped_callback
        self.setAcceptDrops(True)
        self.setObjectName("dropZone")

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setStyleSheet("""
                QFrame#dropZone {
                    border: 2px dashed #3b82f6;
                    border-radius: 6px;
                    background-color: #1e2638;
                    min-height: 120px;
                }
                QFrame#dropZone QLabel { border: none; background: transparent; }
            """)

    def dragLeaveEvent(self, event):
        self.reset_style()

    def dropEvent(self, event: QDropEvent):
        self.reset_style()
        paths = [url.toLocalFile() for url in event.mimeData().urls()]
        if paths:
            self.on_files_dropped_callback(paths)

    def reset_style(self):
        self.setStyleSheet("""
            QFrame#dropZone {
                border: 2px dashed #3a4150;
                border-radius: 6px;
                background-color: #171a21;
                min-height: 120px;
            }
            QFrame#dropZone QLabel { border: none; background: transparent; }
        """)


class DraggablePictureTile(QWidget):
    def __init__(self, path, pixmap, remove_callback, reorder_callback, parent=None):
        super().__init__(parent)
        self.path = path
        self.remove_callback = remove_callback
        self.reorder_callback = reorder_callback
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self.setStyleSheet("background: #0d0f12; border-radius: 4px; border: 1px solid #2a2f3a;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(3, 3, 3, 3)
        layout.setSpacing(2)

        img_lbl = QLabel()
        img_lbl.setPixmap(pixmap)
        img_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        img_lbl.setStyleSheet("border: none; background: transparent;")

        rem_btn = QPushButton("× Remove")
        rem_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        rem_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e222b;
                color: #ef4444;
                border: 1px solid #3a4150;
                border-radius: 3px;
                font-size: 10px;
                padding: 2px;
            }
            QPushButton:hover { background-color: #3b1d24; border-color: #ef4444; }
        """)
        rem_btn.clicked.connect(lambda: self.remove_callback(self.path))

        layout.addWidget(img_lbl)
        layout.addWidget(rem_btn)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_start_position = event.pos()
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            return
        if (event.pos() - self.drag_start_position).manhattanLength() < QApplication.startDragDistance():
            return

        drag = QDrag(self)
        mime_data = QMimeData()
        mime_data.setData("application/x-picturepath", QByteArray(self.path.encode("utf-8")))
        drag.setMimeData(mime_data)

        pixmap = self.grab()
        drag.setPixmap(pixmap)
        drag.setHotSpot(event.pos())

        drag.exec(Qt.DropAction.MoveAction)


class PicturesContainerWidget(QWidget):
    def __init__(self, main_window, reorder_callback, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.reorder_callback = reorder_callback
        self.setAcceptDrops(True)
        self.setStyleSheet("background: transparent;")

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasFormat("application/x-picturepath"):
            event.acceptProposedAction()

    def dragMoveEvent(self, event: QDragMoveEvent):
        if event.mimeData().hasFormat("application/x-picturepath"):
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        if event.mimeData().hasFormat("application/x-picturepath"):
            path = bytes(event.mimeData().data("application/x-picturepath")).decode("utf-8")
            
            drop_x = event.position().toPoint().x()
            target_index = len(self.main_window.picture_data_list)

            layout = self.layout()
            for i in range(layout.count()):
                w = layout.itemAt(i).widget()
                if w and isinstance(w, DraggablePictureTile):
                    if drop_x < w.x() + w.width() // 2:
                        target_index = i
                        break

            self.reorder_callback(path, target_index)
            event.acceptProposedAction()