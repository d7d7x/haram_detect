import sys
import os

# Ensure package path is resolved
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

def main():
    cli_flags = {"--cli", "--stremio", "-i", "--input", "-w", "--watch", "-h", "--help", "--mpv"}
    if any(arg in cli_flags for arg in sys.argv[1:]):
        from autocensor.cli import run_cli
        if "--cli" in sys.argv:
            sys.argv.remove("--cli")
        run_cli(sys.argv[1:])
    else:
        from autocensor.ui.main_window import AutoCensorApp
        app = AutoCensorApp()
        app.mainloop()

if __name__ == "__main__":
    main()
