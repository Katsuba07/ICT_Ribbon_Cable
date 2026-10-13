"""Widget hien thi 1 connector duoi dang luoi cham tron danh so, co the click chon,
to mau theo trang thai, va ho tro nhieu kieu sap xep (layout) pin."""
import math
from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsEllipseItem, QGraphicsTextItem
from PySide6.QtGui import QBrush, QPen, QColor, QFont
from PySide6.QtCore import Qt, Signal

PIN_RADIUS = 10
PIN_SPACING_X = 34
PIN_SPACING_Y = 34
MARGIN = 30
TITLE_OFFSET_Y = 30

COLOR_NORMAL = QColor("#cccccc")
COLOR_BYPASS = QColor("#888888")
COLOR_SELECTED = QColor("#3399ff")
COLOR_PASS = QColor("#4caf50")
COLOR_OPEN = QColor("#e53935")
COLOR_SHORT = QColor("#ffb300")

STATUS_COLORS = {
    "normal": COLOR_NORMAL,
    "bypass": COLOR_BYPASS,
    "selected": COLOR_SELECTED,
    "pass": COLOR_PASS,
    "open": COLOR_OPEN,
    "short": COLOR_SHORT,
}

LAYOUT_CHOICES = ["zigzag", "rows", "clockwise", "custom"]
LAYOUT_DISPLAY_NAMES = {
    "zigzag": "Even/Odd (zigzag)",
    "rows": "Top/Bottom (rows)",
    "clockwise": "Clockwise",
    "custom": "Custom order",
}


def compute_pin_grid_positions(pin_count: int, layout: str = "zigzag", custom_order=None):
    """Tra ve dict {pin_number: (col, row)} - toa do luoi (chua nhan spacing)."""
    positions = {}

    if layout == "rows":
        cols = max(1, math.ceil(pin_count / 2))
        for pin in range(1, pin_count + 1):
            idx = pin - 1
            if idx < cols:
                positions[pin] = (idx, 0)
            else:
                positions[pin] = (idx - cols, 1)
        return positions

    if layout == "clockwise":
        # Day ribbon chi co 2 hang: hang tren di trai->phai (pin 1..cols), hang
        # duoi di NGUOC LAI phai->trai (pin cols+1..pin_count) de khep vong
        # theo dung chieu kim dong ho - day la quy uoc pho bien cho connector
        # IDC 2 hang, khong phai xep thanh hinh vuong.
        cols = max(1, math.ceil(pin_count / 2))
        bottom_count = pin_count - cols
        for pin in range(1, cols + 1):
            positions[pin] = (pin - 1, 0)
        for j in range(bottom_count):
            pin = cols + 1 + j
            col = (cols - 1) - j
            positions[pin] = (col, 1)
        return positions

    if layout == "custom" and custom_order:
        # custom_order la thu tu HIEN THI (vi tri 0,1,2... se la pin custom_order[i]),
        # dat theo cung kieu hinh hoc zigzag mac dinh.
        cols = max(1, math.ceil(pin_count / 2))
        valid_order = [p for p in custom_order if 1 <= p <= pin_count]
        # bat ky pin nao bi thieu trong custom_order (nhap sai/thieu) se duoc noi vao cuoi
        missing = [p for p in range(1, pin_count + 1) if p not in valid_order]
        full_order = valid_order + missing
        for slot_idx, pin in enumerate(full_order):
            col = slot_idx // 2
            row = slot_idx % 2
            positions[pin] = (col, row)
        return positions

    # "zigzag" (mac dinh) - kieu IDC: pin le hang tren, pin chan hang duoi
    for pin in range(1, pin_count + 1):
        idx = pin - 1
        col = idx // 2
        row = idx % 2
        positions[pin] = (col, row)
    return positions


