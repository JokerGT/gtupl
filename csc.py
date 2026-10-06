import sys
import os
import time
import cv2
import configparser
from PIL import Image, ImageDraw, ImageFont

from PyQt6.QtCore import QThread, pyqtSignal

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def get_config_path():
    if getattr(sys, 'frozen', False):
        app_dir = os.path.dirname(sys.executable)
    else:
        app_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(app_dir, "preferences.ini")

def load_settings():
    settings = {
        'x_tiles': 5,
        'y_tiles': 4,
        'tile_size': 512,
        'auto_size': True,
        'orig_size': False,
        'stamp_details': True,
        'show_filename': True,
        'show_size': True,
        'show_res': True,
        'show_fps': True,
        'show_duration': True,
        'ignore_first': 2,
        'ignore_last': 0,
        'format': 'JPEG',
        'quality': 65,
        'save_subfolder': True,
        'save_frames': False,
        'save_seeding': True,
        'torrent_client': 'qBittorrent'
    }

    config_path = get_config_path()
    if os.path.exists(config_path):
        config = configparser.ConfigParser()
        try:
            config.read(config_path)
            if 'Settings' in config:
                s = config['Settings']
                settings['x_tiles'] = s.getint('x_tiles', settings['x_tiles'])
                settings['y_tiles'] = s.getint('y_tiles', settings['y_tiles'])
                settings['tile_size'] = s.getint('tile_size', settings['tile_size'])
                settings['auto_size'] = s.getboolean('auto_size', settings['auto_size'])
                settings['orig_size'] = s.getboolean('orig_size', settings['orig_size'])
                settings['stamp_details'] = s.getboolean('stamp_details', settings['stamp_details'])
                settings['show_filename'] = s.getboolean('show_filename', settings['show_filename'])
                settings['show_size'] = s.getboolean('show_size', settings['show_size'])
                settings['show_res'] = s.getboolean('show_res', settings['show_res'])
                settings['show_fps'] = s.getboolean('show_fps', settings['show_fps'])
                settings['show_duration'] = s.getboolean('show_duration', settings['show_duration'])
                settings['ignore_first'] = s.getint('ignore_first', settings['ignore_first'])
                settings['ignore_last'] = s.getint('ignore_last', settings['ignore_last'])
                settings['format'] = s.get('format', settings['format'])
                settings['quality'] = s.getint('quality', settings['quality'])
                settings['save_subfolder'] = s.getboolean('save_subfolder', settings['save_subfolder'])
                settings['save_frames'] = s.getboolean('save_frames', settings['save_frames'])
                settings['save_seeding'] = s.getboolean('save_seeding', settings.get('save_seeding', True))
                settings['torrent_client'] = s.get('torrent_client', settings.get('torrent_client', 'qBittorrent'))
        except Exception as e:
            print(f"[CSC] Failed to load preferences, setting to defaults")

    return settings

def add_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select Video Files", "", "Video Files (*.3gp *.asf *.asx *.avi *.bik *.divx *.flv *.m2t *.m2ts *.m2v *.m4v *.mkv *.mp4 *.mpeg *.mpg *.mov *.mts *.ogm *.ogv *.rm *.rmvb *.ts *.vob *.webm *.wmv)"
        )
        for f in files:
            self.add_queue_item(f)
            
