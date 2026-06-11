from PyQt5.QtWidgets import (
    QApplication,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
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

LOOP_INTERVAL_FALLBACK_MS = 1500


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self._init_hand_joint()
        self.api = LinkerHandApi(hand_joint=self.hand_joint, hand_type=self.hand_type)
        self.touch_type = -1
        self.loop_timer = QTimer(self)
        self.loop_timer.timeout.connect(self.run_next_preset)
        self.current_preset_index = -1
        self.preset_sequence = []
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
        self.setWindowTitle(f"LinkerHand L10 Dashboard - {hand_label} {self.hand_joint}")
        self.setGeometry(100, 100, 1280, 820)
        self._apply_dashboard_style()

        root_widget = QWidget()
        root_layout = QVBoxLayout(root_widget)
        root_layout.setContentsMargins(18, 18, 18, 18)
        root_layout.setSpacing(14)

        # GUI section: dashboard header.
        header = QFrame()
        header.setObjectName("HeaderCard")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(18, 14, 18, 14)
        title = QLabel("LinkerHand L10 Control Dashboard")
        title.setObjectName("DashboardTitle")
        subtitle = QLabel(f"{hand_label} hand | {self.hand_joint} | {len(self.joint_name)} joints")
        subtitle.setObjectName("DashboardSubtitle")
        header_text = QVBoxLayout()
        header_text.addWidget(title)
        header_text.addWidget(subtitle)
        self.sequence_status_label = QLabel("Manual mode")
        self.sequence_status_label.setObjectName("ModeBadge")
        header_layout.addLayout(header_text)
        header_layout.addStretch()
        header_layout.addWidget(self.sequence_status_label)
        root_layout.addWidget(header)

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
        self.right_view.loop_requested.connect(self.toggle_preset_loop)
        self.right_view.stop_requested.connect(self.stop_all_actions)
        self.right_view.return_initial_requested.connect(self.return_to_initial_position)
        self.right_view.all_zero_requested.connect(self.move_all_joints_zero)
        splitter.setSizes([310, 560, 410])
        root_layout.addWidget(splitter)
        self.setCentralWidget(root_widget)

    def _apply_dashboard_style(self):
        """Define the professional dashboard visual theme."""
        self.setStyleSheet(
            """
            QWidget {
                background: #f4f7fb;
                color: #172033;
                font-family: "Inter", "Segoe UI", "Noto Sans", Arial, sans-serif;
                font-size: 13px;
            }
            #HeaderCard, QGroupBox {
                background: #ffffff;
                border: 1px solid #d9e2ef;
                border-radius: 10px;
            }
            #HeaderCard {
                border-left: 5px solid #2f6fed;
            }
            #DashboardTitle {
                font-size: 24px;
                font-weight: 700;
                color: #111827;
            }
            #DashboardSubtitle {
                color: #667085;
                font-size: 13px;
            }
            #ModeBadge {
                background: #e9f2ff;
                color: #155eef;
                border: 1px solid #b2ccff;
                border-radius: 14px;
                padding: 6px 12px;
                font-weight: 600;
            }
            QGroupBox {
                margin-top: 10px;
                font-weight: 700;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 14px;
                padding: 0 6px;
                color: #344054;
                background: #ffffff;
            }
            QLabel {
                background: transparent;
            }
            QLineEdit, QSpinBox {
                background: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px;
            }
            QPushButton {
                background: #eef4ff;
                border: 1px solid #b2ccff;
                border-radius: 7px;
                color: #1849a9;
                padding: 7px 10px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #dbeafe;
            }
            QPushButton:disabled {
                background: #f2f4f7;
                border-color: #d0d5dd;
                color: #98a2b3;
            }
            QPushButton#PresetButton {
                background: #ffffff;
                color: #344054;
                border: 1px solid #d0d5dd;
                text-align: left;
            }
            QPushButton#PresetButton[active="true"] {
                background: #155eef;
                border-color: #155eef;
                color: #ffffff;
            }
            QPushButton#ActiveButton {
                background: #12b76a;
                border-color: #039855;
                color: #ffffff;
            }
            QPushButton#WarningButton {
                background: #fff7ed;
                border-color: #fed7aa;
                color: #c2410c;
            }
            QPushButton#DangerButton {
                background: #fff1f3;
                border-color: #fecdd3;
                color: #be123c;
            }
            QSlider::groove:horizontal {
                height: 6px;
                background: #d9e2ef;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #155eef;
                border: 2px solid #ffffff;
                width: 16px;
                height: 16px;
                margin: -6px 0;
                border-radius: 8px;
            }
            QScrollArea#PresetScroll {
                background: #ffffff;
                border: 1px solid #eef2f6;
                border-radius: 8px;
            }
            QFrame#MetricCard {
                background: #f8fafc;
                border: 1px solid #e4e7ec;
                border-radius: 8px;
            }
            """
        )

    def _build_status_panel(self):
        """Define passive status and safety UI sections without new hardware commands."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # GUI section: connection status.
        connection_group = QGroupBox("Connection Status")
        connection_layout = QVBoxLayout(connection_group)
        self.connection_status_label = QLabel("Hand API Connected")
        self.connection_status_label.setObjectName("ModeBadge")
        connection_layout.addWidget(self.connection_status_label)
        layout.addWidget(connection_group)

        # GUI section: hand information from the existing YAML configuration.
        hand_info_group = QGroupBox("Hand Information")
        hand_info_layout = QFormLayout(hand_info_group)
        hand_info_layout.addRow("Hand Type", QLabel(HAND_TYPE_LABELS.get(self.hand_type, self.hand_type.title())))
        hand_info_layout.addRow("Joint Model", QLabel(self.hand_joint))
        hand_info_layout.addRow("Number of Joints", QLabel(str(len(self.joint_name))))
        layout.addWidget(hand_info_group)

        # GUI section: passive operating status.
        status_group = QGroupBox("Operating Mode")
        status_layout = QFormLayout(status_group)
        self.mode_status_label = QLabel("Manual slider/preset control")
        self.last_action_label = QLabel("None")
        self.current_values_label = QLabel(str(self.init_pos))
        self.current_values_label.setWordWrap(True)
        status_layout.addRow("Mode", self.mode_status_label)
        status_layout.addRow("Last Action", self.last_action_label)
        status_layout.addRow("Joint Values", self.current_values_label)
        layout.addWidget(status_group)

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
        position = self._get_action_position(text)
        if position is None:
            self._set_mode_status("Preset not found", text)
            return
        self._apply_pose(action_name=text, position=position)

    def _get_action_position(self, text):
        all_action = self.yaml.load_action_yaml(hand_type=self.hand_type, hand_joint=self.hand_joint)
        if all_action is None:
            return None
        for pos in all_action:
            if pos["ACTION_NAME"] == text:
                return pos["POSITION"]
        return None

    def _apply_pose(self, action_name, position):
        """Send one validated pose through the existing finger_move API method."""
        if len(position) != len(self.joint_name):
            self._set_mode_status("Preset ignored", f"{action_name} has {len(position)} values")
            ColorMsg(msg=f"Preset ignored:{action_name}, invalid joint count:{len(position)}", color="red")
            return

        ColorMsg(msg=f"Action name:{action_name}, action values:{position}", color="green")
        self.api.finger_move(pose=position)
        self.left_view.set_slider_values(values=position, emit=False)
        self.right_view.highlight_preset(action_name)
        self._set_mode_status("Manual preset", action_name, position)

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
        self.right_view.clear_highlight()
        self._set_mode_status("Manual slider", "Live slider movement", slider_values_list)

    def toggle_preset_loop(self):
        """Start or stop looping through every valid preset in the current YAML list."""
        if self.loop_timer.isActive():
            self.stop_all_actions()
            return

        actions = self.yaml.load_action_yaml(hand_type=self.hand_type, hand_joint=self.hand_joint) or []
        self.preset_sequence = [
            action
            for action in actions
            if len(action.get("POSITION", [])) == len(self.joint_name)
        ]
        if not self.preset_sequence:
            self._set_mode_status("No sequence presets", "No valid presets to loop")
            return

        self.current_preset_index = -1
        interval_ms = getattr(self.right_view, "interval_ms", None)
        interval = interval_ms.value() if interval_ms is not None else LOOP_INTERVAL_FALLBACK_MS
        self.loop_timer.start(interval)
        self.right_view.set_loop_running(True)
        self._set_mode_status("Looping presets", f"{len(self.preset_sequence)} presets, {interval} ms")
        self.run_next_preset()

    def run_next_preset(self):
        """Run the next preset in sequence mode."""
        if not self.preset_sequence:
            self.stop_all_actions()
            return
        self.current_preset_index = (self.current_preset_index + 1) % len(self.preset_sequence)
        action = self.preset_sequence[self.current_preset_index]
        self._apply_pose(action_name=action["ACTION_NAME"], position=action["POSITION"])
        self._set_mode_status("Looping presets", action["ACTION_NAME"], action["POSITION"])

    def stop_all_actions(self):
        """Stop the GUI preset loop. This does not send a new hardware stop command."""
        if self.loop_timer.isActive():
            self.loop_timer.stop()
        self.right_view.set_loop_running(False)
        self.right_view.clear_highlight()
        self._set_mode_status("Stopped", "Preset loop stopped")

    def return_to_initial_position(self):
        """Return to the GUI-defined initial pose through the existing finger_move method."""
        self.stop_all_actions()
        self._apply_pose(action_name="Return to Initial Position", position=list(self.init_pos))

    def move_all_joints_zero(self):
        """Move all displayed joints to zero through the existing finger_move method."""
        self.stop_all_actions()
        zero_pose = [0] * len(self.joint_name)
        self._apply_pose(action_name="All Joints 0", position=zero_pose)

    def _set_mode_status(self, mode, last_action, values=None):
        if hasattr(self, "sequence_status_label"):
            self.sequence_status_label.setText(mode)
        if hasattr(self, "mode_status_label"):
            self.mode_status_label.setText(mode)
        if hasattr(self, "last_action_label"):
            self.last_action_label.setText(last_action)
        if values is not None and hasattr(self, "current_values_label"):
            self.current_values_label.setText(str(values))

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
        if self.loop_timer.isActive():
            self.loop_timer.stop()
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
