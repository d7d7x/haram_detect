import sys
import os

# Ensure package path is resolved
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

def main():
    if "--cli" in sys.argv:
        from autocensor.cli import run_cli
        # Remove --cli argument before passing to argparse
        sys.argv.remove("--cli")
        run_cli(sys.argv[1:])
    else:
        from autocensor.ui.main_window import AutoCensorApp
        app = AutoCensorApp()
        app.mainloop()

if __name__ == "__main__":
    main()