class PreviewWorker(QThread):
    finished = pyqtSignal(object)  # Emits PIL Image or None on failure

    def __init__(self, settings=None):
        super().__init__()
        self.settings = settings if settings is not None else load_settings()

    def run(self):
        assets_dir = resource_path("assets")
        if not os.path.exists(assets_dir):
            self.finished.emit(None)
            return

        frame_files = []
        for i in range(1, 101):
            fname = f"frame_{i:02d}.jpg"
            fpath = os.path.join(assets_dir, fname)
            if os.path.exists(fpath):
                frame_files.append(fpath)

        if not frame_files:
            self.finished.emit(None)
            return

        total_frames = len(frame_files)
        target_tiles = self.settings['x_tiles'] * self.settings['y_tiles']

        ignore_first_pct = self.settings['ignore_first'] / 100.0
        ignore_last_pct = self.settings['ignore_last'] / 100.0

        start_idx = int(total_frames * ignore_first_pct)
        end_idx = int(total_frames * (1.0 - ignore_last_pct)) - 1

        if start_idx >= end_idx:
            start_idx, end_idx = 0, total_frames - 1

        if target_tiles > 1:
            step = (end_idx - start_idx) / (target_tiles - 1)
            selected_indices = [int(start_idx + i * step) for i in range(target_tiles)]
        else:
            selected_indices = [start_idx]

        sample_img = Image.open(frame_files[0])
        width, height = sample_img.size

        target_size = self.settings['tile_size']
        if self.settings.get('orig_size', False):
            tile_w, tile_h = width, height
        else:
            if width >= height:
                tile_h = target_size
                tile_w = int(target_size * (width / height))
            else:
                tile_w = target_size
                tile_h = int(target_size * (height / width))

        frames = []
        for idx in selected_indices:
            idx_clamped = min(max(0, idx), total_frames - 1)
            img = Image.open(frame_files[idx_clamped])
            img = img.resize((tile_w, tile_h), Image.Resampling.LANCZOS)
            frames.append(img)

        grid_w = self.settings['x_tiles'] * tile_w
        grid_h = self.settings['y_tiles'] * tile_h
        min_header_height = 100
        header_h = max(min_header_height, int(tile_h * 0.3)) if self.settings['stamp_details'] else 0

        sheet = Image.new('RGB', (grid_w, grid_h + header_h), (255, 255, 255))
        draw = ImageDraw.Draw(sheet)
        
        if self.settings['stamp_details'] and header_h > 0:
            header_bg_color = "#17191e"
            text_color = (255, 255, 255)
            draw.rectangle([0, 0, grid_w, header_h], fill=header_bg_color)

        def middle_ellipse_text(text, font, max_width):
            def get_w(t):
                bbox = draw.textbbox((0, 0), t, font=font)
                return bbox[2] - bbox[0]

            if get_w(text) <= max_width:
                return text

            ellipsis = "..."
            if get_w(ellipsis) >= max_width:
                return ellipsis

            name, ext = os.path.splitext(text)
            low = 1
            high = len(name) // 2
            best_text = ellipsis + ext if ext else ellipsis

            while low <= high:
                mid = (low + high) // 2
                head = name[:mid]
                tail = name[-mid:] + ext
                candidate = f"{head}{ellipsis}{tail}"

                if get_w(candidate) <= max_width:
                    best_text = candidate
                    low = mid + 1
                else:
                    high = mid - 1

            return best_text

        if self.settings['stamp_details'] and header_h > 0:
            # 1. Draw header background color (e.g., light hex theme)
            header_bg_color = "#17191e"
            draw.rectangle([0, 0, grid_w, header_h], fill=header_bg_color)

            x_margin = 25
            icon_target_w = 0

            # 2. Handle icon scaling and positioning on the right side
            icon_path = resource_path("assets/gtlogonew.png")  # Ensure your icon is converted to PNG
            if os.path.exists(icon_path):
                icon_img = Image.open(icon_path).convert("RGBA")
                
                # Scale to exactly 35% of the header height while maintaining the 2242x980 aspect ratio
                icon_target_h = int(header_h * 0.35)
                icon_aspect = icon_img.width / icon_img.height
                icon_target_w = int(icon_target_h * icon_aspect)
                
                icon_img = icon_img.resize((icon_target_w, icon_target_h), Image.Resampling.LANCZOS)
                
                # Align vertically and place on the right with x_margin spacing
                icon_x = grid_w - icon_target_w - x_margin
                icon_y = (header_h - icon_target_h) // 2
                
                sheet.paste(icon_img, (icon_x, icon_y), icon_img)

            # 3. Setup text lines
            info_lines = []
            if self.settings.get('show_filename', True):
                # Use appropriate filename variable depending on worker context
                filename_str = os.path.basename(file_path) if 'file_path' in locals() else "Flow.(2024).1080p.x265.4Mbps.6CH.mp4"
                info_lines.append(f"File: {filename_str}")

            line2_items = []
            if self.settings.get('show_res', True):
                line2_items.append(f"Resolution: {width}x{height}")
            if self.settings.get('show_fps', True):
                fps_val = f"{fps:.2f}" if 'fps' in locals() else "23.976"
                line2_items.append(f"FPS: {fps_val}")
            line2 = " | ".join(filter(None, line2_items))
            if line2:
                info_lines.append(line2)

            if self.settings.get('show_duration', True):
                dur_str = f"{int(duration_sec//3600):02d}:{int((duration_sec%3600)//60):02d}:{int(duration_sec%60):02d}" if 'duration_sec' in locals() else "01:25:29"
                info_lines.append(f"Duration: {dur_str}")

            if self.settings.get('show_size', True):
                size_str = "Size: 2.07 GB"
                if 'file_path' in locals() and os.path.exists(file_path):
                    file_bytes = os.path.getsize(file_path)
                    if file_bytes >= 1024**3:
                        size_str = f"Size: {file_bytes / (1024**3):.2f} GB"
                    elif file_bytes >= 1024**2:
                        size_str = f"Size: {file_bytes / (1024**2):.2f} MB"
                    else:
                        size_str = f"Size: {file_bytes} Bytes"
                info_lines.append(size_str)

            if info_lines:
                font_size = max(10, int(header_h / (len(info_lines) + 1.5)))
                try:
                    font = ImageFont.truetype("arial.ttf", font_size)
                except IOError:
                    font = ImageFont.load_default()

                line_gap = int(font_size * 0.3)
                total_text_height = (len(info_lines) * font_size) + ((len(info_lines) - 1) * line_gap)
                y_text = int((header_h - total_text_height) / 2)

                # 4. Restrict max text width so text doesn't overlap the icon
                icon_spacing = icon_target_w + 20 if icon_target_w > 0 else 0
                max_text_width = grid_w - x_margin - x_margin - icon_spacing

                header_bg_color = "#17191e"
                text_color = (255, 255, 255)
                
                for line in info_lines:
                    display_line = middle_ellipse_text(line, font, max_text_width)
                    draw.text((x_margin, y_text), display_line, fill=text_color, font=font)
                    y_text += font_size + line_gap

        for i, frame_img in enumerate(frames):
            row = i // self.settings['x_tiles']
            col = i % self.settings['x_tiles']
            x = col * tile_w
            y = header_h + (row * tile_h)
            sheet.paste(frame_img, (x, y))

        self.finished.emit(sheet)


