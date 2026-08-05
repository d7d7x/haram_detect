import os
import sys
import time
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import logging
from pathlib import Path

from autocensor import __version__
from autocensor.config import THEME, DATA_DIR
from autocensor.core.dictionary import CensorshipDictionary
from autocensor.core.media_processor import MediaProcessor
from autocensor.core.live_subtitle_modifier import LiveSubtitleModifier
from autocensor.core.live_audio_bleeper import LiveAudioBleeper
from autocensor.core.watcher import WatcherService
from autocensor.utils.stremio_utils import get_stremio_cache_dir, get_active_stremio_stream_info
from autocensor.utils.ffmpeg_utils import is_ffmpeg_available

logger = logging.getLogger(__name__)

try:
    import customtkinter as ctk
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    HAS_CTK = True
except ImportError:
    HAS_CTK = False

class AutoCensorApp(ctk.CTk if HAS_CTK else tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("AutoCensor AI - Direct Stremio Censorship Engine")
        self.geometry("860x660")
        self.minsize(820, 580)

        # Initialize Core Engines
        self.dictionary = CensorshipDictionary()
        self.processor = MediaProcessor(self.dictionary)
        self.live_sub_modifier = LiveSubtitleModifier(self.dictionary)
        self.live_bleeper = LiveAudioBleeper()
        self.watcher: WatcherService = None
        self.is_polling = True

        # Window Icon
        icon_ico = DATA_DIR / "app_icon.ico"
        if icon_ico.exists():
            try:
                self.iconbitmap(str(icon_ico))
            except Exception:
                pass

        self.create_header()
        self.create_main_hero()
        self.create_mode_selection_buttons()
        self.create_activity_log()
        self.create_statusbar()

        # Start live Stremio API poller
        self.start_stremio_api_poller()

        # Auto-start watcher on launch
        self.after(500, self.auto_start_watcher)

    def create_header(self):
        header_frame = ctk.CTkFrame(self, fg_color=THEME["surface"]) if HAS_CTK else tk.Frame(self, bg="#1e293b")
        header_frame.pack(fill="x", padx=0, pady=0)

        text_frame = ctk.CTkFrame(header_frame, fg_color="transparent") if HAS_CTK else tk.Frame(header_frame, bg="#1e293b")
        text_frame.pack(side="left", padx=20, pady=12)

        title_lbl = ctk.CTkLabel(
            text_frame, text="⚡ AutoCensor AI",
            font=("Segoe UI", 22, "bold"), text_color=THEME["text_primary"]
        ) if HAS_CTK else tk.Label(text_frame, text="⚡ AutoCensor AI", font=("Segoe UI", 18, "bold"), fg="#f8fafc", bg="#1e293b")
        title_lbl.pack(anchor="w")

        sub_lbl = ctk.CTkLabel(
            text_frame, text="Direct In-Place Subtitle Censorship for Stremio & Downloads",
            font=("Segoe UI", 11), text_color=THEME["text_secondary"]
        ) if HAS_CTK else tk.Label(text_frame, text="Direct In-Place Subtitle Censorship for Stremio & Downloads", font=("Segoe UI", 9), fg="#94a3b8", bg="#1e293b")
        sub_lbl.pack(anchor="w")

        ver_lbl = ctk.CTkLabel(
            header_frame, text=f"v{__version__}",
            fg_color=THEME["primary"], corner_radius=12, text_color="white",
            font=("Segoe UI", 11, "bold"), width=60, height=24
        ) if HAS_CTK else tk.Label(header_frame, text=f"v{__version__}", bg="#6366f1", fg="white", font=("Segoe UI", 9, "bold"))
        ver_lbl.pack(side="right", padx=20)

    def create_main_hero(self):
        hero_card = ctk.CTkFrame(self, fg_color=THEME["surface"], corner_radius=15) if HAS_CTK else tk.LabelFrame(self, text="Main Control", padx=20, pady=20)
        hero_card.pack(fill="x", padx=20, pady=10)

        self.status_lbl = ctk.CTkLabel(
            hero_card, text="🟢 AUTO-CENSOR ACTIVE (MONITORING STREMIO)",
            font=("Segoe UI", 14, "bold"), text_color="#10b981"
        ) if HAS_CTK else tk.Label(hero_card, text="🟢 AUTO-CENSOR ACTIVE (MONITORING STREMIO)", fg="#10b981", font=("Segoe UI", 12, "bold"))
        self.status_lbl.pack(pady=(10, 2))

        self.episode_lbl = ctk.CTkLabel(
            hero_card, text="🎬 Stremio Status: Standby (Play any episode in Stremio)",
            font=("Segoe UI", 12), text_color="#94a3b8"
        ) if HAS_CTK else tk.Label(hero_card, text="🎬 Stremio Status: Standby (Play any episode in Stremio)", fg="#94a3b8", font=("Segoe UI", 10))
        self.episode_lbl.pack(pady=(0, 10))

    def create_mode_selection_buttons(self):
        """Displays 2 clickable mode selection buttons so the user can easily pick."""
        mode_card = ctk.CTkFrame(self, fg_color=THEME["surface"], corner_radius=12) if HAS_CTK else tk.LabelFrame(self, text="Select Censorship Mode", padx=15, pady=10)
        mode_card.pack(fill="x", padx=20, pady=(0, 10))

        t_lbl = ctk.CTkLabel(mode_card, text="👇 Click to Choose Your Mode:", font=("Segoe UI", 12, "bold"), text_color="#10b981") if HAS_CTK else tk.Label(mode_card, text="👇 Click to Choose Your Mode:", font=("Segoe UI", 10, "bold"), fg="#10b981", bg="#1e293b")
        t_lbl.pack(anchor="w", padx=5, pady=(4, 6))

        btn_row = ctk.CTkFrame(mode_card, fg_color="transparent") if HAS_CTK else tk.Frame(mode_card, bg="#1e293b")
        btn_row.pack(fill="x", padx=5, pady=4)

        self.m1_btn = ctk.CTkButton(
            btn_row, text="⚡ Mode 1: Live Stremio Watcher\n(Watch live in Stremio)",
            fg_color="#10b981", hover_color="#059669",
            font=("Segoe UI", 12, "bold"), height=52, width=380,
            command=self.select_mode_1_live
        ) if HAS_CTK else tk.Button(btn_row, text="⚡ Mode 1: Live Stremio Watcher", bg="#10b981", fg="white", font=("Segoe UI", 10, "bold"), command=self.select_mode_1_live)
        self.m1_btn.pack(side="left", padx=5, expand=True, fill="x")

        self.m2_btn = ctk.CTkButton(
            btn_row, text="🎬 Mode 2: Download & Process Video\n(Full Audio Muting + Clean Video)",
            fg_color="#6366f1", hover_color="#4f46e5",
            font=("Segoe UI", 12, "bold"), height=52, width=380,
            command=self.select_mode_2_offline
        ) if HAS_CTK else tk.Button(btn_row, text="🎬 Mode 2: Download & Process Video", bg="#6366f1", fg="white", font=("Segoe UI", 10, "bold"), command=self.select_mode_2_offline)
        self.m2_btn.pack(side="right", padx=5, expand=True, fill="x")

    def select_mode_1_live(self):
        """Activates Live Stremio Watcher Mode."""
        self.toggle_master_watcher(start_only=True)
        self.log("✅ [MODE 1 SELECTED] Live Stremio Watcher active! Go to Stremio -> Click 💬 -> Select 2nd English or Arabic subtitle.")
        messagebox.showinfo(
            "Mode 1 Active",
            "Mode 1 (Live Stremio Watcher) is now active!\n\n"
            "Steps in Stremio:\n"
            "1. Play your video in Stremio.\n"
            "2. Click the Subtitle icon (💬).\n"
            "3. Pick the 2nd 'English' or 'Arabic' subtitle.\n"
            "4. AutoCensor will delete forbidden words live!"
        )

    def select_mode_2_offline(self):
        """Pick a video file for full offline censorship (subtitles + audio muting)."""
        filename = filedialog.askopenfilename(
            title="Select Video File to Censor (from Stremio Download or PC)",
            filetypes=[("Video Files", "*.mp4 *.mkv *.avi *.mov"), ("All Files", "*.*")]
        )
        if filename:
            video_p = Path(filename)
            self.log(f"🎬 [MODE 2 SELECTED] Processing video file for full audio muting & subtitle censorship: {video_p.name}")
            def _process_bg():
                try:
                    res = self.processor.process(
                        video_path=video_p,
                        progress_callback=lambda pct, txt: self.log(f"[{int(pct*100)}%] {txt}")
                    )
                    out_v = res.get("output_video", "")
                    self.log(f"🎉 SUCCESS! Censored video created: {Path(out_v).name}")
                    self.after(0, lambda: messagebox.showinfo("Censorship Complete", f"Successfully created censored video file:\n{out_v}"))
                except Exception as e:
                    self.log(f"❌ Error processing file: {e}")
                    self.after(0, lambda: messagebox.showerror("Processing Error", str(e)))

            threading.Thread(target=_process_bg, daemon=True).start()

    def create_activity_log(self):
        log_card = ctk.CTkFrame(self, fg_color=THEME["surface"]) if HAS_CTK else tk.LabelFrame(self, text="Live Activity Log", padx=10, pady=10)
        log_card.pack(fill="both", expand=True, padx=20, pady=(0, 10))

        lbl = ctk.CTkLabel(log_card, text="📋 Live Activity Log:", font=("Segoe UI", 11, "bold"), text_color="#94a3b8") if HAS_CTK else tk.Label(log_card, text="📋 Live Activity Log:", font=("Segoe UI", 9, "bold"))
        lbl.pack(anchor="w", padx=10, pady=(5, 2))

        self.log_list = tk.Listbox(log_card, bg="#0f172a", fg="#f8fafc", font=("Consolas", 10), selectbackground="#334155", bd=0, highlightthickness=0)
        log_scroll = ttk.Scrollbar(log_card, orient="vertical", command=self.log_list.yview)
        self.log_list.configure(yscrollcommand=log_scroll.set)

        self.log_list.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=5)
        log_scroll.pack(side="right", fill="y", padx=(0, 10), pady=5)

        self.log("⚡ AutoCensor AI ready. Click Mode 1 or Mode 2 above!")

    def create_statusbar(self):
        sb_frame = ctk.CTkFrame(self, height=28, fg_color=THEME["surface_light"]) if HAS_CTK else tk.Frame(self, bg="#334155", height=24)
        sb_frame.pack(fill="x", side="bottom")

        ffmpeg_ok = is_ffmpeg_available()
        status_text = f"FFmpeg: {'OK ✓' if ffmpeg_ok else 'MISSING ✗'}  |  Shirk & Polytheism Dictionary: {len(self.dictionary.terms)} terms loaded"

        lbl = ctk.CTkLabel(sb_frame, text=status_text, font=("Segoe UI", 10), text_color="#cbd5e1") if HAS_CTK else tk.Label(sb_frame, text=status_text, font=("Segoe UI", 9), fg="#cbd5e1", bg="#334155")
        lbl.pack(side="left", padx=15)

    def log(self, text: str):
        def _add():
            self.log_list.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {text}")
            self.log_list.see(tk.END)
        self.after(0, _add)

    def auto_start_watcher(self):
        if not self.watcher or not self.watcher.is_running:
            self.toggle_master_watcher(start_only=True)

    def toggle_master_watcher(self, start_only=False):
        if self.watcher and self.watcher.is_running and not start_only:
            self.watcher.stop()
            self.watcher = None
            if HAS_CTK:
                self.status_lbl.configure(text="🔴 AUTO-CENSOR STOPPED", text_color="#ef4444")
            else:
                self.status_lbl.configure(text="🔴 AUTO-CENSOR STOPPED", fg="#ef4444")
            self.log("Auto-Censor service stopped.")
        else:
            cache_dir = get_stremio_cache_dir()
            if not cache_dir:
                messagebox.showwarning("Notice", "Stremio cache directory not found. Standard file watcher will run.")
                cache_dir = Path.home() / "Downloads"

            def on_media_file(file_path: Path):
                self.log(f"[DETECTED] {file_path.name}")
                
                # In-place Subtitle Modification for Stremio Cache
                if file_path.suffix.lower() in [".srt", ".vtt", ".ass"]:
                    success = self.live_sub_modifier.process_subtitle_in_place(file_path)
                    if success:
                        self.log(f"[CLEANED IN STREMIO] Removed forbidden terms from {file_path.name}!")
                    return

                # Embedded Subtitle Extraction for Video Files
                if file_path.suffix.lower() in [".mp4", ".mkv", ".avi"]:
                    extracted_srt = self.live_sub_modifier.extract_and_clean_embedded_subtitle(file_path)
                    if extracted_srt and extracted_srt.exists():
                        self.log(f"[CLEANED EMBEDDED SUBTITLE] Extracted and cleaned {extracted_srt.name}")

            self.watcher = WatcherService(watch_dir=cache_dir, callback=on_media_file)
            self.watcher.start()

            if HAS_CTK:
                self.status_lbl.configure(text="🟢 AUTO-CENSOR ACTIVE (MONITORING STREMIO)", text_color="#10b981")
            else:
                self.status_lbl.configure(text="🟢 AUTO-CENSOR ACTIVE (MONITORING STREMIO)", fg="#10b981")
            
            self.log(f"Monitoring active on Stremio cache: {cache_dir}")

    def start_stremio_api_poller(self):
        def poll_loop():
            last_stream_name = None
            while self.is_polling:
                info = get_active_stremio_stream_info()
                if info and info.get("name"):
                    name = info["name"]
                    if name != last_stream_name:
                        last_stream_name = name
                        self.after(0, lambda n=name: self.episode_lbl.configure(
                            text=f"🎬 Currently Playing in Stremio: {n}",
                            text_color="#10b981" if HAS_CTK else None
                        ))
                        self.log(f"[STREMIO PLAYING] {name}")
                else:
                    if last_stream_name is not None:
                        last_stream_name = None
                        self.after(0, lambda: self.episode_lbl.configure(
                            text="🎬 Stremio Status: Standby (Play any episode in Stremio)",
                            text_color="#94a3b8" if HAS_CTK else None
                        ))
                time.sleep(3)

        threading.Thread(target=poll_loop, daemon=True).start()

    def destroy(self):
        self.is_polling = False
        if self.watcher:
            self.watcher.stop()
        super().destroy()
