"""Collimator Design Tool — Entry Point."""
import sys
from app.application import create_application
from app.main_window import MainWindow


def main():
    app = create_application(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
