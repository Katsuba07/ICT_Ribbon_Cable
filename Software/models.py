"""Data models cho cau hinh cap (Cable Profile)."""
from __future__ import annotations
import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Optional


@dataclass
class ConnectorSpec:
    id: str                # "A" hoac "B1", "B2", ...
    label: str              # ten hien thi
    pin_count: int
    bypass_pins: List[int] = field(default_factory=list)  # cac chan khong dung (1-based)
    layout: str = "zigzag"  # "zigzag" | "rows" | "clockwise" | "custom"
    custom_order: List[int] = field(default_factory=list)  # chi dung khi layout == "custom"

    def to_dict(self):
        return asdict(self)

    @staticmethod
    def from_dict(d):
        return ConnectorSpec(
            id=d["id"],
            label=d.get("label", d["id"]),
            pin_count=d["pin_count"],
            bypass_pins=list(d.get("bypass_pins", [])),
            layout=d.get("layout", "zigzag"),
            custom_order=list(d.get("custom_order", [])),
        )


@dataclass
class WireMapping:
    board_pin: int          # 1..80, chan tren board dung de test soi day nay
    connector_a_pin: int
    connector_b_id: str
    connector_b_pin: int

    def to_dict(self):
        return asdict(self)

    @staticmethod
    def from_dict(d):
        return WireMapping(**d)


@dataclass
class CableProfile:
    name: str
    board_pin_count: int = 80
    connector_a: Optional[ConnectorSpec] = None
    connectors_b: List[ConnectorSpec] = field(default_factory=list)
    wires: List[WireMapping] = field(default_factory=list)

    def active_mask(self) -> List[bool]:
        """Tra ve mask 80 phan tu bool: True neu board_pin do co 1 wire su dung."""
        mask = [False] * self.board_pin_count
        for w in self.wires:
            if 1 <= w.board_pin <= self.board_pin_count:
                mask[w.board_pin - 1] = True
        return mask

    def wire_for_board_pin(self, board_pin: int) -> Optional[WireMapping]:
        for w in self.wires:
            if w.board_pin == board_pin:
                return w
        return None

    def to_dict(self):
        return {
            "name": self.name,
            "board_pin_count": self.board_pin_count,
            "connector_a": self.connector_a.to_dict() if self.connector_a else None,
            "connectors_b": [c.to_dict() for c in self.connectors_b],
            "wires": [w.to_dict() for w in self.wires],
        }

    @staticmethod
    def from_dict(d):
        return CableProfile(
            name=d["name"],
            board_pin_count=d.get("board_pin_count", 80),
            connector_a=ConnectorSpec.from_dict(d["connector_a"]) if d.get("connector_a") else None,
            connectors_b=[ConnectorSpec.from_dict(c) for c in d.get("connectors_b", [])],
            wires=[WireMapping.from_dict(w) for w in d.get("wires", [])],
        )

    def save(self, path: Path):
        Path(path).write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

    @staticmethod
    def load(path: Path) -> "CableProfile":
        d = json.loads(Path(path).read_text(encoding="utf-8"))
        return CableProfile.from_dict(d)


def list_profiles(profiles_dir: Path) -> List[Path]:
    profiles_dir.mkdir(parents=True, exist_ok=True)
    return sorted(profiles_dir.glob("*.json"))
