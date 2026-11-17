"""Main panel: Tasks, Notes and Notifications."""
from __future__ import annotations

from datetime import datetime, timedelta

from PySide6.QtCore import QDateTime, Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (QCheckBox, QDateTimeEdit, QHBoxLayout, QLabel,
                               QLineEdit, QListWidget, QListWidgetItem,
                               QPlainTextEdit, QPushButton, QSplitter,
                               QTabWidget, QVBoxLayout, QWidget)

from . import quickadd
from .store import Store, now_iso


def _fmt_due(iso: str | None) -> str:
    if not iso:
        return ""
    try:
        d = datetime.fromisoformat(iso)
    except ValueError:
        return iso
    now = datetime.now()
    if d.date() == now.date():
        return d.strftime("today %H:%M")
    if d.date() == (now + timedelta(days=1)).date():
        return d.strftime("tomorrow %H:%M")
    return d.strftime("%a %d %b %H:%M")


class Panel(QWidget):
    changed = Signal()          # tasks / notifications changed -> refresh runner

    def __init__(self, store: Store):
        super().__init__(None, Qt.Window)
        self.store = store
        self.setWindowTitle("CapyRunner")
        self.resize(520, 560)
        tabs = QTabWidget()
        tabs.addTab(self._tasks_tab(), "Tasks")
        tabs.addTab(self._notes_tab(), "Notes")
        tabs.addTab(self._notif_tab(), "Notifications")
        self.tabs = tabs
        lay = QVBoxLayout(self)
        lay.addWidget(tabs)
        self.refresh()

    # ================================================================== #
    # Tasks
    # ================================================================== #
    def _tasks_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)

        self.quick = QLineEdit(placeholderText="Add a task…  e.g. “Call Jason in 30m”, “Standup @9:30”, “Report tomorrow @14”")
        self.quick.returnPressed.connect(self._quick_add)
        v.addWidget(self.quick)

        self.show_done = QCheckBox("Show completed")
        self.show_done.toggled.connect(self.refresh_tasks)
        v.addWidget(self.show_done)

        split = QSplitter(Qt.Vertical)
        self.task_list = QListWidget()
        self.task_list.itemChanged.connect(self._task_checked)
        self.task_list.currentItemChanged.connect(self._task_selected)
        split.addWidget(self.task_list)

        editor = QWidget()
        ev = QVBoxLayout(editor)
        ev.setContentsMargins(0, 0, 0, 0)
        self.t_title = QLineEdit(placeholderText="Title")
        row = QHBoxLayout()
        self.t_has_due = QCheckBox("Due")
        self.t_due = QDateTimeEdit(calendarPopup=True, displayFormat="ddd dd MMM yyyy  HH:mm")
        self.t_has_due.toggled.connect(self.t_due.setEnabled)
        row.addWidget(self.t_has_due)
        row.addWidget(self.t_due, 1)
        self.t_notes = QPlainTextEdit(placeholderText="Notes for this task…")
        btns = QHBoxLayout()
        save = QPushButton("Save")
        snooze = QPushButton("Snooze 10 min")
        delete = QPushButton("Delete")
        save.clicked.connect(self._task_save)
        snooze.clicked.connect(self._task_snooze)
        delete.clicked.connect(self._task_delete)
        for b in (save, snooze, delete):
            btns.addWidget(b)
        ev.addWidget(self.t_title)
        ev.addLayout(row)
        ev.addWidget(self.t_notes, 1)
        ev.addLayout(btns)
        self.task_editor = editor
        split.addWidget(editor)
        split.setSizes([300, 220])
        v.addWidget(split, 1)
        editor.setEnabled(False)
        return w

    def focus_quick_add(self):
        self.tabs.setCurrentIndex(0)
        self.show_and_raise()
        self.quick.setFocus()

    def _quick_add(self):
        text = self.quick.text().strip()
        if not text:
            return
        title, due = quickadd.parse(text)
        self.store.add_task(title, due)
        self.quick.clear()
        self.refresh_tasks()
        self.changed.emit()

    def refresh_tasks(self):
        cur = self._current_task_id()
        lst = self.task_list
        lst.blockSignals(True)
        lst.clear()
        now = datetime.now()

        def key(t):
            return (t.get("done", False), t.get("due") or "9999", t.get("created", ""))

        for t in sorted(self.store.tasks, key=key):
            if t.get("done") and not self.show_done.isChecked():
                continue
            due = _fmt_due(t.get("due"))
            label = t["title"] + (f"   ·  {due}" if due else "") + ("   📝" if t.get("notes") else "")
            it = QListWidgetItem(label)
            it.setData(Qt.UserRole, t["id"])
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Checked if t.get("done") else Qt.Unchecked)
            if not t.get("done") and t.get("due"):
                try:
                    if datetime.fromisoformat(t["due"]) <= now:
                        it.setForeground(QBrush(QColor("#E53935")))
                except ValueError:
                    pass
            if t.get("done"):
                f = it.font()
                f.setStrikeOut(True)
                it.setFont(f)
                it.setForeground(QBrush(QColor("#888")))
            lst.addItem(it)
            if t["id"] == cur:
                lst.setCurrentItem(it)
        lst.blockSignals(False)
        if lst.currentItem() is None:
            self.task_editor.setEnabled(False)

    def _current_task_id(self) -> str | None:
        it = self.task_list.currentItem()
        return it.data(Qt.UserRole) if it else None

    def _task_checked(self, item: QListWidgetItem):
        t = self.store.task(item.data(Qt.UserRole))
        if t:
            t["done"] = item.checkState() == Qt.Checked
            t["completed"] = now_iso() if t["done"] else None
            self.store.save_data()
            QTimer.singleShot(0, self.refresh_tasks)
            self.changed.emit()

    def _task_selected(self, item, _prev=None):
        t = self.store.task(item.data(Qt.UserRole)) if item else None
        self.task_editor.setEnabled(bool(t))
        if not t:
            return
        self.t_title.setText(t["title"])
        self.t_notes.setPlainText(t.get("notes", ""))
        has = bool(t.get("due"))
        self.t_has_due.setChecked(has)
        self.t_due.setEnabled(has)
        dt = QDateTime.fromString(t["due"], Qt.ISODate) if has else QDateTime.currentDateTime().addSecs(3600)
        self.t_due.setDateTime(dt)

    def _task_save(self):
        t = self.store.task(self._current_task_id() or "")
        if not t:
            return
        t["title"] = self.t_title.text().strip() or t["title"]
        t["notes"] = self.t_notes.toPlainText()
        new_due = self.t_due.dateTime().toString(Qt.ISODate) if self.t_has_due.isChecked() else None
        if new_due != t.get("due"):
            t["due"] = new_due
            t["reminded"] = False
        self.store.save_data()
        self.refresh_tasks()
        self.changed.emit()

    def _task_snooze(self):
        t = self.store.task(self._current_task_id() or "")
        if not t:
            return
        t["due"] = (datetime.now() + timedelta(minutes=10)).replace(microsecond=0).isoformat()
        t["reminded"] = False
        self.store.save_data()
        self.refresh_tasks()
        self._task_selected(self.task_list.currentItem())
        self.changed.emit()

    def _task_delete(self):
        tid = self._current_task_id()
        if tid:
            self.store.delete_task(tid)
            self.refresh_tasks()
            self.changed.emit()

    # ================================================================== #
    # Notes
    # ================================================================== #
    def _notes_tab(self) -> QWidget:
        w = QWidget()
        h = QHBoxLayout(w)
        left = QVBoxLayout()
        self.note_list = QListWidget()
        self.note_list.currentItemChanged.connect(self._note_selected)
        add = QPushButton("+ New note")
        add.clicked.connect(self._note_add)
        rm = QPushButton("Delete")
        rm.clicked.connect(self._note_delete)
        left.addWidget(add)
        left.addWidget(self.note_list, 1)
        left.addWidget(rm)
        h.addLayout(left, 2)
        self.note_body = QPlainTextEdit(placeholderText="Select or create a note. First line becomes the title.")
        self.note_body.setEnabled(False)
        self._note_timer = QTimer(self, singleShot=True, interval=500, timeout=self._note_save)
        self.note_body.textChanged.connect(self._note_timer.start)
        h.addWidget(self.note_body, 5)
        return w

    def refresh_notes(self):
        cur = self.note_list.currentItem()
        cur_id = cur.data(Qt.UserRole) if cur else None
        self.note_list.blockSignals(True)
        self.note_list.clear()
        for n in self.store.notes:
            it = QListWidgetItem(n["title"] or "Untitled")
            it.setData(Qt.UserRole, n["id"])
            self.note_list.addItem(it)
            if n["id"] == cur_id:
                self.note_list.setCurrentItem(it)
        self.note_list.blockSignals(False)

    def _note(self, nid):
        return next((n for n in self.store.notes if n["id"] == nid), None)

    def _note_add(self):
        n = self.store.add_note("New note", "New note\n")
        self.refresh_notes()
        self.note_list.setCurrentRow(0)
        self.note_body.setFocus()

    def _note_selected(self, item, _prev=None):
        self._note_save()
        n = self._note(item.data(Qt.UserRole)) if item else None
        self.note_body.blockSignals(True)
        self.note_body.setPlainText(n["body"] if n else "")
        self.note_body.blockSignals(False)
        self.note_body.setEnabled(bool(n))
        self._editing_note = n["id"] if n else None

    def _note_save(self):
        nid = getattr(self, "_editing_note", None)
        n = self._note(nid) if nid else None
        if not n:
            return
        body = self.note_body.toPlainText()
        if body == n["body"]:
            return
        n["body"] = body
        n["title"] = (body.strip().splitlines() or ["Untitled"])[0][:60]
        n["updated"] = now_iso()
        self.store.save_data()
        it = self.note_list.currentItem()
        if it and it.data(Qt.UserRole) == nid:
            it.setText(n["title"])

    def _note_delete(self):
        it = self.note_list.currentItem()
        if not it:
            return
        nid = it.data(Qt.UserRole)
        self.store.notes = [n for n in self.store.notes if n["id"] != nid]
        self.store.save_data()
        self._editing_note = None
        self.note_body.setEnabled(False)
        self.note_body.clear()
        self.refresh_notes()

    # ================================================================== #
    # Notifications
    # ================================================================== #
    def _notif_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        self.notif_list = QListWidget()
        self.notif_list.setWordWrap(True)
        row = QHBoxLayout()
        read = QPushButton("Mark all read")
        clear = QPushButton("Clear all")
        read.clicked.connect(self._mark_read)
        clear.clicked.connect(self._clear_notifs)
        row.addWidget(read)
        row.addWidget(clear)
        v.addWidget(self.notif_list, 1)
        v.addLayout(row)
        self.webhook_hint = QLabel()
        self.webhook_hint.setWordWrap(True)
        self.webhook_hint.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.webhook_hint.setStyleSheet("color: #888;")
        v.addWidget(self.webhook_hint)
        return w

    def refresh_notifs(self):
        self.notif_list.clear()
        for n in reversed(self.store.notifications):
            t = n["time"].replace("T", " ")[:16]
            src = f"[{n['source']}] " if n.get("source") else ""
            it = QListWidgetItem(f"{'● ' if not n.get('read') else ''}{src}{n['title']}\n{n.get('body', '')}\n{t}".strip())
            if not n.get("read"):
                f = it.font()
                f.setBold(True)
                it.setFont(f)
            self.notif_list.addItem(it)
        s = self.store.settings
        if s.get("webhook_enabled"):
            tok = ' -H "X-Token: <your token>"' if s.get("webhook_token") else ""
            self.webhook_hint.setText(
                f"Webhook on: curl -X POST http://127.0.0.1:{s['webhook_port']}/notify{tok} "
                "-H 'Content-Type: application/json' -d '{\"title\":\"Build done\",\"body\":\"…\",\"source\":\"CI\"}'")
        else:
            self.webhook_hint.setText("Tip: turn on the webhook in Settings so other apps can send notifications here.")
        idx = self.tabs.indexOf(self.notif_list.parentWidget())
        u = self.store.unread()
        self.tabs.setTabText(idx, f"Notifications ({u})" if u else "Notifications")

    def _mark_read(self):
        self.store.mark_all_read()
        self.refresh_notifs()
        self.changed.emit()

    def _clear_notifs(self):
        self.store.notifications = []
        self.store.save_data()
        self.refresh_notifs()
        self.changed.emit()

    def show_notifications(self):
        self.tabs.setCurrentIndex(2)
        self.show_and_raise()

    # ================================================================== #
    def refresh(self):
        self.refresh_tasks()
        self.refresh_notes()
        self.refresh_notifs()

    def show_and_raise(self):
        self.refresh()
        self.show()
        self.setWindowState(self.windowState() & ~Qt.WindowMinimized)
        self.raise_()
        self.activateWindow()

    quitting = False

    def closeEvent(self, e):
        self._note_save()
        if self.quitting:
            e.accept()
            return
        e.ignore()
        self.hide()
