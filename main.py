import sys
import os
import sqlite3
import base64
import argparse
from typing import Optional, Tuple
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QFileDialog,
    QLabel,
    QLineEdit,
    QScrollArea,
    QGridLayout,
    QMenu,
    QSizePolicy,
    QCheckBox,
    QStyle,
    QComboBox,
)
from PyQt5.QtGui import QPixmap, QDrag, QImage
from PyQt5.QtCore import Qt, QBuffer, QMimeData, QUrl, pyqtSignal
import cv2
import numpy as np
import subprocess
import shutil
from tqdm import tqdm

# Ensure the sibling CategorizerProject path is available for shared utilities.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CATEGORIZER_PROJECT_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, '..', 'CategorizerProject'))
if os.path.isdir(CATEGORIZER_PROJECT_DIR) and CATEGORIZER_PROJECT_DIR not in sys.path:
    sys.path.insert(0, CATEGORIZER_PROJECT_DIR)

from anagram_util import get_original_name, convert_to_anagram, add_anagram_record

# Global debug flag
DEBUG_MODE = False


def natural_sort_key(s):
    """Key for natural alphanumeric sort: 'file10' sorts after 'file9'."""
    import re
    return [int(c) if c.isdigit() else c.lower() for c in re.split(r'(\d+)', s)]


def _fmt_size(path):
    """Return a human-readable file size string, or empty string on error."""
    try:
        size = os.path.getsize(path)
    except Exception:
        return ""
    if size < 1024:
        return str(size) + " B"
    elif size < 1048576:
        return "{:.1f} KB".format(size / 1024.0)
    elif size < 1073741824:
        return "{:.1f} MB".format(size / 1048576.0)
    else:
        return "{:.2f} GB".format(size / 1073741824.0)

def debug_print(*args, **kwargs):
    if DEBUG_MODE:
        print(*args, **kwargs)

def decode_anagram_filename(filename):
    try:
        record_file = os.environ.get('ANAGRAM_FILE_PATH')
        if not record_file:
            debug_print("ANAGRAM_FILE_PATH not set for: " + filename)
            return filename
        if not os.path.exists(record_file):
            debug_print("Anagram file not found: " + record_file)
            return filename
        name_without_ext = os.path.splitext(filename)[0]
        extension = os.path.splitext(filename)[1]
        with open(record_file, 'r', encoding='utf-8') as f:
            records = f.readlines()
        for i, record in enumerate(records):
            record = record.strip()
            if ',' in record:
                parts = record.split(',', 1)
                if len(parts) == 2:
                    original_name, anagram = parts[0].strip(), parts[1].strip()
                    if anagram == name_without_ext:
                        return original_name + extension
        return filename
    except Exception as e:
        debug_print("Error decoding anagram for " + filename + ": " + str(e))
        return filename


def generate_anagram_output_filename(input_video_path: str) -> str:
    """
    Generate an output filename with '-subbed' suffix using anagram logic.
    
    Flow:
    1. Get the stem of the input file (without extension)
    2. Reverse-anagram it to get the original name
    3. Append '-subbed' to the original name
    4. Convert the new name back to anagram form
    5. Record the new anagram mapping
    6. Return the anagrammed stem (caller adds extension and path)
    """
    try:
        record_file = os.environ.get('ANAGRAM_FILE_PATH')
        if not record_file:
            debug_print("ANAGRAM_FILE_PATH not set; using simple -subbed suffix")
            base, _ = os.path.splitext(input_video_path)
            return os.path.basename(base) + "-subbed"
        
        if not os.path.exists(record_file):
            debug_print("Anagram file not found; using simple -subbed suffix")
            base, _ = os.path.splitext(input_video_path)
            return os.path.basename(base) + "-subbed"
        
        # Get the stem (no extension) of the input file
        input_stem = os.path.splitext(os.path.basename(input_video_path))[0]
        input_ext = os.path.splitext(input_video_path)[1]
        
        # Reverse-anagram to get the original name
        original_name = get_original_name(input_stem, record_file=record_file)
        if not original_name:
            original_name = input_stem
        
        # Append -subbed to the original name
        new_original = original_name + "-subbed"
        
        # Convert back to anagram
        new_anagram = convert_to_anagram(new_original)
        
        # Record the mapping
        add_anagram_record(new_original, new_anagram, record_file=record_file)
        
        # Return just the anagrammed stem (caller will add extension)
        return new_anagram
    except Exception as e:
        debug_print("Error generating anagram output filename: " + str(e))
        base, ext = os.path.splitext(input_video_path)
        return os.path.basename(base) + "-subbed"


def get_ffmpeg_executable() -> Optional[str]:
    """Return the ffmpeg executable path, preferring a known Chocolatey location."""
    chocolatey_ffmpeg = r"C:\ProgramData\chocolatey\bin\ffmpeg.exe"
    if os.path.exists(chocolatey_ffmpeg):
        return chocolatey_ffmpeg
    found = shutil.which("ffmpeg")
    if found:
        return found
    return None


