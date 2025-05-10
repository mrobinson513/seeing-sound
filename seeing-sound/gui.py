# sound2light/gui.py

import sys
import threading
import yaml
import os
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QPushButton, QVBoxLayout, QComboBox, QHBoxLayout
)
from PyQt6.QtCore import Qt
from config import CONFIG_FILE, load_config
from audio import list_input_devices, p
from lifx import discover_bulbs
from main import listen_and_analyze

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sound2Light Controller")

        self.config = load_config()
        self.worker_thread = None
        self.running = False

        layout = QVBoxLayout()

        # Frequency range
        self.min_freq = self._add_row(layout, "Min Frequency (Hz)", str(self.config.get("min_frequency", 100)))
        self.max_freq = self._add_row(layout, "Max Frequency (Hz)", str(self.config.get("max_frequency", 4000)))

        # Clip threshold
        self.clip_threshold = self._add_row(layout, "Clip Threshold", str(self.config.get("clip_threshold", 32000)))

        # Max brightness
        self.max_brightness = self._add_row(layout, "Max Brightness", str(self.config.get("max_brightness", 60000)))

        # Log level
        layout.addWidget(QLabel("Log Level"))
        self.log_level = QComboBox()
        self.log_level.addItems(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        self.log_level.setCurrentText(self.config.get("log_level", "INFO"))
        layout.addWidget(self.log_level)

        # Input devices
        layout.addWidget(QLabel("Input Device"))
        self.device_combo = QComboBox()
        for i in range(p.get_device_count()):
            info = p.get_device_info_by_index(i)
            if info["maxInputChannels"] > 0:
                self.device_combo.addItem(f"[{i}] {info['name']}", i)
        layout.addWidget(self.device_combo)

        # Start/Stop Button
        self.start_btn = QPushButton("Start")
        self.start_btn.clicked.connect(self.toggle_execution)
        layout.addWidget(self.start_btn)

        self.setLayout(layout)

    def _add_row(self, layout, label, default):
        row = QHBoxLayout()
        row.addWidget(QLabel(label))
        edit = QLineEdit(default)
        row.addWidget(edit)
        layout.addLayout(row)
        return edit

    def toggle_execution(self):
        if not self.running:
            self.save_config()
            bulbs = discover_bulbs()
            device_index = self.device_combo.currentData()

            self.worker_thread = threading.Thread(
                target=listen_and_analyze, kwargs={"bulbs": bulbs, "device_index": device_index}, daemon=True
            )
            self.worker_thread.start()
            self.start_btn.setText("Stop")
            self.running = True
        else:
            # Signal stop (brutal but effective for now)
            os._exit(0)

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

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