class ProcessingWorker(QThread):
    progress_updated = pyqtSignal(int, str)        
    progress_signal = pyqtSignal(int, int, float)  
    item_finished = pyqtSignal(int, bool)          
    finished_all = pyqtSignal(bool)                # Unchanged signature
    finished = pyqtSignal()                        

    def __init__(self, indexed_items, settings):
        super().__init__()
        self.indexed_items = indexed_items
        self.settings = settings
        self._is_cancelled = False
        self.generated_files = []  # Initialize storage for generated assets

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        start_time = time.time()
        total_tiles_to_generate = len(self.indexed_items) * (self.settings['x_tiles'] * self.settings['y_tiles'])
        completed_tiles = 0
        self.generated_files = []  # Reset per run

        for original_idx, file_path in self.indexed_items:
            if self._is_cancelled:
                break
            
            video_name = os.path.basename(file_path)
            # Calculate percentage strictly from 0% to 50% based on tiles
            current_pct = int((completed_tiles / total_tiles_to_generate) * 50) if total_tiles_to_generate > 0 else 0
            self.progress_updated.emit(
                current_pct, 
                f"Processing: {video_name}"
            )

            success, tiles_done, file_assets = self.generate_contact_sheet(
                file_path, completed_tiles, total_tiles_to_generate, start_time
            )
            completed_tiles += tiles_done
            
            if success:
                self.generated_files.extend(file_assets)
            
            if self._is_cancelled:
                break

            self.item_finished.emit(original_idx, success)

        self.progress_updated.emit(50, "Processing complete!")
        self.finished_all.emit(self._is_cancelled)
        self.finished.emit()

    def generate_contact_sheet(self, file_path, current_completed_tiles, total_tiles, start_time):
        target_tiles_for_file = self.settings['x_tiles'] * self.settings['y_tiles']
        generated_assets = []
        try:
            cap = cv2.VideoCapture(file_path)
            if not cap.isOpened():
                return False, target_tiles_for_file, []

            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            duration_sec = frame_count / fps if fps > 0 else 0

            if frame_count <= 0 or width <= 0 or height <= 0:
                cap.release()
                return False, target_tiles_for_file, []

            start_ms = duration_sec * 1000 * (self.settings['ignore_first'] / 100.0)
            end_ms = duration_sec * 1000 * (1.0 - (self.settings['ignore_last'] / 100.0))

            if start_ms >= end_ms:
                start_ms, end_ms = 0, duration_sec * 1000

            end_ms = max(start_ms, end_ms - 100)

            if target_tiles_for_file > 1:
                step = (end_ms - start_ms) / (target_tiles_for_file - 1)
                timestamps_ms = [start_ms + i * step for i in range(target_tiles_for_file)]
            else:
                timestamps_ms = [start_ms]

            target_size = self.settings['tile_size']
            if self.settings['auto_size']:
                if width >= height:
                    tile_h = target_size
                    tile_w = int(target_size * (width / height))
                else:
                    tile_w = target_size
                    tile_h = int(target_size * (height / width))
            else:
                tile_w, tile_h = width, height

            frames = []
            for tile_idx, time_ms in enumerate(timestamps_ms):
                if self._is_cancelled:
                    cap.release()
                    return False, tile_idx, []

                cap.set(cv2.CAP_PROP_POS_MSEC, time_ms)
                ret, frame = cap.read()
                if ret:
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    img = Image.fromarray(frame)
                    img = img.resize((tile_w, tile_h), Image.Resampling.LANCZOS)
                    frames.append(img)
                else:
                    frames.append(Image.new('RGB', (tile_w, tile_h), (0, 0, 0)))

                elapsed = time.time() - start_time
                self.progress_signal.emit(current_completed_tiles + tile_idx + 1, total_tiles, elapsed)

            cap.release()

            if self._is_cancelled:
                return False, target_tiles_for_file, []

            grid_w = self.settings['x_tiles'] * tile_w
            grid_h = self.settings['y_tiles'] * tile_h
            min_header_height = 100
            header_h = max(min_header_height, int(tile_h * 0.3)) if self.settings['stamp_details'] else 0

            sheet = Image.new('RGB', (grid_w, grid_h + header_h), (255, 255, 255))
            draw = ImageDraw.Draw(sheet)

            def middle_ellipse_text(text, font, max_width):
                def get_w(t):
                    bbox = draw.textbbox((0, 0), t, font=font)
                    return bbox[2] - bbox[0]

                if get_w(text) <= max_width:
                    return text

                ellipsis = "..."
                if get_w(ellipsis) >= max_width:
                    return ellipsis

                name, ext = os.path.splitext(text)
                low = 1
                high = len(name) // 2
                best_text = ellipsis + ext if ext else ellipsis

                while low <= high:
                    mid = (low + high) // 2
                    head = name[:mid]
                    tail = name[-mid:] + ext
                    candidate = f"{head}{ellipsis}{tail}"
                    
                    if get_w(candidate) <= max_width:
                        best_text = candidate
                        low = mid + 1
                    else:
                        high = mid - 1

                return best_text

            if self.settings['stamp_details'] and header_h > 0:
                # 1. Draw header background color
                header_bg_color = "#17191e"
                draw.rectangle([0, 0, grid_w, header_h], fill=header_bg_color)

                x_margin = 25
                icon_target_w = 0

                # 2. Handle icon scaling and positioning on the right side
                icon_path = resource_path("assets/gtlogonew.png")
                if os.path.exists(icon_path):
                    icon_img = Image.open(icon_path).convert("RGBA")
                    
                    icon_target_h = int(header_h * 0.35)
                    icon_aspect = icon_img.width / icon_img.height
                    icon_target_w = int(icon_target_h * icon_aspect)
                    
                    icon_img = icon_img.resize((icon_target_w, icon_target_h), Image.Resampling.LANCZOS)
                    
                    icon_x = grid_w - icon_target_w - x_margin
                    icon_y = (header_h - icon_target_h) // 2
                    
                    sheet.paste(icon_img, (icon_x, icon_y), icon_img)

                info_lines = []

                if self.settings['show_filename']:
                    info_lines.append(f"File: {os.path.basename(file_path)}")

                line2_items = []
                if self.settings['show_res']:
                    line2_items.append(f"Resolution: {width}x{height}")
                if self.settings['show_fps']:
                    line2_items.append(f"FPS: {fps:.2f}")
                line2 = " | ".join(filter(None, line2_items))
                if line2:
                    info_lines.append(line2)

                if self.settings['show_duration']:
                    info_lines.append(
                        f"Duration: {int(duration_sec//3600):02d}:{int((duration_sec%3600)//60):02d}:{int(duration_sec%60):02d}"
                    )

                if self.settings['show_size']:
                    file_bytes = os.path.getsize(file_path)
                    if file_bytes >= 1024**3:
                        size_str = f"Size: {file_bytes / (1024**3):.2f} GB"
                    elif file_bytes >= 1024**2:
                        size_str = f"Size: {file_bytes / (1024**2):.2f} MB"
                    else:
                        size_str = f"Size: {file_bytes} Bytes"
                    info_lines.append(size_str)

                font_size = max(10, int(header_h / (len(info_lines) + 1.5)))
                try:
                    font = ImageFont.truetype("arial.ttf", font_size)
                except IOError:
                    font = ImageFont.load_default()

                line_gap = int(font_size * 0.3)
                total_text_height = (len(info_lines) * font_size) + ((len(info_lines) - 1) * line_gap)
                y_text = int((header_h - total_text_height) / 2)

                # 3. Restrict max text width so text doesn't overlap the icon
                icon_spacing = icon_target_w + 20 if icon_target_w > 0 else 0
                max_text_width = grid_w - x_margin - x_margin - icon_spacing
                
                text_color = (255, 255, 255)

                for line in info_lines:
                    display_line = middle_ellipse_text(line, font, max_text_width)
                    draw.text((x_margin, y_text), display_line, fill=text_color, font=font)
                    y_text += font_size + line_gap

            for i, frame_img in enumerate(frames):
                row = i // self.settings['x_tiles']
                col = i % self.settings['x_tiles']
                x = col * tile_w
                y = header_h + (row * tile_h)
                sheet.paste(frame_img, (x, y))

            base_dir = os.path.dirname(file_path)
            raw_stem, video_ext = os.path.splitext(os.path.basename(file_path))
            file_stem = f"{raw_stem}.{video_ext.lstrip('.').lower()}"
            
            fmt = self.settings['format'].lower()
            ext = ".jpg" if fmt == "jpeg" else f".{fmt}"

            if self.settings['save_subfolder']:
                out_dir = os.path.join(base_dir, "contact_sheets")
                os.makedirs(out_dir, exist_ok=True)
            else:
                out_dir = base_dir

            out_path = os.path.join(out_dir, f"{file_stem}{ext}")

            if not self.settings['overwrite'] and os.path.exists(out_path):
                counter = 1
                while True:
                    out_path = os.path.join(out_dir, f"{file_stem}_cs{counter}{ext}")
                    if not os.path.exists(out_path):
                        break
                    counter += 1

            save_kwargs = {}
            if fmt in ('jpeg', 'jpg', 'webp'):
                save_kwargs['quality'] = self.settings['quality']

            # --- DEBUG PRINTS START ---
            print(f"[DEBUG] About to save contact sheet to: {out_path}")
            print(f"[DEBUG] Save parameters: {save_kwargs}")
            # --- DEBUG PRINTS END ---

            sheet.save(out_path, **save_kwargs)
            generated_assets.append(out_path)

            # --- DEBUG PRINT AFTER START ---
            print(f"[DEBUG] Successfully saved file: {out_path}")
            # --- DEBUG PRINT AFTER END ---

            if self.settings['save_frames']:
                frames_dir = os.path.join(base_dir, f"{file_stem}_thumbs")
                os.makedirs(frames_dir, exist_ok=True)
                for i, frame_img in enumerate(frames):
                    frame_path = os.path.join(frames_dir, f"frame_{i+1:02d}{ext}")
                    frame_img.save(frame_path, **save_kwargs)
                    generated_assets.append(frame_path)

            return True, target_tiles_for_file, generated_assets
        except Exception as e:
            print(f"[DEBUG ERROR] Error processing {file_path}: {e}")
            return False, target_tiles_for_file, []