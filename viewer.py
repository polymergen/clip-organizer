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
    QPushButton,
    QFileDialog,
    QLabel,
    QScrollArea,
    QGridLayout,
    QMenu,
)
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtCore import Qt, QBuffer
import cv2
import numpy as np
import subprocess
from tqdm import tqdm

# Global debug flag
DEBUG_MODE = False

def debug_print(*args, **kwargs):
    """Print only if debug mode is enabled."""
    if DEBUG_MODE:
        print(*args, **kwargs)

def decode_anagram_filename(filename):
    """
    Decode anagram filename by looking up in the anagram record file.
    Uses the same logic as the PowerShell reverse_anagram_file.ps1
    """
    try:
        # Get the anagram file path from environment variable
        record_file = os.environ.get('ANAGRAM_FILE_PATH')
        
        if not record_file:
            debug_print(f"⚠️  ANAGRAM_FILE_PATH environment variable not set for file: {filename}")
            return filename
            
        if not os.path.exists(record_file):
            debug_print(f"⚠️  Anagram file does not exist: {record_file}")
            return filename
        
        debug_print(f"✓ Using anagram file: {record_file}")
        
        # Remove file extension for processing
        name_without_ext = os.path.splitext(filename)[0]
        extension = os.path.splitext(filename)[1]
        
        # Read the anagram record file
        with open(record_file, 'r', encoding='utf-8') as f:
            records = f.readlines()
            
        debug_print(f"Finding anagram for: '{name_without_ext}'")
        debug_print(f"ANAGRAM_FILE_PATH: {record_file}")
        debug_print(f"File has {len(records)} records")
        
        # Look for the anagram in the records
        for i, record in enumerate(records):
            record = record.strip()
            if ',' in record:
                parts = record.split(',', 1)  # Split only on first comma
                if len(parts) == 2:
                    original_name, anagram = parts[0].strip(), parts[1].strip()
                    debug_print(f"Record {i+1}: original='{original_name}', anagram='{anagram}'")
                    
                    # Check if the anagram matches our filename (without extension)
                    if anagram == name_without_ext:
                        debug_print(f"✓ EXACT MATCH FOUND! Returning: {original_name + extension}")
                        return original_name + extension
                else:
                    debug_print(f"Record {i+1}: Invalid format (no comma): '{record}'")
            else:
                debug_print(f"Record {i+1}: Skipping empty/invalid line: '{record}'")
        
        # If no match found, return original filename
        debug_print(f"❌ No anagram found for: '{name_without_ext}'")
        return filename
        
    except Exception as e:
        # If any error occurs, return original filename
        debug_print(f"❌ Error decoding anagram for '{filename}': {e}")
        return filename



SCREENCAP_HEIGHT = 800
SCREENCAP_WIDTH = 800
SCREENCAP_FRAME_COUNT = 9

