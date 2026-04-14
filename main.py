import sys
import os
import sqlite3
import base64
import argparse
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
)
from PyQt5.QtGui import QPixmap, QDrag, QImage
from PyQt5.QtCore import Qt, QBuffer, QMimeData, pyqtSignal
import cv2
import numpy as np
import subprocess
from tqdm import tqdm

# Global debug flag
DEBUG_MODE = False

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
    def __init__(self, pixmap, file_path, parent=None):
        super(Label, self).__init__(parent)
        self.original_pixmap = pixmap
        self.file_path = file_path
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(2)

        self.image_label = QLabel()
        self.image_label.setPixmap(pixmap)
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.image_label)

        filename = os.path.basename(file_path)
        decoded_filename = decode_anagram_filename(filename)
        self.decoded_filename = decoded_filename  # stored for search filtering
        self.filename_label = QLabel(decoded_filename)
        self.filename_label.setAlignment(Qt.AlignCenter)
        self.filename_label.setWordWrap(True)
        self.filename_label.setStyleSheet(
            "QLabel { font-size: 10px; color: #333;"
            " background-color: rgba(255,255,255,180);"
            " border: 1px solid #ccc; border-radius: 3px;"
            " padding: 2px; margin: 1px; }"
        )
        layout.addWidget(self.filename_label)

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
        play_action = menu.addAction("Play") if ext not in IMAGE_EXTENSIONS else None
        action = menu.exec_(self.mapToGlobal(position))
        if action == copy_action:
            self.copy_to_clipboard()
        elif play_action and action == play_action:
            self.play_video()

    def copy_to_clipboard(self):
        QApplication.clipboard().setText(self.file_path.replace('/', '\\'))

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
        self.screencaps = []

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        # Top bar: folder button + search box + result count
        top_bar = QHBoxLayout()
        self.select_folder_button = QPushButton("Select Folder")
        self.select_folder_button.clicked.connect(self.selectFolder)
        top_bar.addWidget(self.select_folder_button)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search by filename...")
        self.search_box.textChanged.connect(self._on_search_changed)
        top_bar.addWidget(self.search_box)

        self.result_label = QLabel("")
        self.result_label.setFixedWidth(120)
        top_bar.addWidget(self.result_label)

        main_layout.addLayout(top_bar)

        self.scroll_area = QScrollArea()
        self.scroll_area_widget = QWidget()
        self.scroll_area_layout = QGridLayout(self.scroll_area_widget)
        self.scroll_area.setWidget(self.scroll_area_widget)
        self.scroll_area.setWidgetResizable(True)
        main_layout.addWidget(self.scroll_area)

    def selectFolder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Directory")
        if folder:
            self.displayScreencaps(folder)

    def resizeEvent(self, event):
        if self.current_folder and self.screencaps:
            self.updateLayout()
        super(MainWindow, self).resizeEvent(event)

    def _on_search_changed(self, text):
        self.updateLayout()

    def updateLayout(self):
        for i in reversed(range(self.scroll_area_layout.count())):
            w = self.scroll_area_layout.itemAt(i).widget()
            if w:
                self.scroll_area_layout.removeWidget(w)
                w.setParent(None)

        term = self.search_box.text().lower()
        visible = [
            s for s in self.screencaps
            if term in s.decoded_filename.lower()
        ] if term else self.screencaps

        self.result_label.setText(
            "{}/{} files".format(len(visible), len(self.screencaps))
        )

        available_width = self.scroll_area.width() - 30
        num_cols = max(1, min(5, available_width // 250))
        thumb_width = (available_width // num_cols) - 20
        for idx, screencap in enumerate(visible):
            row, col = divmod(idx, num_cols)
            self.scroll_area_layout.addWidget(screencap, row, col)
            screencap.setMinimumSize(thumb_width, thumb_width)
            screencap.setMaximumSize(thumb_width * 2, thumb_width * 2)

    def displayScreencaps(self, folder):
        self.current_folder = folder
        self.search_box.blockSignals(True)
        self.search_box.clear()
        self.search_box.blockSignals(False)
        for i in reversed(range(self.scroll_area_layout.count())):
            w = self.scroll_area_layout.itemAt(i).widget()
            if w:
                self.scroll_area_layout.removeWidget(w)
                w.setParent(None)
        files = []
        for root, _, filenames in os.walk(folder):
            for f in filenames:
                files.append(os.path.join(root, f))
        self.screencaps = []
        for f in tqdm(files, desc="Loading media"):
            label = GenerateMedia(f, self.db)
            if label:
                self.screencaps.append(label)
        self.updateLayout()


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
