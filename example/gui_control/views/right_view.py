import os
import sys

from PyQt5.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
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
    loop_requested = pyqtSignal()
    stop_requested = pyqtSignal()
    return_initial_requested = pyqtSignal()
    all_zero_requested = pyqtSignal()

    def __init__(self, hand_joint="L20", hand_type="left"):
        super().__init__()
        self.hand_joint = hand_joint
        self.hand_type = hand_type
        self.buttons = []
        self.preset_buttons = {}
        self.yaml = LoadWriteYaml()
        self.all_action = self.yaml.load_action_yaml(hand_type=self.hand_type, hand_joint=self.hand_joint)
        self.init_ui()
        self.init_buttons()

    def init_ui(self):
        """Define the system preset and sequence-control dashboard section."""
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(16, 16, 16, 16)
        self.main_layout.setSpacing(12)

        # GUI section: system presets and saved action buttons.
        preset_group = QGroupBox("System Presets")
        preset_layout = QVBoxLayout(preset_group)
        preset_layout.setContentsMargins(14, 18, 14, 14)
        preset_layout.setSpacing(12)

        # GUI section: add a saved preset from the current slider values.
        add_row = QHBoxLayout()
        add_row.setSpacing(8)
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("New preset name")
        self.add_button = QPushButton("Add")
        self.add_button.clicked.connect(self.add_button_to_list)
        add_row.addWidget(self.input_field)
        add_row.addWidget(self.add_button)
        preset_layout.addLayout(add_row)

        # GUI section: sequence mode controls.
        sequence_group = QGroupBox("Preset Sequence")
        sequence_layout = QVBoxLayout(sequence_group)
        sequence_layout.setContentsMargins(12, 16, 12, 12)
        sequence_layout.setSpacing(8)

        interval_row = QHBoxLayout()
        interval_row.addWidget(QLabel("Interval"))
        self.interval_ms = QSpinBox()
        self.interval_ms.setRange(300, 10000)
        self.interval_ms.setSingleStep(100)
        self.interval_ms.setValue(1500)
        self.interval_ms.setSuffix(" ms")
        interval_row.addWidget(self.interval_ms)
        sequence_layout.addLayout(interval_row)

        action_row = QGridLayout()
        action_row.setSpacing(8)
        self.loop_button = QPushButton("Loop Preset Action")
        self.loop_button.clicked.connect(self.loop_requested.emit)
        self.return_initial_button = QPushButton("Return to Initial Position")
        self.return_initial_button.clicked.connect(self.return_initial_requested.emit)
        self.all_zero_button = QPushButton("All Joints 0")
        self.all_zero_button.setObjectName("WarningButton")
        self.all_zero_button.clicked.connect(self.all_zero_requested.emit)
        self.stop_all_button = QPushButton("Stop All Actions")
        self.stop_all_button.setObjectName("DangerButton")
        self.stop_all_button.clicked.connect(self.stop_requested.emit)
        action_row.addWidget(self.loop_button, 0, 0)
        action_row.addWidget(self.stop_all_button, 0, 1)
        action_row.addWidget(self.return_initial_button, 1, 0)
        action_row.addWidget(self.all_zero_button, 1, 1)
        sequence_layout.addLayout(action_row)
        preset_layout.addWidget(sequence_group)

        # GUI section: scrollable preset list loaded from YAML.
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setObjectName("PresetScroll")
        self.scroll_widget = QWidget()
        self.scroll_layout = QGridLayout(self.scroll_widget)
        self.scroll_layout.setContentsMargins(8, 8, 8, 8)
        self.scroll_layout.setSpacing(8)
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
            self._add_preset_button(item["ACTION_NAME"])

    def _add_preset_button(self, text):
        button = QPushButton(text)
        button.setObjectName("PresetButton")
        button.setMinimumWidth(128)
        button.setFixedHeight(34)
        button.clicked.connect(lambda checked, name=text: self.handle_button_click.emit(name))
        self.scroll_layout.addWidget(button, self.row, self.column, alignment=Qt.AlignLeft | Qt.AlignTop)
        self.buttons.append(button)
        self.preset_buttons[text] = button

        self.column += 1
        if self.column >= self.BUTTONS_PER_ROW:
            self.column = 0
            self.row += 1

    def add_button_to_list(self):
        text = self.input_field.text().strip()
        if text:
            self._add_preset_button(text)
            self.input_field.clear()
            self.add_button_handle.emit(text)

    def set_loop_running(self, is_running):
        if is_running:
            self.loop_button.setText("Stop Preset Loop")
            self.loop_button.setObjectName("ActiveButton")
        else:
            self.loop_button.setText("Loop Preset Action")
            self.loop_button.setObjectName("")
        self.loop_button.style().unpolish(self.loop_button)
        self.loop_button.style().polish(self.loop_button)

    def highlight_preset(self, text):
        self.clear_highlight()
        button = self.preset_buttons.get(text)
        if button is not None:
            button.setProperty("active", True)
            button.style().unpolish(button)
            button.style().polish(button)

    def clear_highlight(self):
        for button in self.preset_buttons.values():
            button.setProperty("active", False)
            button.style().unpolish(button)
            button.style().polish(button)

    def clear_scroll_layout(self):
        """Clear every widget from scroll_layout."""
        while self.scroll_layout.count():
            item = self.scroll_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
