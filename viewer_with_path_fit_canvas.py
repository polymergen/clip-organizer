# filepath: d:\codes_native_windows\ClipOrganizer\viewer_with_path_fit_canvas.py
import sys
import os
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
    QSizePolicy,
)
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtCore import Qt, QSize
import cv2
import numpy as np
import subprocess
from tqdm import tqdm
import pickle


# Default values, will be adjusted dynamically
SCREENCAP_HEIGHT = 800
SCREENCAP_WIDTH = 800
SCREENCAP_FRAME_COUNT = 9
DEFAULT_COLUMNS = 3

class Label(QLabel):
    def __init__(self, pixmap, file_path, parent=None):
        super().__init__(parent)
        self.original_pixmap = pixmap  # Store the original pixmap
        self.setPixmap(pixmap)
        self.file_path = file_path
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setAlignment(Qt.AlignCenter)

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
    
    def resizeEvent(self, event):
        # Rescale the pixmap to fit the new size when the label is resized
        if not self.original_pixmap.isNull():
            scaled_pixmap = self.original_pixmap.scaled(
                self.width(), 
                self.height(),
                Qt.KeepAspectRatio, 
                Qt.SmoothTransformation
            )
            self.setPixmap(scaled_pixmap)
        super().resizeEvent(event)

def GenerateScreencaps(input_video_file):
    # Capture the video using cv2.VideoCapture
    # Replace the path with the path to the video file you want to use
    try:
        output_image = cv2.imread(input_video_file)
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
        screencap = Label(q_img, input_video_file)
        return screencap
    except:
        pass
    
    capture = cv2.VideoCapture(input_video_file)

    # print error message if opening video failed
    if not capture.isOpened():
            print(f"Error opening video: {input_video_file}")
            
    # Get the number of frames in the video
    num_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    # print(f"Num frames: {num_frames}")

    if num_frames < 1: 
        print("No frames in video {}".format(input_video_file))
        return

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

    q_img = QPixmap.fromImage(
                    QImage(
                        output_image.data,
                        output_image_width,
                        output_image_height,
                        bytes_per_line,
                        QImage.Format_RGB888,
                    ).rgbSwapped()
                )
    
    screencap = Label(q_img, input_video_file)
    return screencap

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Screencap Viewer")
        self.setGeometry(100, 100, 1200, 800)
        
        self.current_folder = None  # Track current folder for resizing events
        self.screencaps = []  # Store all screencaps for reuse during resizing

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
        
        # Check if command line argument was passed
        if len(sys.argv) > 1:
            folder_path = sys.argv[1]
            if os.path.isdir(folder_path):
                print(f"Using folder path from command line: {folder_path}")
                self.displayScreencaps(folder_path)
            else:
                print(f"Warning: Provided path is not a valid directory: {folder_path}")

    def selectFolder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Directory", "D:/awan/iCloudDrive/CloudData/Settings/Config/Google/UserSettings/Mapdata")

        if folder:
            self.displayScreencaps(folder)

    def resizeEvent(self, event):
        # When window is resized, update the layout if we have a current folder
        if self.current_folder and len(self.screencaps) > 0:
            self.updateLayout()
        super().resizeEvent(event)
            
    def updateLayout(self):
        """Update the layout based on current window size"""
        # Clear current layout
        for i in reversed(range(self.scroll_area_layout.count())): 
            widget_to_remove = self.scroll_area_layout.itemAt(i).widget()
            if widget_to_remove:
                self.scroll_area_layout.removeWidget(widget_to_remove)
                widget_to_remove.setParent(None)
        
        # Calculate how many columns can fit
        available_width = self.scroll_area.width() - 30  # Account for scrollbar and margins
        
        # Determine optimal number of columns based on available width
        # Minimum 1 column, maximum 5 columns
        num_cols = max(1, min(5, available_width // 250))
        
        # Calculate thumbnail size based on available width
        thumb_width = (available_width // num_cols) - 20  # Account for grid spacing
        
        row, col = 0, 0
        
        # Add screencaps to the layout
        for screencap in self.screencaps:
            self.scroll_area_layout.addWidget(screencap, row, col)
            
            # Force a specific size for the cell
            screencap.setMinimumSize(thumb_width, thumb_width)
            screencap.setMaximumSize(thumb_width * 2, thumb_width * 2)
            
            col += 1
            if col >= num_cols:
                col = 0
                row += 1

    def displayScreencaps(self, folder):
        self.current_folder = folder  # Store current folder
        
        # Clear existing widgets
        for i in reversed(range(self.scroll_area_layout.count())): 
            widget_to_remove = self.scroll_area_layout.itemAt(i).widget()
            if widget_to_remove:
                self.scroll_area_layout.removeWidget(widget_to_remove)
                widget_to_remove.setParent(None)
        
        video_files = self.getVideoFiles(folder)
        
        # Generate screencaps
        self.screencaps = []
        for video_file in tqdm(video_files, desc="Generating screencaps"):
            screencap = GenerateScreencaps(video_file)
            if screencap:
                self.screencaps.append(screencap)
                
        # Update the layout with the new screencaps
        self.updateLayout()

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
