from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QGridLayout

app = QApplication([])

# Create the main window and main layout (outer grid layout)
main_window = QWidget()
outer_layout = QGridLayout()

# Apply a border to the main window to show the outer layout boundaries
main_window.setStyleSheet("border: 4px solid blue;")

# Create a widget to hold the inner grid layout
inner_widget = QWidget()
inner_layout = QGridLayout()

# Apply a border to the inner widget to show the inner layout boundaries
inner_widget.setStyleSheet("border: 4px dashed red;")

# Add some widgets to the inner layout
label1 = QLabel('Inner Label 1')
label2 = QLabel('Inner Label 2')
inner_layout.addWidget(label1, 0, 0)
inner_layout.addWidget(label2, 0, 1)

# Set the inner layout to the inner widget
inner_widget.setLayout(inner_layout)

# Add the inner widget to the outer layout (placing the grid inside the grid)
outer_layout.addWidget(inner_widget, 0, 0)

# Add other widgets to the outer layout
outer_layout.addWidget(QLabel('Outer Label 1'), 1, 0)
outer_layout.addWidget(QLabel('Outer Label 2'), 1, 1)

# Set the outer layout to the main window
main_window.setLayout(outer_layout)

# Show the main window
main_window.show()

app.exec_()
