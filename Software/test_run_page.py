"""Run Test page."""
from pathlib import Path
import csv
from datetime import datetime
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QComboBox,
    QMessageBox, QScrollArea, QFileDialog, QTextEdit
)

from models import CableProfile, list_profiles
from connector_view import ConnectorView
from uart_comm import list_serial_ports, mask_to_hex, TestWorker


class TestRunPage(QWidget):
    def __init__(self, profiles_dir: Path, reports_dir: Path, parent=None):
        super().__init__(parent)
        self.profiles_dir = profiles_dir
        self.reports_dir = reports_dir
        self.profile: Optional[CableProfile] = None
        self.worker = None
        self.last_result = None
        self._profile_paths = []
        self.views_b = {}

        self._build_ui()
        self.refresh_profile_list()
        self.refresh_ports()

    def _build_ui(self):
        root = QVBoxLayout(self)

        top_bar = QHBoxLayout()
        top_bar.addWidget(QLabel("Cable profile:"))
        self.combo_profile = QComboBox()
        self.combo_profile.currentIndexChanged.connect(self._on_profile_selected)
        top_bar.addWidget(self.combo_profile, stretch=1)
        btn_refresh_profile = QPushButton("Refresh")
        btn_refresh_profile.clicked.connect(self.refresh_profile_list)
        top_bar.addWidget(btn_refresh_profile)
        root.addLayout(top_bar)

        port_bar = QHBoxLayout()
        port_bar.addWidget(QLabel("COM Port:"))
        self.combo_port = QComboBox()
        port_bar.addWidget(self.combo_port)
        btn_refresh_port = QPushButton("Refresh")
        btn_refresh_port.clicked.connect(self.refresh_ports)
        port_bar.addWidget(btn_refresh_port)
        port_bar.addWidget(QLabel("Baudrate:"))
        self.combo_baud = QComboBox()
        self.combo_baud.addItems(["115200", "57600", "9600"])
        port_bar.addWidget(self.combo_baud)
        root.addLayout(port_bar)

        action_bar = QHBoxLayout()
        self.btn_run = QPushButton("Run Test")
        self.btn_run.clicked.connect(self.run_test)
        action_bar.addWidget(self.btn_run)
        self.btn_export = QPushButton("Export CSV Report")
        self.btn_export.clicked.connect(self.export_csv)
        self.btn_export.setEnabled(False)
        action_bar.addWidget(self.btn_export)
        self.btn_clear_log = QPushButton("Clear Log")
        self.btn_clear_log.clicked.connect(self.clear_log)
        action_bar.addWidget(self.btn_clear_log)
        self.btn_reset_view = QPushButton("Reset View")
        self.btn_reset_view.clicked.connect(self.reset_view)
        action_bar.addWidget(self.btn_reset_view)
        action_bar.addStretch()
        root.addLayout(action_bar)

        self.status_label = QLabel("Ready.")
        self.status_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        root.addWidget(self.status_label)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.canvas = QWidget()
        self.canvas_layout = QVBoxLayout(self.canvas)
        self.scroll.setWidget(self.canvas)
        root.addWidget(self.scroll, stretch=1)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(120)
        root.addWidget(self.log)

    def refresh_profile_list(self):
        self.combo_profile.blockSignals(True)
        self.combo_profile.clear()
        self._profile_paths = list_profiles(self.profiles_dir)
        for p in self._profile_paths:
            self.combo_profile.addItem(p.stem)
        self.combo_profile.blockSignals(False)
        if self._profile_paths:
            self.combo_profile.setCurrentIndex(0)
            self._on_profile_selected(0)
        else:
            self.profile = None
            self._rebuild_connector_views()

    def refresh_ports(self):
        self.combo_port.clear()
        self.combo_port.addItems(list_serial_ports())

    def _on_profile_selected(self, index):
        if index < 0 or index >= len(self._profile_paths):
            self.profile = None
            self._rebuild_connector_views()
            return
        self.profile = CableProfile.load(self._profile_paths[index])
        self._rebuild_connector_views()

    def _rebuild_connector_views(self):
        while self.canvas_layout.count():
            item = self.canvas_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self.views_b = {}

        if not self.profile:
            return

        self.view_a = ConnectorView(
            f"Connector A ({self.profile.connector_a.pin_count} pins)",
            self.profile.connector_a.pin_count,
            self.profile.connector_a.bypass_pins,
            self.profile.connector_a.layout,
            self.profile.connector_a.custom_order,
        )
        self.view_a.setMinimumHeight(140)
        self.canvas_layout.addWidget(self.view_a)

        for spec in self.profile.connectors_b:
            view = ConnectorView(f"{spec.label} ({spec.pin_count} pins)", spec.pin_count,
                                  spec.bypass_pins, spec.layout, spec.custom_order)
            view.setMinimumHeight(140)
            self.views_b[spec.id] = view
            self.canvas_layout.addWidget(view)

    def run_test(self):
        if not self.profile:
            QMessageBox.warning(self, "No profile selected", "Please select a cable profile first.")
            return
        port = self.combo_port.currentText()
        if not port:
            QMessageBox.warning(self, "No COM port selected", "Please select the COM port connected to the board.")
            return

        mask = self.profile.active_mask()
        mask_hex = mask_to_hex(mask)
        baud = int(self.combo_baud.currentText())

        self.btn_run.setEnabled(False)
        self.status_label.setText("Testing...")
        self.status_label.setStyleSheet("font-weight: bold; font-size: 14px; color: black;")
        self._log(f"Sent test command: T:{mask_hex}")

        self.worker = TestWorker(port, baud, mask_hex)
        self.worker.finished.connect(self._on_test_finished)
        self.worker.error.connect(self._on_test_error)
        self.worker.start()

    def _on_test_finished(self, result: dict):
        self.btn_run.setEnabled(True)
        self.last_result = result
        self.btn_export.setEnabled(True)

        open_pins = set(result.get("open", []))
        short_pairs = result.get("short", [])
        short_pins = set()
        for a, b in short_pairs:
            short_pins.add(a)
            short_pins.add(b)

        self._log(f"Result: open={sorted(open_pins)} short={short_pairs}")

        self.view_a.reset_colors()
        for v in self.views_b.values():
            v.reset_colors()

        for w in self.profile.wires:
            status = "pass"
            if w.board_pin in short_pins:
                status = "short"
            elif w.board_pin in open_pins:
                status = "open"
            self.view_a.set_status(w.connector_a_pin, status)
            view_b = self.views_b.get(w.connector_b_id)
            if view_b:
                view_b.set_status(w.connector_b_pin, status)

        if not open_pins and not short_pairs:
            self.status_label.setText("RESULT: PASS")
            self.status_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #2e7d32;")
        else:
            self.status_label.setText(f"RESULT: FAIL - {len(open_pins)} open, {len(short_pairs)} short")
            self.status_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #c62828;")

    def _on_test_error(self, message: str):
        self.btn_run.setEnabled(True)
        self.status_label.setText("Test error.")
        self.status_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #c62828;")
        self._log(f"ERROR: {message}")
        QMessageBox.critical(self, "Error", message)

    def _log(self, text: str):
        self.log.append(text)

    def clear_log(self):
        self.log.clear()

    def reset_view(self):
        self.view_a.reset_colors()
        for v in self.views_b.values():
            v.reset_colors()
        self.status_label.setText("Ready.")
        self.status_label.setStyleSheet("font-weight: bold; font-size: 14px;")

    def export_csv(self):
        if not self.last_result or not self.profile:
            return
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_path = self.reports_dir / f"{self.profile.name}_{ts}.csv"
        path, _ = QFileDialog.getSaveFileName(self, "Export report", str(default_path), "CSV (*.csv)")
        if not path:
            return

        open_pins = set(self.last_result.get("open", []))
        short_pairs = self.last_result.get("short", [])
        short_map = {}
        for a, b in short_pairs:
            short_map.setdefault(a, []).append(b)
            short_map.setdefault(b, []).append(a)

        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(["Cable profile", self.profile.name])
            writer.writerow(["Timestamp", datetime.now().isoformat(timespec="seconds")])
            writer.writerow([])
            writer.writerow(["Board pin", "Connector A pin", "Connector B", "Connector B pin", "Status", "Short with (board pin)"])
            for w in self.profile.wires:
                status = "PASS"
                short_with = ""
                if w.board_pin in short_map:
                    status = "SHORT"
                    short_with = ",".join(str(x) for x in short_map[w.board_pin])
                elif w.board_pin in open_pins:
                    status = "OPEN"
                writer.writerow([w.board_pin, w.connector_a_pin, w.connector_b_id, w.connector_b_pin, status, short_with])

        QMessageBox.information(self, "Exported", f"Report saved to:\n{path}")
