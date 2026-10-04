# src/vitalwave/dashboard.py

import pyqtgraph as pg

from queue import Empty
from collections import deque
from PySide6 import QtCore, QtGui, QtWidgets
from vitalwave.receiver import METRICS, PHASES


pg.setConfigOptions(antialias=True)

HISTORY = 120
AVERAGE_INTERVAL_MS = 3000
AVERAGED = ("HR", "BR")

COLORS = {
    "HR": "#ff5d73",
    "BR": "#2ad4c4",
    "D": "#f0b44c",
    "TP": "#7eb6ff",
    "BP": "#2ad4c4",
    "HP": "#ff5d73",
}


class SignalPlot(QtWidgets.QFrame):
    """One labeled card with the latest value and a scrolling line."""

    def __init__(self, title, color, unit="", digits=None, large=False):
        super().__init__()
        self.setObjectName("card")
        self.unit = unit
        self.digits = digits
        self.samples = deque(maxlen=HISTORY)
        self.setStyleSheet(
            "QFrame#card {"
            "background: #161d27;"
            "border-radius: 16px;"
            f"border-top: 3px solid {color};"
            "}"
        )

        self.title_label = QtWidgets.QLabel(title.upper())
        self.title_label.setStyleSheet(
            "color: #8ea0b5; font-size: 11px; letter-spacing: 1.2px;"
        )

        self.value_label = QtWidgets.QLabel("--")
        if large:
            size = 46
        elif unit:
            size = 20
        else:
            size = 14
        self.value_label.setStyleSheet(
            f"color: {color}; font-family: Consolas; font-size: {size}px;"
        )

        header = QtWidgets.QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.addWidget(self.value_label)
        if unit:
            unit_label = QtWidgets.QLabel(unit)
            unit_label.setStyleSheet("color: #8ea0b5; font-size: 13px;")
            header.addWidget(unit_label, alignment=QtCore.Qt.AlignmentFlag.AlignBottom)
        header.addStretch()

        self.plot = pg.PlotWidget()
        self.plot.setBackground("#161d27")
        self.plot.setMenuEnabled(False)
        self.plot.setMouseEnabled(False, False)
        self.plot.hideButtons()
        self.plot.showGrid(x=True, y=True, alpha=0.28)
        self.plot.getViewBox().setDefaultPadding(0.08)
        tick_font = QtGui.QFont("Segoe UI", 9 if large else 7)
        for name in ("left", "bottom"):
            axis = self.plot.getAxis(name)
            axis.setPen(pg.mkPen("#6d8296"))
            axis.setTextPen(pg.mkPen("#8ea0b5"))
            axis.setStyle(tickFont=tick_font, tickLength=4, maxTickLevel=0)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )
        self.plot.setMinimumHeight(80 if large else 48)

        self.curve = self.plot.plot(pen=pg.mkPen(color, width=2))

        layout = QtWidgets.QVBoxLayout(self)
        if large:
            layout.setContentsMargins(16, 12, 16, 12)
        else:
            layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(2)
        layout.addWidget(self.title_label)
        layout.addLayout(header)
        layout.addWidget(self.plot, stretch=1)

    def set_title(self, title):
        self.title_label.setText(title.upper())

    def add(self, value):
        value = float(value)
        self.samples.append(value)
        if self.digits is not None:
            text = f"{value:.{self.digits}f}"
        elif self.unit in ("bpm", "/min"):
            text = f"{value:.0f}"
        else:
            text = f"{value:.2f}"
        self.value_label.setText(text)
        self.curve.setData(list(self.samples))