def embed_subtitles_ffmpeg(input_video: str, subtitle_file: str, output_video: str) -> Tuple[bool, str]:
    """
    Embed a subtitle track into a video using ffmpeg.

    Returns:
        (success, error_message)
    """
    ffmpeg_executable = get_ffmpeg_executable()
    if not ffmpeg_executable or not os.path.exists(ffmpeg_executable):
        message = "ffmpeg executable not found at C:\\ProgramData\\chocolatey\\bin\\ffmpeg.exe and not available on PATH."
        debug_print(message)
        return False, message

    cmd = [
        ffmpeg_executable,
        "-nostdin",
        "-y",
        "-i",
        input_video,
        "-i",
        subtitle_file,
        "-map",
        "0",
        "-map",
        "1",
        "-c:v",
        "copy",
        "-c:a",
        "copy",
        "-c:s",
        "mov_text",
        output_video,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            error = result.stderr.strip() or result.stdout.strip() or "Unknown ffmpeg error"
            debug_print("FFmpeg command failed: " + error)
            return False, error
        return True, ""
    except FileNotFoundError:
        message = f"FFmpeg executable not found: {ffmpeg_executable}"
        debug_print(message)
        return False, message
    except subprocess.TimeoutExpired:
        message = "FFmpeg timed out while embedding subtitles."
        debug_print(message)
        return False, message
        return False, message
    except Exception as e:
        error = str(e)
        debug_print("FFmpeg error: " + error)
        return False, error


SCREENCAP_HEIGHT = 800
SCREENCAP_WIDTH = 800
SCREENCAP_FRAME_COUNT = 9
IMAGE_EXTENSIONS = {
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp',
    '.tiff', '.tif', '.ico', '.jfif',
}

class ScreencapDatabase:
    def __init__(self, db_path):
        self.db_path = db_path
        self._init_database()

    def _init_database(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS screencaps (
                file_path  TEXT PRIMARY KEY,
                image_data TEXT NOT NULL,
                file_size  INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()

    def get_screencap(self, file_path):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('SELECT image_data FROM screencaps WHERE file_path = ?', (file_path,))
        result = c.fetchone()
        conn.close()
        return result[0] if result else None

    def save_screencap(self, file_path, image_data):
        file_size = 0
        try:
            if os.path.exists(file_path):
                file_size = os.path.getsize(file_path)
        except Exception:
            pass
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute(
            'INSERT OR REPLACE INTO screencaps (file_path, image_data, file_size) VALUES (?, ?, ?)',
            (file_path, image_data, file_size),
        )
        conn.commit()
        conn.close()

    def get_database_size(self):
        try:
            return os.path.getsize(self.db_path) / (1024 * 1024)
        except Exception:
            return 0

    def cleanup_old_entries(self, days=30):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute(
            "DELETE FROM screencaps WHERE created_at < datetime('now', '-{} days')".format(days)
        )
        deleted = c.rowcount
        conn.commit()
        conn.close()
        return deleted

def pixmap_to_base64_compressed(pixmap, max_size=400, quality=75):
    original_area = pixmap.width() * pixmap.height()
    if original_area > 2000000:
        max_size, quality = 300, 60
    elif original_area > 1000000:
        max_size, quality = 350, 65
    elif original_area > 500000:
        max_size, quality = 400, 70
    if pixmap.width() > max_size or pixmap.height() > max_size:
        pixmap = pixmap.scaled(max_size, max_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    buffer = QBuffer()
    buffer.open(QBuffer.WriteOnly)
    pixmap.save(buffer, "JPEG", quality)
    return base64.b64encode(buffer.data().data()).decode('utf-8')

def base64_to_pixmap(base64_string):
    image_data = base64.b64decode(base64_string.encode('utf-8'))
    pixmap = QPixmap()
    pixmap.loadFromData(image_data)
    return pixmap

class Label(QWidget):
    def __init__(self, pixmap, file_path, show_original=False, parent=None):
        super(Label, self).__init__(parent)
        self.original_pixmap = pixmap
        self.file_path = file_path
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(2)

        cb_row = QHBoxLayout()
        self.select_checkbox = QCheckBox()
        self.select_checkbox.setFixedSize(18, 18)
        self.select_checkbox.setToolTip("Select for deletion")
        cb_row.addWidget(self.select_checkbox)
        cb_row.addStretch()
        layout.addLayout(cb_row)

        self.image_label = QLabel()
        self.image_label.setPixmap(pixmap)
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.image_label)

        filename = os.path.basename(file_path)
        self.anagram_filename = filename
        self.decoded_filename = decode_anagram_filename(filename)
        display = self.decoded_filename if show_original else self.anagram_filename
        self.filename_label = QLabel(display)
        self.filename_label.setAlignment(Qt.AlignCenter)
        self.filename_label.setWordWrap(True)
        self.filename_label.setStyleSheet(
            "QLabel { font-size: 10px; color: #333;"
            " background-color: rgba(255,255,255,180);"
            " border: 1px solid #ccc; border-radius: 3px;"
            " padding: 2px; margin: 1px; }"
        )
        layout.addWidget(self.filename_label)

        self.size_label = QLabel(_fmt_size(file_path))
        self.size_label.setAlignment(Qt.AlignCenter)
        self.size_label.setStyleSheet(
            "QLabel { font-size: 9px; color: #777;"
            " padding: 1px; margin: 0px; }"
        )
        layout.addWidget(self.size_label)

    def setPixmap(self, pixmap):
        self.original_pixmap = pixmap
        self.image_label.setPixmap(pixmap)

    def resizeEvent(self, event):
        if self.original_pixmap and not self.original_pixmap.isNull():
            scaled = self.original_pixmap.scaled(
                self.image_label.width(),
                self.image_label.height(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            self.image_label.setPixmap(scaled)
        super(Label, self).resizeEvent(event)

    def update_display(self, show_original):
        self.filename_label.setText(self.decoded_filename if show_original else self.anagram_filename)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            drag = QDrag(self)
            mime = QMimeData()
            mime.setText(self.file_path)
            drag.setMimeData(mime)
            drag.exec_(Qt.MoveAction)

    def show_context_menu(self, position):
        ext = os.path.splitext(self.file_path)[1].lower()
        menu = QMenu(self)
        copy_action = menu.addAction("Copy Path")
        copy_file_action = menu.addAction("Copy File")
        play_action = menu.addAction("Play") if ext not in IMAGE_EXTENSIONS else None
        action = menu.exec_(self.mapToGlobal(position))
        if action == copy_action:
            self.copy_to_clipboard()
        elif action == copy_file_action:
            self.copy_file_to_clipboard()
        elif play_action and action == play_action:
            self.play_video()

    def copy_to_clipboard(self):
        QApplication.clipboard().setText(self.file_path.replace('/', '\\'))

    def copy_file_to_clipboard(self):
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(self.file_path)])
        QApplication.clipboard().setMimeData(mime)

    def play_video(self):
        try:
            subprocess.Popen(['mpv', self.file_path])
        except FileNotFoundError:
            print("Error: mpv is not installed or not in PATH")

    def enterEvent(self, event):
        try:
            size = os.path.getsize(self.file_path)
            if size < 1024:
                size_str = str(size) + " B"
            elif size < 1048576:
                size_str = "{:.2f} KB".format(size / 1024.0)
            elif size < 1073741824:
                size_str = "{:.2f} MB".format(size / 1048576.0)
            else:
                size_str = "{:.2f} GB".format(size / 1073741824.0)
            self.setToolTip(self.file_path + "  [" + size_str + "]")
        except Exception:
            self.setToolTip(self.file_path)
        super(Label, self).enterEvent(event)


class FolderWidget(QWidget):
    folder_clicked = pyqtSignal(str)

    def __init__(self, folder_path, show_original=False, parent=None):
        super(FolderWidget, self).__init__(parent)
        self.folder_path = folder_path
        raw_name = os.path.basename(folder_path)
        self.anagram_name = raw_name
        self.decoded_name = decode_anagram_filename(raw_name)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setCursor(Qt.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(2)

        icon_label = QLabel()
        icon_label.setPixmap(
            QApplication.style().standardIcon(QStyle.SP_DirIcon).pixmap(64, 64)
        )
        icon_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon_label)

        display = self.decoded_name if show_original else self.anagram_name
        self.name_label = QLabel(display)
        self.name_label.setAlignment(Qt.AlignCenter)
        self.name_label.setWordWrap(True)
        self.name_label.setStyleSheet(
            "QLabel { font-size: 10px; color: #333;"
            " background-color: rgba(255,255,255,180);"
            " border: 1px solid #ccc; border-radius: 3px;"
            " padding: 2px; margin: 1px; }"
        )
        layout.addWidget(self.name_label)

    def update_display(self, show_original):
        self.name_label.setText(self.decoded_name if show_original else self.anagram_name)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.folder_clicked.emit(self.folder_path)

    def show_context_menu(self, position):
        menu = QMenu(self)
        copy_action = menu.addAction("Copy Path")
        action = menu.exec_(self.mapToGlobal(position))
        if action == copy_action:
            QApplication.clipboard().setText(self.folder_path.replace('/', '\\'))

    def enterEvent(self, event):
        self.setToolTip(self.folder_path)
        super(FolderWidget, self).enterEvent(event)


class VideoPlaceholder(QWidget):
    def __init__(self, file_path, show_original=False, parent=None):
        super(VideoPlaceholder, self).__init__(parent)
        self.file_path = file_path
        filename = os.path.basename(file_path)
        self.anagram_filename = filename
        self.decoded_filename = decode_anagram_filename(filename)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(2)

        cb_row = QHBoxLayout()
        self.select_checkbox = QCheckBox()
        self.select_checkbox.setFixedSize(18, 18)
        self.select_checkbox.setToolTip("Select for deletion")
        cb_row.addWidget(self.select_checkbox)
        cb_row.addStretch()
        layout.addLayout(cb_row)

        icon_label = QLabel("▶")
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setStyleSheet("font-size: 28px; color: #666;")
        layout.addWidget(icon_label)

        display = self.decoded_filename if show_original else self.anagram_filename
        self.name_label = QLabel(display)
        self.name_label.setAlignment(Qt.AlignCenter)
        self.name_label.setWordWrap(True)
        self.name_label.setStyleSheet(
            "QLabel { font-size: 10px; color: #333;"
            " background-color: rgba(255,255,255,180);"
            " border: 1px solid #ccc; border-radius: 3px;"
            " padding: 2px; margin: 1px; }"
        )
        layout.addWidget(self.name_label)

        self.size_label = QLabel(_fmt_size(file_path))
        self.size_label.setAlignment(Qt.AlignCenter)
        self.size_label.setStyleSheet(
            "QLabel { font-size: 9px; color: #777;"
            " padding: 1px; margin: 0px; }"
        )
        layout.addWidget(self.size_label)

    def update_display(self, show_original):
        self.name_label.setText(self.decoded_filename if show_original else self.anagram_filename)

    def show_context_menu(self, position):
        menu = QMenu(self)
        copy_action = menu.addAction("Copy Path")
        copy_file_action = menu.addAction("Copy File")
        play_action = menu.addAction("Play")
        embed_subs_action = menu.addAction("Embed Subtitles")
        action = menu.exec_(self.mapToGlobal(position))
        if action == copy_action:
            QApplication.clipboard().setText(self.file_path.replace('/', '\\'))
        elif action == copy_file_action:
            mime = QMimeData()
            mime.setUrls([QUrl.fromLocalFile(self.file_path)])
            QApplication.clipboard().setMimeData(mime)
        elif action == play_action:
            self.play_video()
        elif action == embed_subs_action:
            self.embed_subtitles()

    def play_video(self):
        try:
            subprocess.Popen(['mpv', self.file_path])
        except FileNotFoundError:
            print("Error: mpv is not installed or not in PATH")

    def embed_subtitles(self):
        """Open subtitle selection dialog and embed subtitles into the video."""
        from PyQt5.QtWidgets import QMessageBox
        
        # Ask user to select a subtitle file
        subtitle_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Subtitle File",
            "",
            "Subtitle Files (*.srt *.ass *.vtt);;All Files (*.*)"
        )
        if not subtitle_path:
            return
        
        # Generate output filename with anagram logic
        output_stem = generate_anagram_output_filename(self.file_path)
        output_dir = os.path.dirname(self.file_path)
        temp_output_video = os.path.join(output_dir, output_stem + ".mp4")
        final_output_video = os.path.join(output_dir, output_stem + ".mif")
        
        # Show a progress message
        QMessageBox.information(self, "Embedding", "Embedding subtitles... Please wait.")
        
        # Perform the embedding to a temp MP4 first, then rename to .mif
        success, error_message = embed_subtitles_ffmpeg(self.file_path, subtitle_path, temp_output_video)
        if success:
            try:
                if os.path.exists(final_output_video):
                    os.remove(final_output_video)
                os.replace(temp_output_video, final_output_video)
            except Exception as e:
                error_message = f"Failed to rename output to .mif: {e}"
                debug_print(error_message)
                QMessageBox.critical(
                    self,
                    "Error",
                    "Subtitles were embedded, but the output file could not be renamed to .mif. " + error_message,
                )
                return
        
        if success:
            # Ask if user wants to preview with mpv
            reply = QMessageBox.question(
                self,
                "Success",
                f"Subtitles embedded successfully!\n\nOutput: {os.path.basename(final_output_video)}\n\nPreview with mpv?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                try:
                    subprocess.Popen(['mpv', final_output_video])
                except FileNotFoundError:
                    QMessageBox.warning(self, "Error", "mpv is not installed or not in PATH")
        else:
            QMessageBox.critical(
                self,
                "Error",
                "Failed to embed subtitles. " + error_message + "\nCheck that ffmpeg is installed and available at C:\\ProgramData\\chocolatey\\bin\\ffmpeg.exe or on your PATH.",
            )

    def enterEvent(self, event):
        try:
            size = os.path.getsize(self.file_path)
            if size < 1024:
                size_str = str(size) + " B"
            elif size < 1048576:
                size_str = "{:.2f} KB".format(size / 1024.0)
            elif size < 1073741824:
                size_str = "{:.2f} MB".format(size / 1048576.0)
            else:
                size_str = "{:.2f} GB".format(size / 1073741824.0)
            self.setToolTip(self.file_path + "  [" + size_str + "]")
        except Exception:
            self.setToolTip(self.file_path)
        super(VideoPlaceholder, self).enterEvent(event)


class DropArea(QLabel):
    file_dropped = pyqtSignal(str)

    def __init__(self, text_shown, actual_folder_text, parent=None):
        super(DropArea, self).__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setText(text_shown)
        self.setStyleSheet("border: 2px dashed #aaa")
        self.setAcceptDrops(True)
        self._folder_name = actual_folder_text.split("\n")[0]

    def dragEnterEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dropEvent(self, event):
        file_path = event.mimeData().text()
        destination_folder = os.path.join(os.path.dirname(file_path), self._folder_name)
        if not os.path.exists(destination_folder):
            os.makedirs(destination_folder)
        file_name = os.path.basename(file_path)
        new_path = os.path.join(destination_folder, file_name)
        os.rename(file_path, new_path)
        print("Moved " + file_name + " to " + self._folder_name)
        self.file_dropped.emit(file_path)

    def get_folder_name(self):
        return self._folder_name


class TrashDropZone(QLabel):
    file_deleted = pyqtSignal(str)

    _NORMAL_STYLE = (
        "QLabel { border: 2px dashed #e55; color: #c33; font-size: 14px;"
        " background: #fff0f0; border-radius: 6px; }"
    )
    _HOVER_STYLE = (
        "QLabel { border: 3px solid #e00; color: #900; font-size: 14px;"
        " background: #ffe0e0; border-radius: 6px; }"
    )

    def __init__(self, parent=None):
        super(TrashDropZone, self).__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setText("\U0001f5d1  Drop here to delete permanently")
        self.setMinimumHeight(52)
        self.setMaximumHeight(64)
        self.setStyleSheet(self._NORMAL_STYLE)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasText():
            self.setStyleSheet(self._HOVER_STYLE)
            event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        self.setStyleSheet(self._NORMAL_STYLE)

    def dropEvent(self, event):
        self.setStyleSheet(self._NORMAL_STYLE)
        file_path = event.mimeData().text()
        try:
            os.remove(file_path)
            self.file_deleted.emit(file_path)
        except Exception as e:
            print("Could not delete file: " + str(e))


class MoveDropZone(QLabel):
    file_moved = pyqtSignal(str)  # emits the original path after move

    _NORMAL_STYLE = (
        "QLabel { border: 2px dashed #55a; color: #339; font-size: 14px;"
        " background: #f0f0ff; border-radius: 6px; cursor: pointer; }"
    )
    _HOVER_STYLE = (
        "QLabel { border: 3px solid #00e; color: #006; font-size: 14px;"
        " background: #e0e0ff; border-radius: 6px; }"
    )
    _SET_STYLE = (
        "QLabel { border: 2px solid #55a; color: #339; font-size: 13px;"
        " background: #e8e8ff; border-radius: 6px; }"
    )

    def __init__(self, parent=None):
        super(MoveDropZone, self).__init__(parent)
        self._dest_folder = None
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumHeight(52)
        self.setMaximumHeight(64)
        self.setAcceptDrops(True)
        self._refresh_text()

    def _refresh_text(self):
        if self._dest_folder:
            self.setText("📁  Move to: {}  (click to change)".format(self._dest_folder))
            self.setStyleSheet(self._SET_STYLE)
        else:
            self.setText("📁  Click to set move destination, then drop files here")
            self.setStyleSheet(self._NORMAL_STYLE)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            folder = QFileDialog.getExistingDirectory(None, "Select Destination Folder")
            if folder:
                self._dest_folder = folder
                self._refresh_text()

    def dragEnterEvent(self, event):
        if event.mimeData().hasText() and self._dest_folder:
            self.setStyleSheet(self._HOVER_STYLE)
            event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        self._refresh_text()

    def dropEvent(self, event):
        self._refresh_text()
        if not self._dest_folder:
            return
        file_path = event.mimeData().text()
        file_name = os.path.basename(file_path)
        dest_path = os.path.join(self._dest_folder, file_name)
        try:
            os.rename(file_path, dest_path)
            self.file_moved.emit(file_path)
        except Exception as e:
            print("Could not move file: " + str(e))


def GenerateMedia(input_file, db):
    cached_data = db.get_screencap(input_file)
    if cached_data:
        debug_print("Cache hit: " + input_file)
        return Label(base64_to_pixmap(cached_data), input_file)

    ext = os.path.splitext(input_file)[1].lower()

    if ext in IMAGE_EXTENSIONS:
        pixmap = QPixmap(input_file)
        if not pixmap.isNull():
            debug_print("Image (Qt): " + input_file)
            db.save_screencap(input_file, pixmap_to_base64_compressed(pixmap))
            return Label(pixmap, input_file)

    try:
        cv_img = cv2.imread(input_file)
        if cv_img is not None:
            h, w = cv_img.shape[:2]
            q_img = QPixmap.fromImage(
                QImage(cv_img.data, w, h, 3 * w, QImage.Format_RGB888).rgbSwapped()
            )
            debug_print("Image (cv2): " + input_file)
            db.save_screencap(input_file, pixmap_to_base64_compressed(q_img))
            return Label(q_img, input_file)
    except Exception:
        pass

    debug_print("Generating screencap grid: " + input_file)
    capture = cv2.VideoCapture(input_file)
    if not capture.isOpened():
        print("Error opening: " + input_file)
        return None

    num_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    if num_frames < 1:
        debug_print("No frames in: " + input_file)
        capture.release()
        return None

    num_images = SCREENCAP_FRAME_COUNT
    num_rows = int(num_images ** 0.5)
    num_cols = num_images // num_rows
    frame_width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    output_image = np.zeros((num_rows * frame_height, num_cols * frame_width, 3), np.uint8)

    for row in range(num_rows):
        for col in range(num_cols):
            frame_num = row * num_cols + col
            time = frame_num * num_frames / num_images
            capture.set(cv2.CAP_PROP_POS_FRAMES, time)
            ret, frame = capture.read()
            if not ret:
                continue
            output_image[
                row * frame_height:(row + 1) * frame_height,
                col * frame_width:(col + 1) * frame_width,
            ] = frame

    capture.release()
    h, w = output_image.shape[:2]
    q_img = QPixmap.fromImage(
        QImage(output_image.data, w, h, 3 * w, QImage.Format_RGB888).rgbSwapped()
    )
    db.save_screencap(input_file, pixmap_to_base64_compressed(q_img))
    return Label(q_img, input_file)


class MainWindow(QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()
        self.setWindowTitle("Clip Viewer")
        self.setGeometry(100, 100, 1200, 800)

        db_path = os.environ.get('META_DB_PATH', 'screencaps.db')
        debug_print("DB path: " + db_path)
        self.db = ScreencapDatabase(db_path)
        db_size = self.db.get_database_size()
        debug_print("DB size: {:.2f} MB".format(db_size))
        if db_size > 100:
            deleted = self.db.cleanup_old_entries(30)
            debug_print("Cleaned {} old DB entries".format(deleted))

        self.current_folder = None
        self.nav_history = []
        self.all_widgets = []
        self._pre_screencap_widgets = []  # snapshot before screencaps loaded
        self.show_original = False
        self.screencaps_loaded = False

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        # Navigation bar: Back + path label + Copy Path
        nav_bar = QHBoxLayout()
        self.back_button = QPushButton("← Back")
        self.back_button.clicked.connect(self._go_back)
        self.back_button.setEnabled(False)
        nav_bar.addWidget(self.back_button)

        self.path_label = QLabel("No folder selected")
        self.path_label.setStyleSheet(
            "QLabel { background: #f0f0f0; border: 1px solid #ccc;"
            " border-radius: 3px; padding: 3px 6px; }"
        )
        self.path_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        nav_bar.addWidget(self.path_label)

        copy_path_btn = QPushButton("Copy Path")
        copy_path_btn.clicked.connect(self._copy_current_path)
        nav_bar.addWidget(copy_path_btn)

        main_layout.addLayout(nav_bar)

        # Top bar: folder button + show screencaps + search + result count + checkbox + SRC
        top_bar = QHBoxLayout()

        self.select_folder_button = QPushButton("Select Folder")
        self.select_folder_button.clicked.connect(self.selectFolder)
        top_bar.addWidget(self.select_folder_button)

        self.show_screencaps_checkbox = QCheckBox("Show Screencaps")
        self.show_screencaps_checkbox.setChecked(False)
        self.show_screencaps_checkbox.setEnabled(False)
        self.show_screencaps_checkbox.stateChanged.connect(self._on_show_screencaps_toggled)
        top_bar.addWidget(self.show_screencaps_checkbox)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search by filename...")
        self.search_box.textChanged.connect(self._on_search_changed)
        top_bar.addWidget(self.search_box)

        self.result_label = QLabel("")
        self.result_label.setFixedWidth(120)
        top_bar.addWidget(self.result_label)

        self.original_names_checkbox = QCheckBox("Show Original Names")
        self.original_names_checkbox.setChecked(False)
        self.original_names_checkbox.stateChanged.connect(self._on_original_names_toggled)
        top_bar.addWidget(self.original_names_checkbox)

        sort_label = QLabel("Sort:")
        top_bar.addWidget(sort_label)
        self.sort_combo = QComboBox()
        self.sort_combo.addItem("Anagram Name")
        self.sort_combo.addItem("Original Name")
        self.sort_combo.addItem("File Size")
        self.sort_combo.currentIndexChanged.connect(self._on_sort_changed)
        top_bar.addWidget(self.sort_combo)

        self.src_button = QPushButton("SRC")
        self.src_button.clicked.connect(self.open_src_folder)
        top_bar.addWidget(self.src_button)

        self.delete_selected_button = QPushButton("🗑 Delete Selected")
        self.delete_selected_button.setStyleSheet(
            "QPushButton { color: #c00; font-weight: bold; }"
            "QPushButton:hover { background: #ffe0e0; }"
        )
        self.delete_selected_button.clicked.connect(self._delete_selected)
        top_bar.addWidget(self.delete_selected_button)

        main_layout.addLayout(top_bar)

        self.scroll_area = QScrollArea()
        self.scroll_area_widget = QWidget()
        self.scroll_area_layout = QGridLayout(self.scroll_area_widget)
        self.scroll_area.setWidget(self.scroll_area_widget)
        self.scroll_area.setWidgetResizable(True)
        main_layout.addWidget(self.scroll_area)

        self.trash_zone = TrashDropZone()
        self.trash_zone.file_deleted.connect(self._on_file_deleted)

        self.move_zone = MoveDropZone()
        self.move_zone.file_moved.connect(self._on_file_deleted)  # same: remove from view

        action_bar = QHBoxLayout()
        action_bar.addWidget(self.trash_zone)
        action_bar.addWidget(self.move_zone)
        main_layout.addLayout(action_bar)

    def selectFolder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Directory")
        if folder:
            self.nav_history.clear()
            self._navigate_to(folder)

    def open_src_folder(self):
        self.nav_history.clear()
        self._navigate_to("C:\\Users\\ScriptKiddie\\My Drive\\Faecs")

    def _go_back(self):
        if self.nav_history:
            folder = self.nav_history.pop()
            self._load_folder(folder)
            self._update_nav_ui()

    def _navigate_to(self, folder):
        if self.current_folder:
            self.nav_history.append(self.current_folder)
        self._load_folder(folder)
        self._update_nav_ui()

    def _update_nav_ui(self):
        self.back_button.setEnabled(bool(self.nav_history))
        self.path_label.setText(self.current_folder or "No folder selected")

    def _copy_current_path(self):
        if self.current_folder:
            QApplication.clipboard().setText(self.current_folder.replace('/', '\\'))

    def _load_folder(self, folder):
        self.current_folder = folder
        self.screencaps_loaded = False
        self._pre_screencap_widgets = []
        # Reset show-screencaps checkbox without triggering the handler
        self.show_screencaps_checkbox.blockSignals(True)
        self.show_screencaps_checkbox.setChecked(False)
        self.show_screencaps_checkbox.blockSignals(False)
        self.search_box.blockSignals(True)
        self.search_box.clear()
        self.search_box.blockSignals(False)
        self._clear_grid()
        self.all_widgets = []

        try:
            entries = os.listdir(folder)
        except PermissionError:
            return

        sort_index = self.sort_combo.currentIndex()
        if sort_index == 1:  # Original Name
            folders = sorted(
                [e for e in entries if os.path.isdir(os.path.join(folder, e))],
                key=lambda e: natural_sort_key(decode_anagram_filename(e))
            )
            files = sorted(
                [e for e in entries if os.path.isfile(os.path.join(folder, e))],
                key=lambda e: natural_sort_key(decode_anagram_filename(e))
            )
        elif sort_index == 2:  # File Size
            folders = sorted(
                [e for e in entries if os.path.isdir(os.path.join(folder, e))],
                key=natural_sort_key
            )
            files = sorted(
                [e for e in entries if os.path.isfile(os.path.join(folder, e))],
                key=lambda e: os.path.getsize(os.path.join(folder, e))
            )
        else:  # Anagram Name
            folders = sorted(
                [e for e in entries if os.path.isdir(os.path.join(folder, e))],
                key=natural_sort_key
            )
            files = sorted(
                [e for e in entries if os.path.isfile(os.path.join(folder, e))],
                key=natural_sort_key
            )

        for folder_name in folders:
            fp = os.path.join(folder, folder_name)
            fw = FolderWidget(fp, show_original=self.show_original)
            fw.folder_clicked.connect(self._navigate_to)
            self.all_widgets.append(fw)

        for file_name in files:
            fp = os.path.join(folder, file_name)
            ext = os.path.splitext(file_name)[1].lower()
            if ext in IMAGE_EXTENSIONS:
                cached = self.db.get_screencap(fp)
                if cached:
                    pixmap = base64_to_pixmap(cached)
                else:
                    pixmap = QPixmap(fp)
                    if pixmap.isNull():
                        try:
                            cv_img = cv2.imread(fp)
                            if cv_img is not None:
                                h, w_px = cv_img.shape[:2]
                                pixmap = QPixmap.fromImage(
                                    QImage(cv_img.data, w_px, h, 3 * w_px,
                                           QImage.Format_RGB888).rgbSwapped()
                                )
                        except Exception:
                            pass
                    if not pixmap.isNull():
                        self.db.save_screencap(fp, pixmap_to_base64_compressed(pixmap))
                if not pixmap.isNull():
                    lbl = Label(pixmap, fp, show_original=self.show_original)
                    self.all_widgets.append(lbl)
                    continue
            vp = VideoPlaceholder(fp, show_original=self.show_original)
            self.all_widgets.append(vp)

        has_videos = any(isinstance(w, VideoPlaceholder) for w in self.all_widgets)
        self.show_screencaps_checkbox.setEnabled(has_videos)
        self.updateLayout()

    def _on_show_screencaps_toggled(self, state):
        if state == Qt.Checked:
            if self.screencaps_loaded:
                return
            self.screencaps_loaded = True
            # Save snapshot so we can revert
            self._pre_screencap_widgets = list(self.all_widgets)
            video_indices = [
                i for i, w in enumerate(self.all_widgets)
                if isinstance(w, VideoPlaceholder)
            ]
            print("Loading screencaps for {} video(s)...".format(len(video_indices)))
            for i in tqdm(video_indices, desc="Generating screencaps", unit="file"):
                w = self.all_widgets[i]
                print("  Screencap: " + w.file_path)
                label = GenerateMedia(w.file_path, self.db)
                if label is not None:
                    label.update_display(self.show_original)
                    self.all_widgets[i] = label
            print("Done.")
            self.updateLayout()
        else:
            # Revert to pre-screencap state
            if self._pre_screencap_widgets:
                self.all_widgets = list(self._pre_screencap_widgets)
            self.screencaps_loaded = False
            self.updateLayout()

    def resizeEvent(self, event):
        if self.current_folder:
            self.updateLayout()
        super(MainWindow, self).resizeEvent(event)

    def _on_search_changed(self, text):
        self.updateLayout()

    def _on_original_names_toggled(self, state):
        self.show_original = (state == Qt.Checked)
        for w in self.all_widgets:
            if hasattr(w, 'update_display'):
                w.update_display(self.show_original)
        self.updateLayout()

    def _on_sort_changed(self, index):
        if self.current_folder:
            self._load_folder(self.current_folder)

    def _clear_grid(self):
        for i in reversed(range(self.scroll_area_layout.count())):
            item = self.scroll_area_layout.itemAt(i)
            if item:
                widget = item.widget()
                if widget:
                    self.scroll_area_layout.removeWidget(widget)
                    widget.setParent(None)

    def updateLayout(self):
        self._clear_grid()
        term = self.search_box.text().lower()

        def matches(w):
            if not term:
                return True
            if isinstance(w, FolderWidget):
                return (term in w.anagram_name.lower() or term in w.decoded_name.lower())
            if hasattr(w, 'anagram_filename'):
                return (term in w.anagram_filename.lower() or term in w.decoded_filename.lower())
            return True

        visible = [w for w in self.all_widgets if matches(w)]
        self.result_label.setText("{}/{} items".format(len(visible), len(self.all_widgets)))

        available_width = self.scroll_area.width() - 30
        num_cols = max(1, min(5, available_width // 250))
        thumb_width = (available_width // num_cols) - 20
        for idx, widget in enumerate(visible):
            row, col = divmod(idx, num_cols)
            self.scroll_area_layout.addWidget(widget, row, col)
            widget.setMinimumSize(thumb_width, thumb_width)
            widget.setMaximumSize(thumb_width * 2, thumb_width * 2)

    def _on_file_deleted(self, file_path):
        self.all_widgets = [
            w for w in self.all_widgets
            if getattr(w, 'file_path', None) != file_path
        ]
        self.updateLayout()

    def _delete_selected(self):
        to_delete = [
            w for w in self.all_widgets
            if hasattr(w, 'select_checkbox') and w.select_checkbox.isChecked()
        ]
        if not to_delete:
            return
        for w in to_delete:
            try:
                os.remove(w.file_path)
                self.all_widgets.remove(w)
            except Exception as e:
                print("Could not delete: " + w.file_path + ": " + str(e))
        self.updateLayout()

    def displayScreencaps(self, folder):
        self.nav_history.clear()
        self._navigate_to(folder)


class VideoOrganizer(QMainWindow):
    def __init__(self):
        super(VideoOrganizer, self).__init__()
        self.screencaps = {}
        self.current_organizing_folder = None
        self.drop_area_hbox = None
        self.db = ScreencapDatabase(os.environ.get('META_DB_PATH', 'screencaps.db'))
        self._initUI()

    def _initUI(self):
        self.setWindowTitle("Video Organizer")
        self.setGeometry(100, 100, 800, 600)
        central = QWidget()
        self.setCentralWidget(central)
        self.top_layout = QVBoxLayout(central)

        select_button = QPushButton("Select Video Folder")
        select_button.clicked.connect(self.selectFolder)
        self.top_layout.addWidget(select_button)

        rearrange_button = QPushButton("Rearrange Images")
        rearrange_button.clicked.connect(self.rearrange_images)
        self.top_layout.addWidget(rearrange_button)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        self.thumbnail_widget = QWidget()
        self.thumbnail_layout = QGridLayout(self.thumbnail_widget)
        self.thumbnail_layout.setSpacing(10)
        scroll_area.setWidget(self.thumbnail_widget)
        self.top_layout.addWidget(scroll_area)

    def _add_drop_area_layout(self, folder_names_mapping):
        if self.drop_area_hbox is not None:
            for i in reversed(range(self.drop_area_hbox.count())):
                w = self.drop_area_hbox.itemAt(i).widget()
                if w:
                    self.drop_area_hbox.removeWidget(w)
                    w.deleteLater()
            self.top_layout.removeItem(self.drop_area_hbox)
        self.drop_area_hbox = QHBoxLayout()
        for actual_name, shown_name in folder_names_mapping.items():
            folder_path = os.path.join(self.VideoFolder, actual_name)
            if not os.path.exists(folder_path):
                os.makedirs(folder_path)
            drop_area = DropArea(
                actual_folder_text=actual_name,
                text_shown=shown_name + "\n Drop Area",
            )
            drop_area.file_dropped.connect(self.remove_thumbnail)
            self.drop_area_hbox.addWidget(drop_area)
        self.top_layout.addLayout(self.drop_area_hbox)

    def rearrange_images(self):
        self._clear_screencaps()
        if self.current_organizing_folder:
            self.loadScreencapsGivenFolder(self.current_organizing_folder)

    def _clear_screencaps(self):
        for file_path in list(self.screencaps.keys()):
            self.remove_screencap(file_path)

    def selectFolder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Directory")
        if folder:
            self.current_organizing_folder = folder
            self.loadScreencapsGivenFolder(folder)

    def loadScreencapsGivenFolder(self, folder):
        self.VideoFolder = folder
        self.loadScreenCaps(folder)
        folder_names_mapping = {
            "BocbkoSu": "BoobSuck",
            "Colgwir": "Cowgirl",
            "Miaysrson": "Missionary",
            "sFoitaradAntMneoyurplab": "ForeplayAndMasturbation",
            "dooniiotgsgyP": "DoggyPosition",
            "iSiynhBOeresddwa": "SidewaysAndBentOver",
            "sortefco": "Softcore",
            "Trsah": "Trash",
            "dStnlHOerngadi": "StandingOrHeld",
            "iSiogtenrstIntin": "SittingInsertion",
            "OPoVfPwi-enVitO": "PointOfView-POV",
            "StiernoyL": "StoryLine",
        }
        self._add_drop_area_layout(folder_names_mapping)

    def loadScreenCaps(self, folder):
        row, col = 0, 0
        max_cols = 3
        for file in tqdm(os.listdir(folder), desc="Loading screencaps"):
            file_path = os.path.join(folder, file)
            if not os.path.isfile(file_path):
                continue
            if file_path in self.screencaps:
                label = self.screencaps[file_path]
            else:
                label = GenerateMedia(file_path, self.db)
                if label is None:
                    continue
            self.screencaps[file_path] = label
            self.thumbnail_layout.addWidget(label, row, col)
            col += 1
            if col >= max_cols:
                col = 0
                row += 1

    def remove_screencap(self, file_path):
        if file_path in self.screencaps:
            thumbnail = self.screencaps[file_path]
            self.thumbnail_layout.removeWidget(thumbnail)

    def remove_thumbnail(self, file_path):
        if file_path in self.screencaps:
            thumbnail = self.screencaps[file_path]
            self.thumbnail_layout.removeWidget(thumbnail)
            thumbnail.deleteLater()
            del self.screencaps[file_path]


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
        description='Clip Organizer -- unified media viewer and organizer'
    )
    parser.add_argument('--debug', action='store_true', help='Enable debug output')
    parser.add_argument(
        '--organize', action='store_true',
        help='Launch the drag-and-drop video organizer instead of the viewer',
    )
    parser.add_argument('folder_path', nargs='?', help='Folder to open on startup')
    args = parser.parse_args()

    DEBUG_MODE = args.debug

    app = QApplication(sys.argv)

    if args.organize:
        window = VideoOrganizer()
        if args.folder_path and os.path.isdir(args.folder_path):
            window.loadScreencapsGivenFolder(args.folder_path)
    else:
        window = MainWindow()
        if args.folder_path and os.path.isdir(args.folder_path):
            window.displayScreencaps(args.folder_path)

    window.show()
    sys.exit(app.exec_())
