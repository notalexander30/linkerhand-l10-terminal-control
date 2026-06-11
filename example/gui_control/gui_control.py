from PyQt5.QtWidgets import (
    QApplication,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)
from PyQt5.QtCore import Qt, QTimer
import os
import sys

from views.left_view import LeftView
from views.right_view import RightView
from views.wave_form_plot import WaveformPlot

current_dir = os.path.dirname(os.path.abspath(__file__))
target_dir = os.path.abspath(os.path.join(current_dir, "../.."))
sys.path.append(target_dir)

from LinkerHand.linker_hand_api import LinkerHandApi
from LinkerHand.utils.load_write_yaml import LoadWriteYaml
from LinkerHand.utils.color_msg import ColorMsg

"""
LinkerHand graphical control.

This file defines the top-level GUI shell, passive status panels, and signal
wiring. Hardware communication remains in LinkerHandApi and the lower-level
driver modules.
"""

HAND_TYPE_LABELS = {
    "left": "Left",
    "right": "Right",
}

L10_JOINT_NAMES = [
    "Thumb Base",
    "Thumb Side Swing",
    "Index Base",
    "Middle Base",
    "Ring Base",
    "Little Base",
    "Index Side Swing",
    "Ring Side Swing",
    "Little Side Swing",
    "Thumb Rotation",
]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self._init_hand_joint()
        self.api = LinkerHandApi(hand_joint=self.hand_joint, hand_type=self.hand_type)
        self.touch_type = -1
        self._init_gui_view()
        if self.hand_joint == "L7":
            self.add_button_position = [255] * 7
            self.set_speed = [180, 250, 250, 250, 250, 250, 250]
            self.touch_type = self.api.get_touch_type()
            # if self.touch_type == 2:
            #     self._init_normal_force_plot(num_lines=6) # normal force waveform plot
            # else:
            #     self._init_normal_force_plot() # normal force waveform plot
            #     self._init_approach_inc_plot() # proximity sensing waveform plot
        elif self.hand_joint == "L10":
            self.add_button_position = [255] * 10  # Saved position for the add-preset button.
            self.set_speed(speed=[180, 250, 250, 250, 250])
            self.touch_type = self.api.get_touch_type()
            # if self.touch_type == 2:
            #     self._init_normal_force_plot(num_lines=6) # normal force waveform plot
            # else:
            #     self._init_normal_force_plot() # normal force waveform plot
            #     self._init_approach_inc_plot() # proximity sensing waveform plot
        elif self.hand_joint == "L20":
            self.add_button_position = [255] * 20  # Saved position for the add-preset button.
            self.set_speed(speed=[120, 180, 180, 180, 180])
            self._init_normal_force_plot()  # normal force waveform plot
            self.touch_type = self.api.get_touch_type()
            if self.touch_type == 2:
                self._init_normal_force_plot(num_lines=6)  # normal force waveform plot
            else:
                self._init_normal_force_plot()  # normal force waveform plot
                self._init_approach_inc_plot()  # proximity sensing waveform plot
        elif self.hand_joint == "L21":
            self.add_button_position = [255] * 25
            self.set_speed(speed=[60, 220, 220, 220, 220])
            self._init_normal_force_plot()  # normal force waveform plot
            self.touch_type = self.api.get_touch_type()
            if self.touch_type == 2:
                self._init_normal_force_plot(num_lines=6)  # normal force waveform plot
            else:
                self._init_normal_force_plot()  # normal force waveform plot
                self._init_approach_inc_plot()  # proximity sensing waveform plot
        elif self.hand_joint == "L25":
            self.add_button_position = [255] * 30  # Saved position for the add-preset button.
            self.set_speed(speed=[60, 250, 250, 250, 250])

    def _init_hand_joint(self):
        self.yaml = LoadWriteYaml()  # Configuration file helper.
        self.setting = self.yaml.load_setting_yaml()
        self.left_hand = False
        self.right_hand = False
        if self.setting["LINKER_HAND"]["LEFT_HAND"]["EXISTS"] == True:
            self.left_hand = True
        elif self.setting["LINKER_HAND"]["RIGHT_HAND"]["EXISTS"] == True:
            self.right_hand = True

        # The GUI supports one hand at a time; prefer the left hand if both are configured.
        if self.left_hand == True and self.right_hand == True:
            self.left_hand = True
            self.right_hand = False
        if self.left_hand == True:
            print("Left hand")
            self.hand_exists = True
            self.hand_joint = self.setting["LINKER_HAND"]["LEFT_HAND"]["JOINT"]
            self.hand_type = "left"
        if self.right_hand == True:
            print("Right hand")
            self.hand_exists = True
            self.hand_joint = self.setting["LINKER_HAND"]["RIGHT_HAND"]["JOINT"]
            self.hand_type = "right"

        self.init_pos = [255] * 10
        if self.hand_joint == "L25":
            # L25 joint slider names and initial slider positions.
            self.init_pos = [96, 255, 255, 255, 255, 150, 114, 151, 189, 255, 180, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255]
            self.joint_name = ["Thumb Base", "Index Base", "Middle Base", "Ring Base", "Little Base", "Thumb Side Swing", "Index Side Swing", "Middle Side Swing", "Ring Side Swing", "Little Side Swing", "Thumb Lateral Swing", "Reserved", "Reserved", "Reserved", "Reserved", "Thumb Middle", "Index Middle", "Middle Middle", "Ring Middle", "Little Middle", "Thumb Tip", "Index Tip", "Middle Tip", "Ring Tip", "Little Tip"]
        elif self.hand_joint == "L21":
            # L21 joint slider names and initial slider positions.
            self.init_pos = [96, 255, 255, 255, 255, 150, 114, 151, 189, 255, 180, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255]
            self.joint_name = ["Thumb Base", "Index Base", "Middle Base", "Ring Base", "Little Base", "Thumb Side Swing", "Index Side Swing", "Middle Side Swing", "Ring Side Swing", "Little Side Swing", "Thumb Lateral Swing", "Reserved", "Reserved", "Reserved", "Reserved", "Thumb Middle", "Reserved", "Reserved", "Reserved", "Reserved", "Thumb Tip", "Index Tip", "Middle Tip", "Ring Tip", "Little Tip"]
        elif self.hand_joint == "L20":
            # L20 joint slider names and initial slider positions.
            self.init_pos = [255, 255, 255, 255, 255, 255, 10, 100, 180, 240, 245, 255, 255, 255, 255, 255, 255, 255, 255, 255]
            self.joint_name = ["Thumb Base", "Index Base", "Middle Base", "Ring Base", "Little Base", "Thumb Side Swing", "Index Side Swing", "Middle Side Swing", "Ring Side Swing", "Little Side Swing", "Thumb Lateral Swing", "Reserved", "Reserved", "Reserved", "Reserved", "Thumb Tip", "Index Tip", "Middle Tip", "Ring Tip", "Little Tip"]
        elif self.hand_joint == "L10":
            # L10 joint slider names and initial slider positions.
            self.init_pos = [255] * 10
            self.joint_name = L10_JOINT_NAMES
        elif self.hand_joint == "L7":
            # L7 joint slider names and initial slider positions.
            self.init_pos = [250] * 7
            self.joint_name = ["Thumb Bend", "Thumb Side Swing", "Index Bend", "Middle Bend", "Ring Bend", "Little Bend", "Thumb Rotation"]

    def _init_gui_view(self):
        """Define the top-level window, splitter, and three GUI sections."""
        hand_label = HAND_TYPE_LABELS.get(self.hand_type, self.hand_type.title())
        self.setWindowTitle(f"LinkerHand: {hand_label} {self.hand_joint} Control")
        self.setGeometry(100, 100, 1120, 800)

        # GUI section: horizontal splitter that keeps the original live sliders and presets.
        splitter = QSplitter(Qt.Horizontal)
        splitter.setStyleSheet(
            """
            QSplitter::handle {
                width:1px;
                background-color: lightgray;
                margin: 15px 20px;
            }
            """
        )

        # GUI section: passive connection, hand information, heatmap, and quick settings.
        self.status_panel = self._build_status_panel()
        splitter.addWidget(self.status_panel)

        # GUI section: live joint value sliders. Slider movement keeps the existing API path.
        self.left_view = LeftView(joint_name=self.joint_name, init_pos=self.init_pos)
        splitter.addWidget(self.left_view)
        self.left_view.slider_value_changed.connect(self.handle_slider_value_changed)

        # GUI section: saved preset actions loaded from the existing action YAML.
        self.right_view = RightView(hand_joint=self.hand_joint, hand_type=self.hand_type)
        splitter.addWidget(self.right_view)

        # Signal wiring: saved presets update sliders and replay the existing stored positions.
        self.right_view.handle_button_click.connect(self.handle_button_click)
        self.right_view.add_button_handle.connect(self.add_button_handle)
        splitter.setSizes([280, 520, 360])
        self.setCentralWidget(splitter)

    def _build_status_panel(self):
        """Define passive status and safety UI sections without new hardware commands."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        # GUI section: connection status.
        connection_group = QGroupBox("Connection Status")
        connection_layout = QVBoxLayout(connection_group)
        self.connection_status_label = QLabel("Hand API Connected")
        connection_layout.addWidget(self.connection_status_label)
        layout.addWidget(connection_group)

        # GUI section: hand information from the existing YAML configuration.
        hand_info_group = QGroupBox("Hand Information")
        hand_info_layout = QFormLayout(hand_info_group)
        hand_info_layout.addRow("Hand Type", QLabel(HAND_TYPE_LABELS.get(self.hand_type, self.hand_type.title())))
        hand_info_layout.addRow("Joint Model", QLabel(self.hand_joint))
        hand_info_layout.addRow("Number of Joints", QLabel(str(len(self.joint_name))))
        layout.addWidget(hand_info_group)

        # GUI section: passive matrix heatmap placeholder for L10 fingertip matrix data.
        heatmap_group = QGroupBox("Finger Matrix Heatmap")
        heatmap_layout = QGridLayout(heatmap_group)
        heatmap_layout.setSpacing(3)
        for row in range(5):
            for column in range(4):
                cell = QLabel("0")
                cell.setAlignment(Qt.AlignCenter)
                cell.setFixedSize(28, 18)
                cell.setStyleSheet("background-color: #f1f5f9; border: 1px solid #cbd5e1;")
                heatmap_layout.addWidget(cell, row, column)
        layout.addWidget(heatmap_group)

        # GUI section: quick settings labels only. Buttons are disabled to avoid adding commands.
        quick_settings_group = QGroupBox("Quick Settings")
        quick_settings_layout = QFormLayout(quick_settings_group)
        self.speed_input = QLineEdit()
        self.speed_input.setEnabled(False)
        self.torque_input = QLineEdit()
        self.torque_input.setEnabled(False)
        self.set_speed_button = QPushButton("Set Speed")
        self.set_speed_button.setEnabled(False)
        self.set_torque_button = QPushButton("Set Torque")
        self.set_torque_button.setEnabled(False)
        quick_settings_layout.addRow("Speed", self.speed_input)
        quick_settings_layout.addRow("", self.set_speed_button)
        quick_settings_layout.addRow("Torque", self.torque_input)
        quick_settings_layout.addRow("", self.set_torque_button)
        layout.addWidget(quick_settings_group)

        layout.addStretch()
        return panel

    def _init_normal_force_plot(self, num_lines=5):
        return
        # GUI section: normal force waveform plot.
        self.normal_force_plot = WaveformPlot(num_lines=num_lines, labels=None, title="Normal Force Waveform")
        self.normal_force_plot.setGeometry(700, 100, 800, 400)
        self.normal_force_plot.show()
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_normal_force_plot)
        self.timer.start(50)

    def _init_approach_inc_plot(self):
        return
        # GUI section: proximity sensing waveform plot.
        self.approach_inc_plot = WaveformPlot(num_lines=5, labels=None, title="Proximity Sensing Waveform")
        self.approach_inc_plot.setGeometry(700, 600, 800, 400)
        self.approach_inc_plot.show()
        self.timer2 = QTimer()
        self.timer2.timeout.connect(self.update_approach_inc_plot)
        self.timer2.start(50)

    def handle_button_click(self, text):
        """Replay a stored preset through the existing finger_move API path."""
        all_action = self.yaml.load_action_yaml(hand_type=self.hand_type, hand_joint=self.hand_joint)
        for index, pos in enumerate(all_action):
            if pos["ACTION_NAME"] == text:
                position = pos["POSITION"]
                print(type(position))
        # print(f"Action name:{text}, action values:{action_pos}")
        ColorMsg(msg=f"Action name:{text}, action values:{position}", color="green")
        self.api.finger_move(pose=position)
        self.left_view.set_slider_values(values=position)

    def add_button_handle(self, text):
        """Save current slider values as a preset without changing motion semantics."""
        self.add_button_position = self.left_view.get_slider_values()
        self.add_button_text = text
        self.yaml.write_to_yaml(
            action_name=text,
            action_pos=self.left_view.get_slider_values(),
            hand_joint=self.hand_joint,
            hand_type=self.hand_type,
        )

    def handle_slider_value_changed(self, slider_values):
        """Collect live slider values and send them through the existing API method."""
        slider_values_list = []
        for key in slider_values:
            slider_values_list.append(slider_values[key])
        self.api.finger_move(pose=slider_values_list)

    def update_label(self, index, value):
        self.left_view.labels[index].setText(f"{self.joint_name[index]}: {value}")

    def update_normal_force_plot(self):
        """Update the normal force waveform plot."""
        if self.touch_type == 2:
            values = self.api.get_touch()
        else:
            force_values = self.api.get_force()
            values = force_values[0]
        if values == None:
            pass
        else:
            self.normal_force_plot.update_data(values)

    def update_approach_inc_plot(self):
        """Update the proximity sensing waveform plot."""
        if self.touch_type == 2:
            values = [0] * 5
        else:
            force_values = self.api.get_force()
            values = force_values[3]
        self.approach_inc_plot.update_data(values)

    def set_speed(self, speed=[180, 250, 250, 250, 250]):
        ColorMsg(msg=f"Set speed:{speed}", color="green")
        self.api.set_speed(speed)

    def closeEvent(self, event):
        """Close plot windows if they were created, then close the main GUI."""
        for plot_name in ("normal_force_plot", "approach_inc_plot"):
            plot = getattr(self, plot_name, None)
            if plot is not None:
                plot.close()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()

    sys.exit(app.exec_())