class Dashboard(QtWidgets.QMainWindow):
    """Dark monitor for heart rate, breathing, distance, and phase."""

    def __init__(self, receiver):
        super().__init__()
        self.receiver = receiver
        self.plots = {}
        self.average_plots = {}
        self._windows = {key: [] for key in AVERAGED}
        self.setWindowTitle("VitalWave")
        self.resize(1100, 900)
        self._build()

        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._drain)
        self._timer.start(50)

        self._average_timer = QtCore.QTimer(self)
        self._average_timer.timeout.connect(self._commit_averages)
        self._average_timer.start(AVERAGE_INTERVAL_MS)
        self.interval_slider.valueChanged.connect(self._set_interval)
        self.interval_input.editingFinished.connect(self._apply_interval_text)
        QtCore.QTimer.singleShot(0, self._set_initial_split)

    def _set_initial_split(self):
        height = self.splitter.height()
        top = int(height * 0.62)
        self.splitter.setSizes([top, max(1, height - top)])

    def _build(self):
        root = QtWidgets.QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)

        title = QtWidgets.QLabel("VitalWave")
        title.setStyleSheet("font-size: 26px; font-weight: 600;")
        subtitle = QtWidgets.QLabel("60 GHz contactless heart and breathing")
        subtitle.setStyleSheet("color: #8ea0b5; font-size: 13px;")

        heading = QtWidgets.QVBoxLayout()
        heading.setSpacing(0)
        heading.addWidget(title)
        heading.addWidget(subtitle)

        self.status = QtWidgets.QLabel("Starting...")
        self.status.setStyleSheet("color: #f0b44c; font-size: 13px;")

        header = QtWidgets.QHBoxLayout()
        header.addLayout(heading)
        header.addStretch()
        header.addWidget(self.status, alignment=QtCore.Qt.AlignmentFlag.AlignVCenter)

        top = QtWidgets.QWidget()
        top_layout = QtWidgets.QVBoxLayout(top)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(10)
        top_layout.addLayout(self._build_rate_controls())

        averages = QtWidgets.QHBoxLayout()
        averages.setSpacing(14)
        for key in AVERAGED:
            name, unit = METRICS[key]
            plot = SignalPlot(f"{name} · 1s", COLORS[key], unit, digits=1, large=True)
            self.average_plots[key] = plot
            averages.addWidget(plot)
        top_layout.addLayout(averages, stretch=1)

        metrics = QtWidgets.QHBoxLayout()
        metrics.setSpacing(14)
        for key, (name, unit) in METRICS.items():
            metrics.addWidget(self._add_plot(key, name, COLORS[key], unit))

        phases = QtWidgets.QHBoxLayout()
        phases.setSpacing(14)
        for key, name in PHASES.items():
            phases.addWidget(self._add_plot(key, name, COLORS[key]))

        bottom = QtWidgets.QWidget()
        lower = QtWidgets.QVBoxLayout(bottom)
        lower.setContentsMargins(0, 0, 0, 0)
        lower.setSpacing(14)
        lower.addLayout(metrics, stretch=1)
        lower.addLayout(phases, stretch=1)

        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        self.splitter.addWidget(top)
        self.splitter.addWidget(bottom)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setHandleWidth(6)
        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setStyleSheet(
            "QSplitter { background: #0c1016; }"
            "QSplitter::handle:vertical {"
            "background: #3d4d60;"
            "margin: 1px 460px;"
            "border-radius: 2px;"
            "}"
            "QSplitter::handle:vertical:hover { background: #8ea0b5; }"
        )

        layout = QtWidgets.QVBoxLayout(root)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(14)
        layout.addLayout(header)
        layout.addWidget(self.splitter, stretch=1)

        self.setStyleSheet(
            "QMainWindow, QWidget#root { background: #0c1016; }"
            "QLabel { background: transparent; color: #eef3f8; }"
        )

    def _build_rate_controls(self):
        label = QtWidgets.QLabel("Update rate")
        label.setStyleSheet("color: #8ea0b5; font-size: 13px;")

        self.interval_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.interval_slider.setRange(100, 10000)
        self.interval_slider.setSingleStep(100)
        self.interval_slider.setPageStep(500)
        self.interval_slider.setValue(AVERAGE_INTERVAL_MS)
        self.interval_slider.setFixedWidth(220)
        self.interval_slider.setFixedHeight(22)
        self.interval_slider.setStyleSheet(
            "QSlider::groove:horizontal {"
            "height: 4px; background: #2a3542; border-radius: 2px;"
            "}"
            "QSlider::sub-page:horizontal {"
            "background: #2ad4c4; height: 4px; border-radius: 2px;"
            "}"
            "QSlider::handle:horizontal {"
            "width: 14px; margin-top: -5px; margin-bottom: -5px;"
            "background: #2ad4c4; border-radius: 7px;"
            "}"
        )

        self.interval_input = QtWidgets.QLineEdit(str(AVERAGE_INTERVAL_MS))
        self.interval_input.setValidator(QtGui.QIntValidator(100, 10000, self.interval_input))
        self.interval_input.setFixedWidth(72)
        self.interval_input.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
        self.interval_input.setStyleSheet(
            "background: #161d27; color: #eef3f8; border: 1px solid #2c3948;"
            "border-radius: 6px; padding: 4px 8px; font-family: Consolas;"
        )

        unit = QtWidgets.QLabel("ms")
        unit.setStyleSheet("color: #8ea0b5; font-size: 13px;")

        row = QtWidgets.QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)
        row.addStretch()
        row.addWidget(label)
        row.addWidget(self.interval_slider)
        row.addWidget(self.interval_input)
        row.addWidget(unit)
        row.addStretch()
        return row

    def _set_interval(self, ms):
        ms = max(100, min(10000, int(ms)))
        self.interval_slider.blockSignals(True)
        self.interval_slider.setValue(ms)
        self.interval_slider.blockSignals(False)
        self.interval_input.blockSignals(True)
        self.interval_input.setText(str(ms))
        self.interval_input.blockSignals(False)
        self._average_timer.setInterval(ms)
        if self._average_timer.isActive():
            self._average_timer.start()
        for window in self._windows.values():
            window.clear()
        label = f"{ms / 1000:g}s"
        for key, plot in self.average_plots.items():
            name, _unit = METRICS[key]
            plot.set_title(f"{name} · {label}")

    def _apply_interval_text(self):
        try:
            ms = int(self.interval_input.text().strip())
        except ValueError:
            self.interval_input.setText(str(self._average_timer.interval()))
            return
        self._set_interval(ms)

    def _add_plot(self, key, title, color, unit=""):
        plot = SignalPlot(title, color, unit)
        self.plots[key] = plot
        return plot

    def add_reading(self, key, value):
        plot = self.plots.get(key)
        if plot is not None:
            plot.add(value)
        window = self._windows.get(key)
        if window is not None:
            window.append(float(value))

    def _commit_averages(self):
        for key, window in self._windows.items():
            if not window:
                continue
            average = sum(window) / len(window)
            self.average_plots[key].add(average)
            window.clear()

    def set_status(self, text):
        lowered = text.lower()
        if text == "Connected":
            color = "#2ad4c4"
        elif "not found" in lowered or "lost" in lowered:
            color = "#ff5d73"
        else:
            color = "#f0b44c"
        self.status.setText(f"●  {text}")
        self.status.setStyleSheet(f"color: {color}; font-size: 13px;")

    def _drain(self):
        while True:
            try:
                kind, *payload = self.receiver.events.get_nowait()
            except Empty:
                return
            if kind == "status":
                self.set_status(payload[0])
            elif kind == "value":
                self.add_reading(payload[0], payload[1])