class ScreencapDatabase:
    def __init__(self, db_path):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize the database and create the screencaps table if it doesn't exist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS screencaps (
                file_path TEXT PRIMARY KEY,
                image_data TEXT NOT NULL,
                file_size INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()
    def get_screencap(self, file_path):
        """Get screencap from database by file path."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT image_data FROM screencaps WHERE file_path = ?', (file_path,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else None
    
    def save_screencap(self, file_path, image_data):
        """Save screencap to database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get file size if file exists
        file_size = 0
        try:
            if os.path.exists(file_path):
                file_size = os.path.getsize(file_path)
        except Exception:
            pass
            
        cursor.execute('''
            INSERT OR REPLACE INTO screencaps (file_path, image_data, file_size) 
            VALUES (?, ?, ?)
        ''', (file_path, image_data, file_size))
        conn.commit()
        conn.close()
    
    def get_database_size(self):
        """Get the size of the database file in MB."""
        try:
            return os.path.getsize(self.db_path) / (1024 * 1024)
        except Exception:
            return 0
    
    def cleanup_old_entries(self, days=30):
        """Remove entries older than specified days."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            DELETE FROM screencaps 
            WHERE created_at < datetime('now', '-{} days')
        '''.format(days))
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        return deleted

def pixmap_to_base64_compressed(pixmap, max_size=400, quality=75):
    """Convert QPixmap to compressed base64 encoded string with adaptive compression."""
    # Determine compression level based on original size
    original_area = pixmap.width() * pixmap.height()
    
    # Use more aggressive compression for larger images
    if original_area > 2000000:  # > 2 megapixels
        max_size = 300
        quality = 60
    elif original_area > 1000000:  # > 1 megapixel
        max_size = 350
        quality = 65
    elif original_area > 500000:  # > 0.5 megapixels
        max_size = 400
        quality = 70
    
    # Resize the pixmap to reduce size
    if pixmap.width() > max_size or pixmap.height() > max_size:
        pixmap = pixmap.scaled(max_size, max_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    
    buffer = QBuffer()
    buffer.open(QBuffer.WriteOnly)
    # Use JPEG format with quality compression
    pixmap.save(buffer, "JPEG", quality)
    image_data = buffer.data().data()
    return base64.b64encode(image_data).decode('utf-8')

def base64_to_pixmap(base64_string):
    """Convert base64 encoded string to QPixmap."""
    image_data = base64.b64decode(base64_string.encode('utf-8'))
    pixmap = QPixmap()
    pixmap.loadFromData(image_data)
    return pixmap

class Label(QWidget):
    def __init__(self, pixmap, file_path, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        
        # Create layout for image and filename
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(2)
        
        # Create image label
        self.image_label = QLabel()
        self.image_label.setPixmap(pixmap)
        self.image_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.image_label)
        
        # Create filename label
        filename = os.path.basename(file_path)
        decoded_filename = decode_anagram_filename(filename)
        
        self.filename_label = QLabel(decoded_filename)
        self.filename_label.setAlignment(Qt.AlignCenter)
        self.filename_label.setWordWrap(True)
        self.filename_label.setStyleSheet("""
            QLabel {
                font-size: 10px;
                color: #333;
                background-color: rgba(255, 255, 255, 180);
                border: 1px solid #ccc;
                border-radius: 3px;
                padding: 2px;
                margin: 1px;
            }
        """)
        layout.addWidget(self.filename_label)
        
        # Set size policy
        self.setSizePolicy(QLabel().sizePolicy())

    def setPixmap(self, pixmap):
        """Compatibility method for existing code"""
        self.image_label.setPixmap(pixmap)

    def show_context_menu(self, position):
        context_menu = QMenu(self)
        copy_action = context_menu.addAction("Copy")
        action = context_menu.exec_(self.mapToGlobal(position))

        if action == copy_action:
            self.copy_to_clipboard()

    def copy_to_clipboard(self):
        clipboard = QApplication.clipboard()
        self.file_path = self.file_path.replace('/', '\\')
        clipboard.setText(self.file_path)

    def play_video(self):
        try:
            subprocess.Popen(['mpv', self.file_path])
        except FileNotFoundError:
            print("Error: mpv is not installed or not in the system PATH")
    
    def enterEvent(self, event):
        file_size = os.path.getsize(self.file_path)
        if file_size < 1024:
            file_size_str = f"{file_size} B"
        elif file_size < 1024 ** 2:
            file_size_str = f"{file_size / 1024:.2f} KB"
        elif file_size < 1024 ** 3:
            file_size_str = f"{file_size / 1024 ** 2:.2f} MB"
        else:
            file_size_str = f"{file_size / 1024 ** 3:.2f} GB"
        
        self.setToolTip(self.file_path + " Size: " + str(file_size_str))
        super().enterEvent(event)

def GenerateScreencaps(input_video_file, db):
    """Generate screencaps with database caching."""
    # First check if screencap exists in database
    cached_data = db.get_screencap(input_video_file)
    if cached_data:
        debug_print(f"Using cached screencap for {input_video_file}")
        cached_pixmap = base64_to_pixmap(cached_data)
        screencap = Label(
            cached_pixmap.scaled(SCREENCAP_WIDTH, SCREENCAP_HEIGHT, Qt.KeepAspectRatio), 
            input_video_file
        )
        return screencap
    
    # If not in database, generate new screencap
    # First try to read as image file
    try:
        output_image = cv2.imread(input_video_file)
        if output_image is not None:
            output_image_width = output_image.shape[1]
            output_image_height = output_image.shape[0]
            bytes_per_line = 3 * output_image_width
            q_img = QPixmap.fromImage(
                    QImage(
                        output_image.data,
                        output_image_width,
                        output_image_height,
                        bytes_per_line,
                        QImage.Format_RGB888,                    ).rgbSwapped()
                )
            # Save to database
            db.save_screencap(input_video_file, pixmap_to_base64_compressed(q_img))
            
            screencap = Label(
                q_img.scaled(SCREENCAP_WIDTH, SCREENCAP_HEIGHT, Qt.KeepAspectRatio), 
                input_video_file
            )
            return screencap
    except Exception:
        pass
    
    # If image reading failed, try video processing
    debug_print(f"Generating screencap for video: {input_video_file}")
    capture = cv2.VideoCapture(input_video_file)

    # print error message if opening video failed
    if not capture.isOpened():
        print(f"Error opening video: {input_video_file}")
        return None
            
    # Get the number of frames in the video
    num_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    # debug_print(f"Num frames: {num_frames}")

    if num_frames < 1: 
        debug_print("No frames in video {}".format(input_video_file))
        return None

    # Prompt the user for the number of images they want to generate
    # num_images = int(input('How many images do you want to generate? '))
    num_images = SCREENCAP_FRAME_COUNT

    # Calculate the number of rows and columns so that they are about the same value
    num_rows = int(num_images ** 0.5)
    num_cols = num_images // num_rows

    # Get the width and height of the frames in the video
    frame_width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    # print("Frame width: {} Frame height: {}".format(frame_width, frame_height))

    # Create an empty image with the correct dimensions
    output_image = np.zeros((num_rows * frame_height, num_cols * frame_width, 3), np.uint8)

    # Loop through the number of rows and columns, capturing a frame from the video and
    # adding it to the output image at the correct position
    for row in range(num_rows):
        for col in range(num_cols):
            # Calculate the frame number for this position
            frame_num = row * num_cols + col

            # Calculate the time in seconds for this frame
            time = frame_num * num_frames / num_images

            # print("Time: {}".format(convert(time)))

            # Set the capture to the correct time
            capture.set(cv2.CAP_PROP_POS_FRAMES, time)

            # Read the frame from the capture
            ret, frame = capture.read()

            if not ret:
                # print("Error reading frame")
                continue 

            # Add the frame to the output image
            # print("{}:{}, {}:{}".format(row * frame_height, (row + 1) * frame_height, col * frame_width, (col + 1) * frame_width))
            output_image[row * frame_height:(row + 1) * frame_height, col * frame_width:(col + 1) * frame_width] = frame

    output_image_width = output_image.shape[1]
    output_image_height = output_image.shape[0]
    bytes_per_line = 3 * output_image_width

    # show image
    # cv2.imshow("Output Image", output_image)
    # cv2.waitKey(0)

    q_img = QPixmap.fromImage(
        QImage(
            output_image.data,
            output_image_width,
            output_image_height,
            bytes_per_line,
            QImage.Format_RGB888,
        ).rgbSwapped()
    )
    
    # Save to database
    db.save_screencap(input_video_file, pixmap_to_base64_compressed(q_img))
    
    screencap = Label(
        q_img.scaled(SCREENCAP_WIDTH, SCREENCAP_HEIGHT, Qt.KeepAspectRatio), 
        input_video_file
    )
    return screencap

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Screencap Viewer")
        self.setGeometry(100, 100, 1200, 800)
        # Initialize database
        db_path = os.environ.get('META_DB_PATH', 'screencaps.db')
        debug_print(f"Using database path: {db_path}")
        self.db = ScreencapDatabase(db_path)
        
        # Print database info
        db_size = self.db.get_database_size()
        debug_print(f"Database size: {db_size:.2f} MB")
        
        # Cleanup old entries if database is getting large
        if db_size > 100:  # If database is over 100MB
            deleted = self.db.cleanup_old_entries(30)
            debug_print(f"Cleaned up {deleted} old entries from database")

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        self.layout = QVBoxLayout(self.central_widget)

        self.select_folder_button = QPushButton("Select Folder")
        self.select_folder_button.clicked.connect(self.selectFolder)
        self.layout.addWidget(self.select_folder_button)

        self.scroll_area = QScrollArea()
        self.scroll_area_widget = QWidget()
        self.scroll_area_layout = QGridLayout(self.scroll_area_widget)
        self.scroll_area.setWidget(self.scroll_area_widget)
        self.scroll_area.setWidgetResizable(True)
        self.layout.addWidget(self.scroll_area)

    def selectFolder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Directory", "D:/awan/iCloudDrive/CloudData/Settings/Config/Google/UserSettings/Mapdata")
        
        if folder:
            self.displayScreencaps(folder)

    def displayScreencaps(self, folder):
        for i in reversed(range(self.scroll_area_layout.count())): 
            widget_to_remove = self.scroll_area_layout.itemAt(i).widget()
            self.scroll_area_layout.removeWidget(widget_to_remove)
            widget_to_remove.setParent(None)

        video_files = self.getVideoFiles(folder)
        row, col = 0, 0
        max_cols = 3

        screencaps = []
        for video_file in tqdm(video_files, desc="Generating screencaps"):
            screencap = GenerateScreencaps(video_file, self.db)
            if screencap:
                screencaps.append(screencap)
        for screencap in screencaps:
            self.scroll_area_layout.addWidget(screencap, row, col)
            col += 1
            if col >= max_cols:
                col = 0
                row += 1

    def getVideoFiles(self, folder):
        video_files = []
        for root, _, files in os.walk(folder):
            for file in files:
                if True:
                    video_files.append(os.path.join(root, file))
        return video_files

if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Screencap Viewer')
    parser.add_argument('--debug', action='store_true', help='Enable debug output')
    args = parser.parse_args()
    
    # Set global debug flag
    DEBUG_MODE = args.debug
    
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())