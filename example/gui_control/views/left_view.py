from PyQt5.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)
from PyQt5.QtCore import Qt, pyqtSignal


class LeftView(QWidget):
    # Signal emitted whenever a slider value changes.
    slider_value_changed = pyqtSignal(dict)

    def __init__(self, joint_name=[], init_pos=[]):
        super().__init__()
        self.is_open = True
        self.joint_name = joint_name
        self.init_pos = init_pos
        self._suppress_emit = False
        self.init_view()

    def init_view(self):
        """Define the live joint slider section."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # GUI section: joint value list.
        joint_group = QGroupBox("Joint Value List")
        joint_layout = QVBoxLayout(joint_group)
        joint_layout.setContentsMargins(14, 18, 14, 14)
        joint_layout.setSpacing(10)

        self.sliders = []
        self.labels = []
        for i in range(len(self.joint_name)):
            slider_layout = QHBoxLayout()
            slider_layout.setSpacing(12)

            label = QLabel(f"{self.joint_name[i]}: {self.init_pos[i]}", self)
            label.setFixedWidth(180)
            self.labels.append(label)
            slider_layout.addWidget(label)

            slider = QSlider(Qt.Horizontal, self)
            slider.setRange(0, 255)
            slider.setValue(self.init_pos[i])
            slider.setFixedHeight(22)
            slider.valueChanged.connect(lambda value, index=i: self.update_label(index, value))
            self.sliders.append(slider)
            slider_layout.addWidget(slider)
            joint_layout.addLayout(slider_layout)

        main_layout.addWidget(joint_group)

        # GUI section: existing enable/disable display toggle.
        self.toggle_button = QPushButton("Enabled", self)
        self.toggle_button.setCheckable(True)
        self.toggle_button.clicked.connect(self.toggle_button_clicked)
        main_layout.addWidget(self.toggle_button)
        main_layout.addStretch()

    def update_label(self, index, value):
        self.labels[index].setText(f"{self.joint_name[index]}: {value}")
        slider_values = {}
        sliders = self.findChildren(QSlider)
        for i, slider in enumerate(sliders):
            slider_values[i] = slider.value()
        if not self._suppress_emit:
            self.slider_value_changed.emit(slider_values)

    def set_slider_values(self, values, emit=True):
        self._suppress_emit = not emit
        for i, value in enumerate(values):
            if i < len(self.sliders):
                if not emit:
                    self.sliders[i].blockSignals(True)
                self.sliders[i].setValue(value)
                self.update_label(i, value)
                if not emit:
                    self.sliders[i].blockSignals(False)
        self._suppress_emit = False

    def get_slider_values(self):
        """Return all slider values."""
        return [slider.value() for slider in self.sliders]

    def handle_button_click(self, text):
        print(f"Button clicked with text: {text}")
        # Preserved placeholder for button-click handling.

    def toggle_button_clicked(self):
        if self.toggle_button.isChecked():
            self.toggle_button.setText("Disabled")
            self.is_open = False
            # Existing display state only; no hardware command is sent here.
        else:
            self.toggle_button.setText("Enabled")
            self.is_open = True
            # Existing display state only; no hardware command is sent here.
