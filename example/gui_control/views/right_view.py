import os
import sys

from PyQt5.QtWidgets import (
    QCheckBox,
    QGridLayout,
    QGroupBox,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from PyQt5.QtCore import Qt, pyqtSignal

current_dir = os.path.dirname(os.path.abspath(__file__))
target_dir = os.path.abspath(os.path.join(current_dir, "../../.."))
sys.path.append(target_dir)

from LinkerHand.utils.load_write_yaml import LoadWriteYaml


class RightView(QWidget):
    add_button_handle = pyqtSignal(str)
    handle_button_click = pyqtSignal(str)

    def __init__(self, hand_joint="L20", hand_type="left"):
        super().__init__()
        self.hand_joint = hand_joint
        self.hand_type = hand_type
        self.buttons = []
        self.yaml = LoadWriteYaml()
        self.all_action = self.yaml.load_action_yaml(hand_type=self.hand_type, hand_joint=self.hand_joint)
        self.init_ui()
        self.init_buttons()

    def init_ui(self):
        """Define the saved action preset section."""
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(10)

        # GUI section: system presets and saved action buttons.
        preset_group = QGroupBox("System Presets")
        preset_layout = QVBoxLayout(preset_group)

        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Preset name")
        self.add_button = QPushButton("Add")
        self.add_button.clicked.connect(self.add_button_to_list)

        preset_layout.addWidget(self.input_field)
        preset_layout.addWidget(self.add_button)

        self.loop_preset_checkbox = QCheckBox("Loop Preset Action")
        self.loop_preset_checkbox.setEnabled(False)
        preset_layout.addWidget(self.loop_preset_checkbox)

        # Disabled safety placeholders: enabling these would require new motion commands.
        self.return_initial_button = QPushButton("Return to Initial Position")
        self.return_initial_button.setEnabled(False)
        self.stop_all_button = QPushButton("Stop All Actions")
        self.stop_all_button.setEnabled(False)
        preset_layout.addWidget(self.return_initial_button)
        preset_layout.addWidget(self.stop_all_button)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_widget = QWidget()
        self.scroll_layout = QGridLayout(self.scroll_widget)
        self.scroll_layout.setContentsMargins(10, 10, 10, 10)
        self.scroll_layout.setSpacing(10)
        self.scroll_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.scroll_area.setWidget(self.scroll_widget)
        preset_layout.addWidget(self.scroll_area)

        self.main_layout.addWidget(preset_group)

        self.row = 0
        self.column = 0
        self.BUTTONS_PER_ROW = 2

    def init_buttons(self):
        """Create saved preset buttons from the existing action YAML."""
        if self.all_action == None:
            return
        for item in self.all_action:
            button = QPushButton(item["ACTION_NAME"])
            button.setFixedWidth(120)
            button.setFixedHeight(30)
            button.clicked.connect(lambda checked, text=item["ACTION_NAME"]: self.handle_button_click.emit(text))
            self.scroll_layout.addWidget(button, self.row, self.column, alignment=Qt.AlignLeft | Qt.AlignTop)

            self.column += 1
            if self.column >= self.BUTTONS_PER_ROW:
                self.column = 0
                self.row += 1

    def add_button_to_list(self):
        text = self.input_field.text().strip()
        if text:
            button = QPushButton(text)
            button.setFixedWidth(120)
            button.setFixedHeight(30)
            button.clicked.connect(lambda checked, text=text: self.handle_button_click.emit(text))
            self.scroll_layout.addWidget(button, self.row, self.column, alignment=Qt.AlignLeft | Qt.AlignTop)

            self.column += 1
            if self.column >= self.BUTTONS_PER_ROW:
                self.column = 0
            self.input_field.clear()
            self.buttons.append(button)
            self.add_button_handle.emit(text)

    def clear_scroll_layout(self):
        """Clear every widget from scroll_layout."""
        while self.scroll_layout.count():
            item = self.scroll_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
