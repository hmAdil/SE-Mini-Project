import sys

from app import create_app

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    create_app().run(port=port)
