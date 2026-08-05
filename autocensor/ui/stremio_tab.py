import tkinter as tk
from tkinter import ttk, messagebox
import logging
from pathlib import Path
from autocensor.core.dictionary import CensorshipDictionary
from autocensor.core.watcher import WatcherService
from autocensor.core.media_processor import MediaProcessor
from autocensor.utils.stremio_utils import get_stremio_cache_dir, find_external_player

logger = logging.getLogger(__name__)

try:
    import customtkinter as ctk
    HAS_CTK = True
except ImportError:
    HAS_CTK = False

class StremioTabFrame(ctk.CTkFrame if HAS_CTK else tk.Frame):
    def __init__(self, master, dictionary: CensorshipDictionary):
        super().__init__(master)
        self.dictionary = dictionary
        self.processor = MediaProcessor(dictionary)
        self.watcher: WatcherService = None
        self.create_widgets()

    def create_widgets(self):
        # Header Info Card
        card = ctk.CTkFrame(self) if HAS_CTK else tk.LabelFrame(self, text="Stremio Integration Status", padx=15, pady=15)
        card.pack(fill="x", padx=15, pady=15)

        cache_dir = get_stremio_cache_dir()
        player_path = find_external_player()

        # Cache Status
        c_status = f"✓ Detected: {cache_dir}" if cache_dir else "⚠ Not auto-detected (Will use default appdata path)"
        c_color = "#10b981" if cache_dir else "#f59e0b"

        c_lbl = ctk.CTkLabel(card, text=f"Stremio Cache: {c_status}", font=("Segoe UI", 12, "bold"), text_color=c_color) if HAS_CTK else tk.Label(card, text=f"Stremio Cache: {c_status}", fg=c_color, font=("Segoe UI", 10, "bold"))
        c_lbl.pack(anchor="w", pady=4)

        # Player Status
        p_status = f"✓ Found Player: {player_path.name}" if player_path else "⚠ No VLC/MPV found (will use OS default player)"
        p_color = "#10b981" if player_path else "#94a3b8"

        p_lbl = ctk.CTkLabel(card, text=f"Playback Engine: {p_status}", font=("Segoe UI", 12), text_color=p_color) if HAS_CTK else tk.Label(card, text=f"Playback Engine: {p_status}", fg=p_color, font=("Segoe UI", 10))
        p_lbl.pack(anchor="w", pady=4)

        # One-Click Auto-Watch Button
        action_frame = ctk.CTkFrame(self) if HAS_CTK else tk.Frame(self)
        action_frame.pack(fill="x", padx=15, pady=10)

        self.status_lbl = ctk.CTkLabel(action_frame, text="● STREMIO WATCHER STOPPED", text_color="#ef4444", font=("Segoe UI", 12, "bold")) if HAS_CTK else tk.Label(action_frame, text="● STREMIO WATCHER STOPPED", fg="#ef4444", font=("Segoe UI", 10, "bold"))
        self.status_lbl.pack(side="left", padx=10)

        self.toggle_btn = ctk.CTkButton(
            action_frame, text="⚡ Enable Auto-Censor for Stremio",
            fg_color="#6366f1", hover_color="#4f46e5",
            font=("Segoe UI", 13, "bold"), height=38,
            command=self.toggle_stremio_watcher
        ) if HAS_CTK else tk.Button(action_frame, text="⚡ Enable Auto-Censor for Stremio", bg="#6366f1", fg="white", font=("Segoe UI", 11, "bold"), command=self.toggle_stremio_watcher)
        self.toggle_btn.pack(side="right", padx=10)

        # Instructions / How to Use Card
        info_frame = ctk.CTkFrame(self) if HAS_CTK else tk.LabelFrame(self, text="How Stremio Integration Works", padx=15, pady=15)
        info_frame.pack(fill="both", expand=True, padx=15, pady=10)

        instructions = (
            "🚀 How to Use AutoCensor AI with Stremio:\n\n"
            "Method 1: Automatic Stremio Cache Watcher (Easiest)\n"
            "1. Click '⚡ Enable Auto-Censor for Stremio' above.\n"
            "2. Open Stremio and play any episode or movie normally.\n"
            "3. AutoCensor AI automatically detects the streaming episode in Stremio's cache, censors subtitles & audio, and saves clean files.\n\n"
            "Method 2: External Player Launcher\n"
            "1. In Stremio Settings -> Playback -> Set 'Play in external player' to Always.\n"
            "2. Whenever you click an episode in Stremio, select AutoCensor AI to automatically censor audio & subtitles before playing!"
        )

        txt_widget = tk.Text(info_frame, bg="#1e293b", fg="#f8fafc", font=("Consolas", 10), wrap="word", relief="flat")
        txt_widget.insert("1.0", instructions)
        txt_widget.configure(state="disabled")
        txt_widget.pack(fill="both", expand=True, padx=5, pady=5)

    def toggle_stremio_watcher(self):
        if self.watcher and self.watcher.is_running:
            self.watcher.stop()
            self.watcher = None
            self.status_lbl.configure(text="● STREMIO WATCHER STOPPED", text_color="#ef4444" if HAS_CTK else None)
            self.toggle_btn.configure(text="⚡ Enable Auto-Censor for Stremio", fg_color="#6366f1" if HAS_CTK else None)
        else:
            cache_dir = get_stremio_cache_dir()
            if not cache_dir or not cache_dir.exists():
                messagebox.showwarning("Stremio Cache Missing", "Stremio cache directory was not found. Please launch Stremio and play a stream first.")
                return

            def on_stremio_file(file_path: Path):
                try:
                    res = self.processor.process(video_path=file_path)
                    logger.info(f"Stremio episode censored: {file_path.name} -> {Path(res['output_video']).name}")
                except Exception as e:
                    logger.error(f"Failed censoring Stremio episode: {e}")

            self.watcher = WatcherService(watch_dir=cache_dir, callback=on_stremio_file)
            self.watcher.start()

            self.status_lbl.configure(text="● STREMIO WATCHER ACTIVE", text_color="#10b981" if HAS_CTK else None)
            self.toggle_btn.configure(text="Stop Stremio Auto-Censor", fg_color="#ef4444" if HAS_CTK else None)
