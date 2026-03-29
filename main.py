"""
English Coach — main entry point.
Run: python main.py
"""

import os
import sys
import subprocess
import shutil

# Ensure we can import sibling modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Auto-install dependencies if missing
def install_deps():
    try:
        import flask
        import anthropic
        import dotenv
    except ImportError:
        print("📦 Installing dependencies...")
        req_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "requirements.txt")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", req_file, "-q"])
        print("✅ Dependencies installed!\n")

install_deps()

from dotenv import load_dotenv

# Load .env from the english_coach directory
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")

# Auto-create .env from example if it doesn't exist
if not os.path.exists(env_path):
    example_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env.example")
    if os.path.exists(example_path):
        shutil.copy(example_path, env_path)
        print(f"📄 Created .env file at: {env_path}")

load_dotenv(env_path)

# Check for API key
api_key = os.environ.get("ANTHROPIC_API_KEY", "")
if not api_key or api_key == "your_api_key_here":
    print("\n" + "=" * 50)
    print("  ⚠️  ANTHROPIC_API_KEY not set!")
    print("=" * 50)
    print(f"\n  Edit your .env file at:")
    print(f"  {env_path}")
    print(f"\n  Replace 'your_api_key_here' with your real key.")
    print("  Get it at: https://console.anthropic.com/")
    print("\n  The app will start, but sentence analysis")
    print("  won't work until you add your key.\n")

from app import app

if __name__ == "__main__":
    import webbrowser
    print("\n" + "=" * 50)
    print("  📝 English Coach — Starting Up!")
    print("=" * 50)
    print("\n  Opening in your browser...")
    print("  🌐 http://localhost:5050")
    print("\n  Press Ctrl+C to stop.\n")

    # Auto-open browser
    webbrowser.open("http://localhost:5050")

    app.run(debug=False, port=5050, host="0.0.0.0")
