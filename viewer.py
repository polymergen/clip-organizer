import sys
import os
import sqlite3
import base64
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
        cursor.execute('''
            INSERT OR REPLACE INTO screencaps (file_path, image_data) 
            VALUES (?, ?)
        ''', (file_path, image_data))
        conn.commit()
        conn.close()

def pixmap_to_base64(pixmap):
    """Convert QPixmap to base64 encoded string."""
    buffer = QBuffer()
    buffer.open(QBuffer.WriteOnly)
    pixmap.save(buffer, "PNG")
    image_data = buffer.data().data()
    return base64.b64encode(image_data).decode('utf-8')

def base64_to_pixmap(base64_string):
    """Convert base64 encoded string to QPixmap."""
    image_data = base64.b64decode(base64_string.encode('utf-8'))
    pixmap = QPixmap()
    pixmap.loadFromData(image_data)
    return pixmap

class Label(QLabel):
    def __init__(self, pixmap, file_path, parent=None):
        super().__init__(parent)
        self.setPixmap(pixmap)
        self.file_path = file_path
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)


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
        print(f"Using cached screencap for {input_video_file}")
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
                        QImage.Format_RGB888,
                    ).rgbSwapped()
                )
            # Save to database
            db.save_screencap(input_video_file, pixmap_to_base64(q_img))
            
            screencap = Label(
                q_img.scaled(SCREENCAP_WIDTH, SCREENCAP_HEIGHT, Qt.KeepAspectRatio), 
                input_video_file
            )
            return screencap
    except Exception:
        pass
    
    # If image reading failed, try video processing
    print(f"Generating screencap for video: {input_video_file}")
    capture = cv2.VideoCapture(input_video_file)

    # print error message if opening video failed
    if not capture.isOpened():
            print(f"Error opening video: {input_video_file}")
            return None
            
    # Get the number of frames in the video
    num_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    # print(f"Num frames: {num_frames}")

    if num_frames < 1: 
        print("No frames in video {}".format(input_video_file))
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
    db.save_screencap(input_video_file, pixmap_to_base64(q_img))
    
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
        print("Using database path:", db_path)
        self.db = ScreencapDatabase(db_path)

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
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())