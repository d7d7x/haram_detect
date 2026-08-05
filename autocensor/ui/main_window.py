import tkinter as tk
from tkinter import ttk
import logging
from pathlib import Path
from autocensor import __version__
from autocensor.config import THEME
from autocensor.core.dictionary import CensorshipDictionary
from autocensor.ui.processing_tab import ProcessingTabFrame
from autocensor.ui.dictionary_tab import DictionaryTabFrame
from autocensor.ui.watcher_tab import WatcherTabFrame
from autocensor.ui.stremio_tab import StremioTabFrame
from autocensor.utils.ffmpeg_utils import is_ffmpeg_available

logger = logging.getLogger(__name__)

try:
    import customtkinter as ctk
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    HAS_CTK = True
except ImportError:
    HAS_CTK = False

from autocensor.config import THEME, DATA_DIR

class AutoCensorApp(ctk.CTk if HAS_CTK else tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("AutoCensor AI - Automated Subtitle & Audio Censorship Engine")
        self.geometry("980x680")
        self.minsize(900, 600)

        icon_ico = DATA_DIR / "app_icon.ico"
        if icon_ico.exists():
            try:
                self.iconbitmap(str(icon_ico))
            except Exception:
                pass

        self.dictionary = CensorshipDictionary()

        self.create_header()
        self.create_tabs()
        self.create_statusbar()

    def create_header(self):
        header_frame = ctk.CTkFrame(self, fg_color=THEME["surface"]) if HAS_CTK else tk.Frame(self, bg="#1e293b")
        header_frame.pack(fill="x", padx=0, pady=0)

        # Title & Subtitle
        text_frame = ctk.CTkFrame(header_frame, fg_color="transparent") if HAS_CTK else tk.Frame(header_frame, bg="#1e293b")
        text_frame.pack(side="left", padx=20, pady=12)

        title_lbl = ctk.CTkLabel(
            text_frame, text="⚡ AutoCensor AI",
            font=("Segoe UI", 22, "bold"), text_color=THEME["text_primary"]
        ) if HAS_CTK else tk.Label(text_frame, text="⚡ AutoCensor AI", font=("Segoe UI", 18, "bold"), fg="#f8fafc", bg="#1e293b")
        title_lbl.pack(anchor="w")

        sub_lbl = ctk.CTkLabel(
            text_frame, text="Automated Subtitle & Audio Polytheistic / Shirk Term Censorship Engine",
            font=("Segoe UI", 11), text_color=THEME["text_secondary"]
        ) if HAS_CTK else tk.Label(text_frame, text="Automated Subtitle & Audio Polytheistic / Shirk Term Censorship Engine", font=("Segoe UI", 9), fg="#94a3b8", bg="#1e293b")
        sub_lbl.pack(anchor="w")

        # Version Badge
        ver_lbl = ctk.CTkLabel(
            header_frame, text=f"v{__version__}",
            fg_color=THEME["primary"], corner_radius=12, text_color="white",
            font=("Segoe UI", 11, "bold"), width=60, height=24
        ) if HAS_CTK else tk.Label(header_frame, text=f"v{__version__}", bg="#6366f1", fg="white", font=("Segoe UI", 9, "bold"))
        ver_lbl.pack(side="right", padx=20)

    def create_tabs(self):
        if HAS_CTK:
            self.tabview = ctk.CTkTabview(self, fg_color=THEME["surface"])
            self.tabview.pack(fill="both", expand=True, padx=15, pady=10)

            self.tabview.add("Media Processing")
            self.tabview.add("Stremio Integration")
            self.tabview.add("Prohibited Terms Dictionary")
            self.tabview.add("Folder Watcher Service")

            ProcessingTabFrame(self.tabview.tab("Media Processing"), self.dictionary).pack(fill="both", expand=True)
            StremioTabFrame(self.tabview.tab("Stremio Integration"), self.dictionary).pack(fill="both", expand=True)
            DictionaryTabFrame(self.tabview.tab("Prohibited Terms Dictionary"), self.dictionary).pack(fill="both", expand=True)
            WatcherTabFrame(self.tabview.tab("Folder Watcher Service"), self.dictionary).pack(fill="both", expand=True)

        else:
            notebook = ttk.Notebook(self)
            notebook.pack(fill="both", expand=True, padx=10, pady=10)

            proc_tab = tk.Frame(notebook)
            stremio_tab = tk.Frame(notebook)
            dict_tab = tk.Frame(notebook)
            watch_tab = tk.Frame(notebook)

            notebook.add(proc_tab, text="Media Processing")
            notebook.add(stremio_tab, text="Stremio Integration")
            notebook.add(dict_tab, text="Prohibited Terms Dictionary")
            notebook.add(watch_tab, text="Folder Watcher Service")

            ProcessingTabFrame(proc_tab, self.dictionary).pack(fill="both", expand=True)
            StremioTabFrame(stremio_tab, self.dictionary).pack(fill="both", expand=True)
            DictionaryTabFrame(dict_tab, self.dictionary).pack(fill="both", expand=True)
            WatcherTabFrame(watch_tab, self.dictionary).pack(fill="both", expand=True)


    def create_statusbar(self):
        sb_frame = ctk.CTkFrame(self, height=28, fg_color=THEME["surface_light"]) if HAS_CTK else tk.Frame(self, bg="#334155", height=24)
        sb_frame.pack(fill="x", side="bottom")

        ffmpeg_ok = is_ffmpeg_available()
        status_text = f"FFmpeg Status: {'AVAILABLE ✓' if ffmpeg_ok else 'NOT FOUND ✗'}  |  Terms in Dictionary: {len(self.dictionary.terms)}"

        lbl = ctk.CTkLabel(sb_frame, text=status_text, font=("Segoe UI", 10), text_color="#cbd5e1") if HAS_CTK else tk.Label(sb_frame, text=status_text, font=("Segoe UI", 9), fg="#cbd5e1", bg="#334155")
        lbl.pack(side="left", padx=15)