class PinItem(QGraphicsEllipseItem):
    def __init__(self, pin_number: int, x: float, y: float, on_left_click, on_right_click):
        super().__init__(-PIN_RADIUS, -PIN_RADIUS, PIN_RADIUS * 2, PIN_RADIUS * 2)
        self.pin_number = pin_number
        self.on_left_click = on_left_click
        self.on_right_click = on_right_click
        self.setPos(x, y)
        self.setBrush(QBrush(COLOR_NORMAL))
        self.setPen(QPen(Qt.black, 1))
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(f"Pin {pin_number}\nLeft-click: map wire\nRight-click: toggle bypass")

    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            if self.on_right_click:
                self.on_right_click(self.pin_number)
        else:
            if self.on_left_click:
                self.on_left_click(self.pin_number)
        super().mousePressEvent(event)

    def set_status_color(self, color: QColor):
        self.setBrush(QBrush(color))


class ConnectorView(QGraphicsView):
    """Ve 1 connector duoi dang luoi cham tron, ho tro nhieu kieu layout."""
    pinClicked = Signal(int)       # click chuot trai
    pinRightClicked = Signal(int)  # click chuot phai (toggle bypass)

    def __init__(self, label: str, pin_count: int, bypass_pins=None,
                 layout: str = "zigzag", custom_order=None, parent=None):
        super().__init__(parent)
        self.label = label
        self.pin_count = pin_count
        self.bypass_pins = set(bypass_pins or [])
        self.layout = layout
        self.custom_order = list(custom_order or [])
        self.pin_items = {}

        self.scene_ = QGraphicsScene(self)
        self.setScene(self.scene_)
        self._build()

    def _build(self):
        self.scene_.clear()
        self.pin_items.clear()

        title = QGraphicsTextItem(self.label)
        title.setFont(QFont("Sans Serif", 10, QFont.Bold))
        title.setPos(0, 0)
        self.scene_.addItem(title)

        positions = compute_pin_grid_positions(self.pin_count, self.layout, self.custom_order)
        max_col = max((c for c, r in positions.values()), default=0)
        max_row = max((r for c, r in positions.values()), default=0)

        for pin in range(1, self.pin_count + 1):
            col, row = positions.get(pin, (0, 0))
            x = MARGIN + col * PIN_SPACING_X
            y = MARGIN + TITLE_OFFSET_Y + row * PIN_SPACING_Y

            item = PinItem(pin, x, y, self._on_pin_left_clicked, self._on_pin_right_clicked)
            if pin in self.bypass_pins:
                item.set_status_color(COLOR_BYPASS)
            self.scene_.addItem(item)
            self.pin_items[pin] = item

            lbl = QGraphicsTextItem(str(pin))
            lbl.setFont(QFont("Sans Serif", 7))
            lbl.setPos(x - 6, y - 28 if row == 0 else y + 12)
            self.scene_.addItem(lbl)

        w = MARGIN * 2 + (max_col + 1) * PIN_SPACING_X
        h = MARGIN * 2 + TITLE_OFFSET_Y + (max_row + 1) * PIN_SPACING_Y
        self.scene_.setSceneRect(0, 0, w, h)

    def set_layout(self, layout: str, custom_order=None):
        self.layout = layout
        if custom_order is not None:
            self.custom_order = list(custom_order)
        self._build()

    def _on_pin_left_clicked(self, pin_number: int):
        self.pinClicked.emit(pin_number)

    def _on_pin_right_clicked(self, pin_number: int):
        self.pinRightClicked.emit(pin_number)

    def set_bypass_pins(self, bypass_pins):
        self.bypass_pins = set(bypass_pins)
        self.reset_colors()

    def highlight_pin(self, pin_number: int, color: QColor):
        item = self.pin_items.get(pin_number)
        if item:
            item.set_status_color(color)

    def reset_colors(self):
        for pin, item in self.pin_items.items():
            color = COLOR_BYPASS if pin in self.bypass_pins else COLOR_NORMAL
            item.set_status_color(color)

    def set_status(self, pin_number: int, status: str):
        self.highlight_pin(pin_number, STATUS_COLORS.get(status, COLOR_NORMAL))
