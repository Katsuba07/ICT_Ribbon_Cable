"""Cable Setup page: define connectors, mark bypass pins, create wire mappings."""
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QLineEdit,
    QSpinBox, QListWidget, QMessageBox, QInputDialog,
    QGroupBox, QScrollArea, QFileDialog, QComboBox, QFrame
)

from models import CableProfile, ConnectorSpec, WireMapping
from connector_view import ConnectorView, LAYOUT_CHOICES, LAYOUT_DISPLAY_NAMES


class CableSetupPage(QWidget):
    def __init__(self, profiles_dir: Path, parent=None):
        super().__init__(parent)
        self.profiles_dir = profiles_dir
        self.profile = CableProfile(
            name="New cable",
            connector_a=ConnectorSpec(id="A", label="Connector A", pin_count=64),
        )
        self.views = {}          # connector_id -> ConnectorView
        self.pending_pin_a = None
        self.selected_wire_index = None

        self._build_ui()
        self._rebuild_connector_views()

    # ---------------- UI ----------------
    def _build_ui(self):
        root = QVBoxLayout(self)

        top_bar = QHBoxLayout()
        top_bar.addWidget(QLabel("Cable name:"))
        self.name_edit = QLineEdit(self.profile.name)
        self.name_edit.textChanged.connect(self._on_name_changed)
        top_bar.addWidget(self.name_edit)

        btn_new = QPushButton("New")
        btn_new.clicked.connect(self._new_profile)
        top_bar.addWidget(btn_new)

        btn_open = QPushButton("Open profile...")
        btn_open.clicked.connect(self._open_profile)
        top_bar.addWidget(btn_open)

        btn_save = QPushButton("Save profile")
        btn_save.clicked.connect(self._save_profile)
        top_bar.addWidget(btn_save)

        root.addLayout(top_bar)

        a_box = QGroupBox("Connector A")
        a_layout = QHBoxLayout(a_box)
        a_layout.addWidget(QLabel("Pin count:"))
        self.spin_a_pins = QSpinBox()
        self.spin_a_pins.setRange(1, 80)
        self.spin_a_pins.setValue(self.profile.connector_a.pin_count)
        self.spin_a_pins.valueChanged.connect(self._on_a_pin_count_changed)
        a_layout.addWidget(self.spin_a_pins)
        a_layout.addStretch()
        root.addWidget(a_box)

        b_box = QGroupBox("Connector B (the other end(s) of the cable)")
        b_box_layout = QVBoxLayout(b_box)
        btn_row = QHBoxLayout()
        btn_add_b = QPushButton("+ Add Connector B")
        btn_add_b.clicked.connect(self._add_connector_b)
        btn_row.addWidget(btn_add_b)
        btn_row.addStretch()
        b_box_layout.addLayout(btn_row)
        root.addWidget(b_box)

        # Thanh cong cu thao tac nhanh
        quick_bar = QHBoxLayout()
        btn_auto_map = QPushButton("Auto-map (sequential)")
        btn_auto_map.setToolTip(
            "Automatically pair remaining unmapped, non-bypass pins on Connector A\n"
            "with remaining unmapped, non-bypass pins on Connector B blocks, in order."
        )
        btn_auto_map.clicked.connect(self._auto_map_sequential)
        quick_bar.addWidget(btn_auto_map)

        btn_clear_all = QPushButton("Clear all mappings")
        btn_clear_all.clicked.connect(self._clear_all_wires)
        quick_bar.addWidget(btn_clear_all)
        quick_bar.addStretch()
        root.addLayout(quick_bar)

        hint = QLabel(
            "Left-click a pin on Connector A, then left-click the matching pin on a "
            "Connector B block to create a wire. Left-click an already-mapped pin to "
            "remove that mapping. Right-click any pin to toggle it as BYPASS (unused). "
            "Mapped pins are shown in teal."
        )
        hint.setWordWrap(True)
        root.addWidget(hint)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.canvas = QWidget()
        self.canvas_layout = QVBoxLayout(self.canvas)
        self.scroll.setWidget(self.canvas)
        root.addWidget(self.scroll, stretch=1)

        wire_box = QGroupBox("Wire mapping list (click a row to highlight it above)")
        wire_layout = QVBoxLayout(wire_box)
        self.wire_list = QListWidget()
        self.wire_list.currentRowChanged.connect(self._on_wire_row_selected)
        wire_layout.addWidget(self.wire_list)
        btn_remove_wire = QPushButton("Remove selected wire")
        btn_remove_wire.clicked.connect(self._remove_selected_wire)
        wire_layout.addWidget(btn_remove_wire)
        root.addWidget(wire_box)

    # ---------------- Build 1 connector block (header + view) ----------------
    def _build_connector_block(self, spec: ConnectorSpec, view: ConnectorView, removable: bool):
        block = QFrame()
        block_layout = QVBoxLayout(block)
        block_layout.setContentsMargins(0, 0, 0, 0)

        header = QHBoxLayout()
        header.addWidget(QLabel(f"<b>{spec.label}</b> ({spec.pin_count} pins)"))

        header.addWidget(QLabel("Layout:"))
        combo = QComboBox()
        for key in LAYOUT_CHOICES:
            combo.addItem(LAYOUT_DISPLAY_NAMES[key], userData=key)
        combo.setCurrentIndex(LAYOUT_CHOICES.index(spec.layout if spec.layout in LAYOUT_CHOICES else "zigzag"))
        header.addWidget(combo)

        custom_edit = QLineEdit(",".join(str(p) for p in spec.custom_order))
        custom_edit.setPlaceholderText("e.g. 1,3,5,7,2,4,6,8")
        custom_edit.setVisible(spec.layout == "custom")
        header.addWidget(custom_edit)

        def on_layout_changed(_idx, spec=spec, view=view, combo=combo, custom_edit=custom_edit):
            layout_key = combo.currentData()
            spec.layout = layout_key
            custom_edit.setVisible(layout_key == "custom")
            if layout_key == "custom":
                view.set_layout("custom", spec.custom_order)
            else:
                view.set_layout(layout_key)

        combo.currentIndexChanged.connect(on_layout_changed)

        def on_custom_order_edited(spec=spec, view=view, custom_edit=custom_edit):
            text = custom_edit.text().strip()
            try:
                order = [int(x) for x in text.split(",") if x.strip() != ""]
            except ValueError:
                QMessageBox.warning(self, "Invalid order", "Custom order must be a comma-separated list of pin numbers.")
                return
            spec.custom_order = order
            if spec.layout == "custom":
                view.set_layout("custom", order)
            self._refresh_pin_colors()

        custom_edit.editingFinished.connect(on_custom_order_edited)

        header.addStretch()

        if removable:
            btn_remove = QPushButton("Remove connector")
            btn_remove.clicked.connect(lambda _=False, cid=spec.id: self._remove_connector_b(cid))
            header.addWidget(btn_remove)

        block_layout.addLayout(header)
        block_layout.addWidget(view)
        return block

    # ---------------- Rebuild connector display area ----------------
    def _rebuild_connector_views(self):
        while self.canvas_layout.count():
            item = self.canvas_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self.views.clear()

        self.view_a = ConnectorView(
            "Connector A",
            self.profile.connector_a.pin_count,
            self.profile.connector_a.bypass_pins,
            self.profile.connector_a.layout,
            self.profile.connector_a.custom_order,
        )
        self.view_a.pinClicked.connect(self._on_pin_a_clicked)
        self.view_a.pinRightClicked.connect(lambda pin: self._toggle_bypass("A", pin))
        self.view_a.setMinimumHeight(150)
        self.views["A"] = self.view_a
        self.canvas_layout.addWidget(self._build_connector_block(self.profile.connector_a, self.view_a, removable=False))

        for spec in self.profile.connectors_b:
            view = ConnectorView(spec.label, spec.pin_count, spec.bypass_pins, spec.layout, spec.custom_order)
            view.setMinimumHeight(150)
            view.pinClicked.connect(lambda pin, cid=spec.id: self._on_pin_b_clicked(cid, pin))
            view.pinRightClicked.connect(lambda pin, cid=spec.id: self._toggle_bypass(cid, pin))
            self.views[spec.id] = view
            self.canvas_layout.addWidget(self._build_connector_block(spec, view, removable=True))

        self._refresh_wire_list()
        self._refresh_pin_colors()

    def _refresh_wire_list(self):
        self.wire_list.blockSignals(True)
        self.wire_list.clear()
        for w in self.profile.wires:
            self.wire_list.addItem(
                f"Board pin {w.board_pin}: A.{w.connector_a_pin}  <->  {w.connector_b_id}.{w.connector_b_pin}"
            )
        self.wire_list.blockSignals(False)

    def _refresh_pin_colors(self):
        """To mau lai toan bo pin: normal/bypass mac dinh, mapped = teal,
        va highlight rieng cap pin dang duoc chon trong danh sach (neu co)."""
        for view in self.views.values():
            view.reset_colors()

        for w in self.profile.wires:
            va = self.views.get("A")
            if va:
                va.set_status(w.connector_a_pin, "pass")  # dung mau "pass" (xanh la) lam mau "mapped"
            vb = self.views.get(w.connector_b_id)
            if vb:
                vb.set_status(w.connector_b_pin, "pass")

        if self.pending_pin_a is not None:
            self.views["A"].set_status(self.pending_pin_a, "selected")

        if self.selected_wire_index is not None and 0 <= self.selected_wire_index < len(self.profile.wires):
            w = self.profile.wires[self.selected_wire_index]
            self.views["A"].set_status(w.connector_a_pin, "selected")
            vb = self.views.get(w.connector_b_id)
            if vb:
                vb.set_status(w.connector_b_pin, "selected")

    # ---------------- Event handlers ----------------
    def _on_name_changed(self, text):
        self.profile.name = text

    def _new_profile(self):
        self.profile = CableProfile(
            name="New cable",
            connector_a=ConnectorSpec(id="A", label="Connector A", pin_count=64),
        )
        self.name_edit.setText(self.profile.name)
        self.spin_a_pins.setValue(self.profile.connector_a.pin_count)
        self.pending_pin_a = None
        self.selected_wire_index = None
        self._rebuild_connector_views()

    def _on_a_pin_count_changed(self, value):
        self.profile.connector_a.pin_count = value
        self._rebuild_connector_views()

    def _add_connector_b(self):
        existing_ids = {c.id for c in self.profile.connectors_b}
        n = 1
        while f"B{n}" in existing_ids:
            n += 1
        default_id = f"B{n}"

        pin_count, ok = QInputDialog.getInt(self, "Add Connector B", f"Pin count for {default_id}:", 34, 1, 80)
        if not ok:
            return
        spec = ConnectorSpec(id=default_id, label=f"Connector {default_id}", pin_count=pin_count)
        self.profile.connectors_b.append(spec)
        self._rebuild_connector_views()

    def _remove_connector_b(self, connector_id):
        affected_wires = [w for w in self.profile.wires if w.connector_b_id == connector_id]
        msg = f"Remove connector '{connector_id}'?"
        if affected_wires:
            msg += f"\n\nThis will also remove {len(affected_wires)} existing wire mapping(s) using it."
        reply = QMessageBox.question(self, "Remove connector", msg, QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes:
            return

        self.profile.connectors_b = [c for c in self.profile.connectors_b if c.id != connector_id]
        self.profile.wires = [w for w in self.profile.wires if w.connector_b_id != connector_id]
        self.pending_pin_a = None
        self.selected_wire_index = None
        self._rebuild_connector_views()

    def _wire_for_a_pin(self, pin_number):
        return next((w for w in self.profile.wires if w.connector_a_pin == pin_number), None)

    def _wire_for_b_pin(self, connector_id, pin_number):
        return next((w for w in self.profile.wires
                     if w.connector_b_id == connector_id and w.connector_b_pin == pin_number), None)

    def _on_pin_a_clicked(self, pin_number):
        existing = self._wire_for_a_pin(pin_number)
        if existing:
            self._confirm_remove_wire(existing)
            return

        self.pending_pin_a = pin_number
        self._refresh_pin_colors()

    def _on_pin_b_clicked(self, connector_id, pin_number):
        existing = self._wire_for_b_pin(connector_id, pin_number)
        if existing:
            self._confirm_remove_wire(existing)
            return

        if self.pending_pin_a is None:
            QMessageBox.information(self, "No pin A selected", "Left-click a pin on Connector A first.")
            return

        used_board_pins = {w.board_pin for w in self.profile.wires}
        board_pin = 1
        while board_pin in used_board_pins:
            board_pin += 1
        if board_pin > self.profile.board_pin_count:
            QMessageBox.warning(self, "No pins left", f"The board only has {self.profile.board_pin_count} pins, all in use.")
            return

        wire = WireMapping(
            board_pin=board_pin,
            connector_a_pin=self.pending_pin_a,
            connector_b_id=connector_id,
            connector_b_pin=pin_number,
        )
        self.profile.wires.append(wire)
        self.pending_pin_a = None
        self._refresh_wire_list()
        self._refresh_pin_colors()

    def _confirm_remove_wire(self, wire: WireMapping):
        reply = QMessageBox.question(
            self, "Remove mapping",
            f"Board pin {wire.board_pin}: A.{wire.connector_a_pin} <-> {wire.connector_b_id}.{wire.connector_b_pin}\n\n"
            "Remove this mapping?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.profile.wires.remove(wire)
            self.pending_pin_a = None
            self.selected_wire_index = None
            self._refresh_wire_list()
            self._refresh_pin_colors()

    def _toggle_bypass(self, connector_id, pin_number):
        spec = self.profile.connector_a if connector_id == "A" else \
            next((c for c in self.profile.connectors_b if c.id == connector_id), None)
        if spec is None:
            return

        if pin_number in spec.bypass_pins:
            spec.bypass_pins.remove(pin_number)
        else:
            # Neu pin dang duoc map, hoi truoc khi vua bypass vua xoa mapping
            existing = (self._wire_for_a_pin(pin_number) if connector_id == "A"
                        else self._wire_for_b_pin(connector_id, pin_number))
            if existing:
                reply = QMessageBox.question(
                    self, "Pin is mapped",
                    "This pin currently has a wire mapping. Marking it as BYPASS will "
                    "also remove that mapping. Continue?",
                    QMessageBox.Yes | QMessageBox.No,
                )
                if reply != QMessageBox.Yes:
                    return
                self.profile.wires.remove(existing)
                self._refresh_wire_list()
            spec.bypass_pins.append(pin_number)

        self.views[connector_id].set_bypass_pins(spec.bypass_pins)
        self._refresh_pin_colors()

    def _on_wire_row_selected(self, row):
        self.selected_wire_index = row if row >= 0 else None
        self._refresh_pin_colors()

    def _remove_selected_wire(self):
        row = self.wire_list.currentRow()
        if row < 0:
            return
        del self.profile.wires[row]
        self.selected_wire_index = None
        self._refresh_wire_list()
        self._refresh_pin_colors()

    def _auto_map_sequential(self):
        used_a = {w.connector_a_pin for w in self.profile.wires}
        avail_a = [p for p in range(1, self.profile.connector_a.pin_count + 1)
                   if p not in used_a and p not in self.profile.connector_a.bypass_pins]

        avail_b = []  # list de (connector_id, pin)
        for spec in self.profile.connectors_b:
            used_b = {w.connector_b_pin for w in self.profile.wires if w.connector_b_id == spec.id}
            for p in range(1, spec.pin_count + 1):
                if p not in used_b and p not in spec.bypass_pins:
                    avail_b.append((spec.id, p))

        if not avail_a or not avail_b:
            QMessageBox.information(self, "Nothing to map", "No unmapped, non-bypass pins available on both sides.")
            return

        used_board_pins = {w.board_pin for w in self.profile.wires}
        board_pin = 1
        count = 0
        for a_pin, (b_id, b_pin) in zip(avail_a, avail_b):
            while board_pin in used_board_pins:
                board_pin += 1
            if board_pin > self.profile.board_pin_count:
                break
            self.profile.wires.append(WireMapping(board_pin=board_pin, connector_a_pin=a_pin,
                                                    connector_b_id=b_id, connector_b_pin=b_pin))
            used_board_pins.add(board_pin)
            count += 1

        self._refresh_wire_list()
        self._refresh_pin_colors()
        QMessageBox.information(self, "Auto-map complete", f"Created {count} new wire mapping(s).")

    def _clear_all_wires(self):
        if not self.profile.wires:
            return
        reply = QMessageBox.question(self, "Clear all mappings",
                                      f"Remove all {len(self.profile.wires)} wire mapping(s)?",
                                      QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        self.profile.wires.clear()
        self.pending_pin_a = None
        self.selected_wire_index = None
        self._refresh_wire_list()
        self._refresh_pin_colors()

    def _save_profile(self):
        self.profiles_dir.mkdir(parents=True, exist_ok=True)
        safe_name = "".join(c if c.isalnum() or c in "-_ " else "_" for c in self.profile.name).strip() or "profile"
        default_path = self.profiles_dir / f"{safe_name}.json"
        path, _ = QFileDialog.getSaveFileName(self, "Save profile", str(default_path), "JSON (*.json)")
        if not path:
            return
        self.profile.save(Path(path))
        QMessageBox.information(self, "Saved", f"Profile saved to:\n{path}")

    def _open_profile(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open profile", str(self.profiles_dir), "JSON (*.json)")
        if not path:
            return
        self.profile = CableProfile.load(Path(path))
        self.name_edit.setText(self.profile.name)
        self.spin_a_pins.setValue(self.profile.connector_a.pin_count)
        self.pending_pin_a = None
        self.selected_wire_index = None
        self._rebuild_connector_views()
