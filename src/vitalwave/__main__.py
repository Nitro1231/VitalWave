# src/vitalwave/__main__.py

import sys
import logging

from PySide6 import QtGui, QtWidgets
from vitalwave.dashboard import Dashboard
from vitalwave.receiver import RadarReceiver


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-7s  %(message)s",
        datefmt="%H:%M:%S",
    )

    app = QtWidgets.QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setFont(QtGui.QFont("Segoe UI", 10))

    receiver = RadarReceiver()
    window = Dashboard(receiver)
    receiver.start()
    window.show()
    raise SystemExit(app.exec())


if __name__ == "__main__":
    main()
