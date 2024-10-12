from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QGridLayout

app = QApplication([])

# Create the main window and main layout (outer grid layout)
main_window = QWidget()
outer_layout = QGridLayout()

# Apply a border to the main window to show the outer layout boundaries
main_window.setStyleSheet("border: 4px solid blue;")

# Create a widget to hold the inner grid layout
# inner_widget = QWidget()
# inner_layout = QGridLayout()

# Apply a border to the inner widget to show the inner layout boundaries


colors = [
    'red', 'green', 'blue', 'yellow', 'purple', 'orange', 'pink', 'brown', 
    'cyan', 'magenta', 'lime', 'maroon', 'navy', 'olive', 'teal'
]

inner_layouts = []

for i in range(15):
    inner_layout = QGridLayout()
    for row in range(4):
        for col in range(4):
            label = QLabel(f'Label {i+1}-{row*4+col+1}')
            label.setStyleSheet(f"border: 3px solid black;")
            inner_layout.addWidget(label, row, col)
    inner_layouts.append(inner_layout)

    # Create inner widgets and set their layouts
    inner_widgets = []
    for i, layout in enumerate(inner_layouts):
        inner_widget = QWidget()
        inner_widget.setLayout(layout)
        inner_widget.setStyleSheet(f"border: 2px dashed {colors[i % len(colors)]};")
        inner_widgets.append(inner_widget)
        outer_layout.addWidget(inner_widget, i // 4, i % 4)


# Set the outer layout to the main window
main_window.setLayout(outer_layout)

# Show the main window
main_window.show()

app.exec_()
