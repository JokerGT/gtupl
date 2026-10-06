# styles.py

GLOBAL_STYLESHEET = """
    QMainWindow {
        background-color: #17191e;
        color: #d0d4dc;
    }
    
    QComboBox::drop-down {
        border: none;
        background: transparent;
    }
    
    QSpinBox {
        border: 1px solid #2a2f3a;
        border-radius: 4px;
        color: #d0d4dc;
        padding-right: 20px;
    }
    
    QSpinBox::up-button {
        subcontrol-origin: padding;
        subcontrol-position: top right;
        width: 16px;
        background: #1e222b;
        border-left: 1px solid #2a2f3a;
        border-bottom: 1px solid #2a2f3a;
        border-top-right-radius: 3px;
    }
    QSpinBox::down-button {
        subcontrol-origin: padding;
        subcontrol-position: bottom right;
        width: 16px;
        background: #1e222b;
        border-left: 1px solid #2a2f3a;
        border-bottom-right-radius: 3px;
    }

    QScrollBar:vertical {
        border: none;
        background-color: transparent;
        width: 8px;
        margin: 0px;
    }
    QScrollBar::handle:vertical {
        background-color: #3a4150;
        min-height: 20px;
        border-radius: 4px;
    }
    QScrollBar::handle:vertical:hover {
        background-color: #4b5563;
    }
    QScrollBar::handle:vertical:pressed {
        background-color: #3b82f6;
    }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
        border: none;
        background: none;
        height: 0px;
    }
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
        background: none;
    }
    QScrollBar:horizontal {
        border: none;
        background-color: transparent;
        height: 6px;
        margin: 0px;
    }
    QScrollBar::handle:horizontal {
        background-color: #3a4150;
        min-width: 20px;
        border-radius: 4px;
    }
    QScrollBar::handle:horizontal:hover {
        background-color: #4b5563;
    }
    QScrollBar::handle:horizontal:pressed {
        background-color: #3b82f6;
    }
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
        border: none;
        background: none;
        width: 0px;
    }
    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
        background: none;
    }
"""

def apply_input_style(widget):
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