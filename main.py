# Entry point for the Foundation GTK app.
# Run with: python3 main.py

import sys
from foundation.app import FoundationApp


def main():
    app = FoundationApp()
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
