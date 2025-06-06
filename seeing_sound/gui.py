import sys
import threading
import yaml
import os
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QPushButton, QVBoxLayout, QComboBox, QHBoxLayout
)
from PyQt6.QtCore import Qt
from seeing_sound.config import CONFIG_FILE, load_config
from seeing_sound.audio import p
from seeing_sound.lifx import discover_bulbs
from seeing_sound.main import listen_and_analyze
from seeing_sound.color_profiles import get_profile

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Seeing Sound Controller")

        self.config = load_config()
        self.worker_thread = None
        self.running = False

        layout = QVBoxLayout()

        self.min_freq = self._add_row(layout, "Min Frequency (Hz)", str(self.config.get("min_frequency", 100)))
        self.max_freq = self._add_row(layout, "Max Frequency (Hz)", str(self.config.get("max_frequency", 4000)))
        self.clip_threshold = self._add_row(layout, "Clip Threshold", str(self.config.get("clip_threshold", 32000)))
        self.max_brightness = self._add_row(layout, "Max Brightness", str(self.config.get("max_brightness", 60000)))

        layout.addWidget(QLabel("Log Level"))
        self.log_level = QComboBox()
        self.log_level.addItems(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        self.log_level.setCurrentText(self.config.get("log_level", "INFO"))
        layout.addWidget(self.log_level)

        layout.addWidget(QLabel("Input Device"))
        self.device_combo = QComboBox()
        for i in range(p.get_device_count()):
            info = p.get_device_info_by_index(i)
            if info["maxInputChannels"] > 0:
                self.device_combo.addItem(f"[{i}] {info['name']}", i)
        layout.addWidget(self.device_combo)

        profile_row = QHBoxLayout()
        profile_label = QLabel("Color Profile")
        self.profile_combo = QComboBox()
        self.profile_combo.addItems(["default", "warm", "cold"])
        profile_row.addWidget(profile_label)
        profile_row.addWidget(self.profile_combo)
        layout.addLayout(profile_row)

        self.start_btn = QPushButton("Start")
        self.start_btn.clicked.connect(self.toggle_execution)
        layout.addWidget(self.start_btn)

        self.setLayout(layout)
        self.show_lights()

    def _add_row(self, layout, label, default):
        row = QHBoxLayout()
        row.addWidget(QLabel(label))
        edit = QLineEdit(default)
        row.addWidget(edit)
        layout.addLayout(row)
        return edit

    def show_lights(self):
        bulbs = discover_bulbs()
        print("Detected LIFX Lights:")
        for b in bulbs:
            try:
                print(f" - {b.get_label()} @ {b.get_ip_addr()}")
            except:
                print(f" - (unknown) @ {b.ip_addr}")

    def toggle_execution(self):
        if not self.running:
            self.save_config()
            bulbs = discover_bulbs()
            
            device_index = self.device_combo.currentData()

            selected_profile = self.profile_combo.currentText()
            profile = get_profile(selected_profile)

            self.worker_thread = threading.Thread(
                target=listen_and_analyze, kwargs={
                    "bulbs": bulbs, 
                    "device_index": device_index,
                    "profile": profile},
                daemon=True
            )
            self.worker_thread.start()
            self.start_btn.setText("Stop")
            self.running = True
        else:
            self.running = False
            self.start_btn.setText("Start")
            print("🛑 Stop requested. Please restart the app to fully release resources.")

    def save_config(self):
        config = {
            "min_frequency": int(self.min_freq.text()),
            "max_frequency": int(self.max_freq.text()),
            "clip_threshold": int(self.clip_threshold.text()),
            "max_brightness": int(self.max_brightness.text()),
            "log_level": self.log_level.currentText(),
        }
        with open(CONFIG_FILE, "w") as f:
            yaml.dump(config, f)

def main():
    print("🔍 Scanning for LIFX lights...")
    bulbs = discover_bulbs()
    print("Detected LIFX Lights:")
    for b in bulbs:
        try:
            print(f" - {b.get_label()} @ {b.get_ip_addr()}")
        except:
            print(f" - (unknown) @ {b.ip_addr}")

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
