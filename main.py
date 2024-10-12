import sys
import os
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QFileDialog,
    QLabel,
    QScrollArea,
    QGridLayout,
    QMenu,
)
from PyQt5.QtGui import QPixmap, QDrag, QImage
from PyQt5.QtCore import Qt, QMimeData, QPoint, pyqtSignal
import cv2
import numpy as np
import subprocess
SCREENCAP_HEIGHT = 350
SCREENCAP_WIDTH = 350
SCREENCAP_FRAME_COUNT = 9
colors = [
    "red",
    "green",
    "blue",
    "yellow",
    "purple",
    "orange",
    "pink",
    "brown",
    "cyan",
    "magenta",
    "lime",
    "maroon",
    "navy",
    "olive",
    "teal",
]

def GenerateScreencaps(input_video_file):
    # Capture the video using cv2.VideoCapture
    # Replace the path with the path to the video file you want to use
    capture = cv2.VideoCapture(input_video_file)

    # print error message if opening video failed
    if not capture.isOpened():
            print(f"Error opening video: {input_video_file}")
    # Get the number of frames in the video
    num_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    print(f"Num frames: {num_frames}")

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
    print("Frame width: {} Frame height: {}".format(frame_width, frame_height))

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
                print("Error reading frame")
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
    
    screencap = DraggableLabel(
    q_img.scaled(SCREENCAP_WIDTH, SCREENCAP_HEIGHT, Qt.KeepAspectRatio), input_video_file
    )
    return  screencap


class DropArea(QLabel):
    file_dropped = pyqtSignal(str)  # Signal to emit when a file is dropped

    def __init__(self, text_shown, actual_folder_text, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setText(text_shown)
        # self.setStyleSheet("border: 2px dashed #aaa")
        self.setAcceptDrops(True)
        self._folder_name = actual_folder_text.split("\n")[
            0
        ]  # Assume first line is folder name

    def dragEnterEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dropEvent(self, event):
        file_path = event.mimeData().text()
        file_path_parent = os.path.dirname(file_path)
        parent_of_parent = os.path.dirname(file_path_parent) 
        destination_folder = os.path.join(parent_of_parent, self._folder_name)

        # Create the folder if it doesn't exist
        if not os.path.exists(destination_folder):
            os.makedirs(destination_folder)

        # Move the file
        file_name = os.path.basename(file_path)
        ori_parent_folder = os.path.dirname(file_path)
        new_path = os.path.join(destination_folder, file_name)
        os.rename(file_path, new_path)

        print(f"Moved file {file_name} from {ori_parent_folder} to {self._folder_name}")

        # Emit signal with the original file path
        self.file_dropped.emit(file_path)

    def get_folder_name(self):
        return self._folder_name


class DraggableLabel(QLabel):
    def __init__(self, pixmap, file_path, parent=None):
        super().__init__(parent)
        self.setPixmap(pixmap)
        self.file_path = file_path
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            drag = QDrag(self)
            mime = QMimeData()
            mime.setText(self.file_path)
            drag.setMimeData(mime)
            drag.exec_(Qt.MoveAction)

    def show_context_menu(self, position):
        context_menu = QMenu(self)
        play_action = context_menu.addAction("Play")
        action = context_menu.exec_(self.mapToGlobal(position))

        if action == play_action:
            self.play_video()

    def play_video(self):
        try:
            subprocess.Popen(['mpv', self.file_path])
        except FileNotFoundError:
            print("Error: mpv is not installed or not in the system PATH")


class VideoOrganizer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.screencaps = {}
        self.initUI()

    def initUI(self):
        self.setWindowTitle("Video Organizer")
        self.setGeometry(100, 100, 800, 600)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.mainLayout = QVBoxLayout(central_widget)

        # Button to select folder
        select_button = QPushButton("Select Video Folder")
        select_button.clicked.connect(self.selectFolder)
        self.mainLayout.addWidget(select_button)

        # Scroll area for thumbnails
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        self.screencap_canvas_widget = QWidget()

        self.MainGridLayout = QGridLayout(self.screencap_canvas_widget)
        self.MainGridLayout.setSpacing(10)
        scroll_area.setWidget(self.screencap_canvas_widget)
        self.mainLayout.addWidget(scroll_area)

        self.InnerGridLayouts = []

    def add_drop_area_layout(self, layout, folder_names_mapping):
        drop_area_layout = QHBoxLayout()
        i = 0 
        for actual_name, shown_name in folder_names_mapping.items():
            folder_path = os.path.join(self.ParentFolder, actual_name)
            os.makedirs(folder_path, exist_ok=True)
            drop_area = DropArea(actual_folder_text=actual_name, text_shown=f"{shown_name}\n Drop Area")
            drop_area.file_dropped.connect(self.remove_sreencap)
            drop_area.setStyleSheet(f"border: 2px dashed {colors[i % len(colors)]};")
            i += 1
            drop_area_layout.addWidget(drop_area)
        layout.addLayout(drop_area_layout)

    def selectFolder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Directory")
        row = 0 
        col = 0
        max_cols = 3
        i = 0
        if folder:
            self.ParentFolder = folder
            subfolders = [f.name for f in os.scandir(folder) if f.is_dir()]
            folder_names_mapping = {subfolder: subfolder for subfolder in subfolders}

            for subfolder, _ in folder_names_mapping.items():
                subgrid_layout = self.LoopOverFolderAndGenerateScreencapsPerFileForSubGrid(os.path.join(folder, subfolder))
                if subgrid_layout is None: continue
                subgrid_widget = QWidget()
                subgrid_widget.setStyleSheet(
                    f"""
    border: 2px dashed {colors[i % len(colors)]};
"""
                )

                subgrid_widget.setLayout(subgrid_layout)
                self.MainGridLayout.addWidget(subgrid_widget, row, col)
                i += 1
                col += 1
                if col >= max_cols:
                    col = 0
                    row += 1

            # Drop areas
            self.add_drop_area_layout(self.mainLayout, folder_names_mapping)

    def LoopOverFolderAndGenerateScreencapsPerFileForSubGrid(self, folder):
        row, col = 0, 1
        max_cols = 5  # Adjust this value to change the number of columns
        subgrid = QGridLayout()

        file_list = os.listdir(folder)
        if len(file_list) == 0: return None
        label = QLabel(os.path.basename(folder))
        label.setStyleSheet("background-color: black ; color: white")
        label.setMaximumHeight(SCREENCAP_HEIGHT)
        label.setMaximumWidth(SCREENCAP_WIDTH)
        subgrid.addWidget(label, row, 0)

        for file in file_list:
            file_path = os.path.join(folder, file)
            if os.path.isfile(file_path):
                qpixmap_image = GenerateScreencaps(file_path)
                qpixmap_image.setMaximumHeight(SCREENCAP_HEIGHT)
                qpixmap_image.setMaximumWidth(SCREENCAP_WIDTH)
                self.screencaps[file_path] = (qpixmap_image, subgrid)
                subgrid.addWidget(qpixmap_image, row, col)
                col += 1
                if col >= max_cols:
                    col = 0
                    row += 1
        return subgrid

    def remove_sreencap(self, file_path):
        if file_path in self.screencaps:
            image, subgrid = self.screencaps[file_path]
            subgrid.removeWidget(image)
            image.deleteLater()
            del self.screencaps[file_path]


if __name__ == "__main__":
    app = QApplication(sys.argv)
    ex = VideoOrganizer()
    ex.show()
    sys.exit(app.exec_())
