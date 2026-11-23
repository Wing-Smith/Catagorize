"""检索页：文件名/路径子串检索（跨全部受管文件夹）。"""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout
from qfluentwidgets import BodyLabel, LineEdit, PushButton

from app.core.i18n import tr
from app.core.store import Database
from app.ui.pages.base_page import BasePage


class SearchPage(BasePage):
    def title(self) -> str:
        return tr("nav.search")

    def subtitle(self) -> str:
        return tr("search.subtitle")

    def __init__(self, parent=None):
        super().__init__(parent)
        self._db = Database().open()

        row = QHBoxLayout()
        row.setSpacing(8)
        self.search_box = LineEdit()
        self.search_box.setClearButtonEnabled(True)
        self.search_box.returnPressed.connect(self._run_search)
        self.go_btn = PushButton("")
        self.go_btn.clicked.connect(self._run_search)
        row.addWidget(self.search_box, 1)
        row.addWidget(self.go_btn)
        self.body().addLayout(row)

        self.results = BodyLabel("")
        self.results.setWordWrap(True)
        self.body().addWidget(self.results)
        self.body().addStretch(1)
        self.retranslate()

    def retranslate(self) -> None:
        super().retranslate()
        self.search_box.setPlaceholderText(tr("search.placeholder"))
        self.go_btn.setText(tr("search.button"))
        self._run_search()

    def _run_search(self) -> None:
        query = self.search_box.text().strip()
        if not query:
            self.results.setText("")
            return
        rows = self._db.search(query)
        if not rows:
            self.results.setText(tr("search.no_match", q=query))
            return
        lines = [
            tr("search.result_line", path=r["path_rel"], profile=r["profile_id"][:8], size=r["size"])
            for r in rows[:50]
        ]
        more = tr("search.more", n=len(rows) - 50) if len(rows) > 50 else ""
        self.results.setText("\n".join(lines) + more)
