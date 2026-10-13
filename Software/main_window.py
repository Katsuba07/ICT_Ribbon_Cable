"""Cua so chinh cua ung dung Cable Tester."""
from pathlib import Path
from PySide6.QtWidgets import QMainWindow, QTabWidget

from cable_setup_page import CableSetupPage
from test_run_page import TestRunPage

BASE_DIR = Path(__file__).resolve().parent
PROFILES_DIR = BASE_DIR / "profiles"
REPORTS_DIR = BASE_DIR / "reports"

TAB_SETUP = "Cable Setup"
TAB_TEST = "Run Test"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Ribbon Cable Tester")
        self.resize(1000, 750)

        self.tabs = QTabWidget()
        self.setup_page = CableSetupPage(PROFILES_DIR)
        self.test_page = TestRunPage(PROFILES_DIR, REPORTS_DIR)

        self.tabs.addTab(self.setup_page, TAB_SETUP)
        self.tabs.addTab(self.test_page, TAB_TEST)
        self.tabs.currentChanged.connect(self._on_tab_changed)

        self.setCentralWidget(self.tabs)

    def _on_tab_changed(self, index):
        # Refresh the profile list when switching to the Test tab,
        # in case a new profile was just created/saved on the Setup tab.
        if self.tabs.tabText(index) == TAB_TEST:
            self.test_page.refresh_profile_list()
