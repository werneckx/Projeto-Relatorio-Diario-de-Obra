from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))

try:
    from app import create_app
    app = create_app()
    with app.app_context():
        print("Imports successful.")
except Exception as e:
    import traceback
    traceback.print_exc()
