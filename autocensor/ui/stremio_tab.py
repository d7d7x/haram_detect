import os
import sys
import subprocess
import time
import threading
import tkinter as tk
from tkinter import ttk, messagebox
import logging
from pathlib import Path
from autocensor.core.dictionary import CensorshipDictionary
from autocensor.core.watcher import WatcherService
from autocensor.core.media_processor import MediaProcessor
from autocensor.utils.stremio_utils import get_stremio_cache_dir, find_external_player, get_active_stremio_stream_info

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
        self.is_polling = True
        self.create_widgets()
        self.start_api_poller()

    def create_widgets(self):
        # Header Info Card
        card = ctk.CTkFrame(self) if HAS_CTK else tk.LabelFrame(self, text="Stremio Integration Status", padx=15, pady=15)
        card.pack(fill="x", padx=15, pady=15)

        cache_dir = get_stremio_cache_dir()
        player_path = find_external_player()

        # Cache Path Status
        c_status = f"✓ {cache_dir}" if cache_dir else "⚠ Not detected"
        c_color = "#10b981" if cache_dir else "#f59e0b"

        self.c_lbl = ctk.CTkLabel(card, text=f"Stremio Cache Folder: {c_status}", font=("Segoe UI", 12, "bold"), text_color=c_color) if HAS_CTK else tk.Label(card, text=f"Stremio Cache Folder: {c_status}", fg=c_color, font=("Segoe UI", 10, "bold"))
        self.c_lbl.pack(anchor="w", pady=4)

        # Active Server & Stream Detector Status
        self.stream_lbl = ctk.CTkLabel(card, text="Stremio Streaming Server (http://127.0.0.1:11470): ONLINE | No stream active", font=("Segoe UI", 12), text_color="#64748b") if HAS_CTK else tk.Label(card, text="Stremio Streaming Server: ONLINE | No stream active", fg="#64748b", font=("Segoe UI", 10))
        self.stream_lbl.pack(anchor="w", pady=4)

        # External Player Status
        p_status = f"✓ Found Player: {player_path.name}" if player_path else "⚠ OS Default Player"
        p_color = "#10b981" if player_path else "#94a3b8"

        p_lbl = ctk.CTkLabel(card, text=f"Playback Engine: {p_status}", font=("Segoe UI", 11), text_color=p_color) if HAS_CTK else tk.Label(card, text=f"Playback Engine: {p_status}", fg=p_color, font=("Segoe UI", 9))
        p_lbl.pack(anchor="w", pady=4)

        # Solution Selection Frame
        sol_frame = ctk.CTkFrame(self) if HAS_CTK else tk.LabelFrame(self, text="Engine Solution Selection", padx=10, pady=5)
        sol_frame.pack(fill="x", padx=15, pady=5)

        s_lbl = ctk.CTkLabel(sol_frame, text="Active Engine Solution:") if HAS_CTK else tk.Label(sol_frame, text="Active Engine Solution:")
        s_lbl.pack(side="left", padx=10)

        self.solution_var = tk.StringVar(value="solution_1")
        if HAS_CTK:
            ctk.CTkRadioButton(sol_frame, text="⚡ Solution 1: Live In-Place Engine (Instant Playback)", variable=self.solution_var, value="solution_1").pack(side="left", padx=10)
            ctk.CTkRadioButton(sol_frame, text="🎬 Solution 2: Full FFmpeg Re-Muxing Engine (Permanent Video File)", variable=self.solution_var, value="solution_2").pack(side="left", padx=10)
        else:
            tk.Radiobutton(sol_frame, text="⚡ Solution 1: Live In-Place Engine", variable=self.solution_var, value="solution_1").pack(side="left", padx=10)
            tk.Radiobutton(sol_frame, text="🎬 Solution 2: Full FFmpeg Re-Muxing Engine", variable=self.solution_var, value="solution_2").pack(side="left", padx=10)

        # Toggle Button Bar
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

        # Live Activity Log View
        log_frame = ctk.CTkFrame(self) if HAS_CTK else tk.LabelFrame(self, text="Stremio Live Stream Monitor Log", padx=5, pady=5)
        log_frame.pack(fill="both", expand=True, padx=15, pady=10)

        self.log_list = tk.Listbox(log_frame, bg="#1e293b", fg="#f8fafc", font=("Consolas", 10), selectbackground="#334155")
        log_scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_list.yview)
        self.log_list.configure(yscrollcommand=log_scroll.set)

        self.log_list.pack(side="left", fill="both", expand=True)
        log_scroll.pack(side="right", fill="y")

        self.log("Stremio Live API & Cache Monitor initialized.")

    def log(self, text: str):
        def _add():
            self.log_list.insert(tk.END, text)
            self.log_list.see(tk.END)
        self.after(0, _add)

    def start_api_poller(self):
        """Background thread polling Stremio API http://127.0.0.1:11470."""
        def poll_loop():
            last_stream_name = None
            while self.is_polling:
                info = get_active_stremio_stream_info()
                if info and info.get("name"):
                    stream_name = info["name"]
                    if stream_name != last_stream_name:
                        last_stream_name = stream_name
                        self.after(0, lambda name=stream_name: self.stream_lbl.configure(
                            text=f"🎬 Currently Playing in Stremio: {name}",
                            text_color="#10b981" if HAS_CTK else None
                        ))
                        self.log(f"[STREMIO API DETECTED] Playing Episode: {stream_name}")
                else:
                    if last_stream_name is not None:
                        last_stream_name = None
                        self.after(0, lambda: self.stream_lbl.configure(
                            text="Stremio Streaming Server: ONLINE | Standby (No active episode streaming)",
                            text_color="#94a3b8" if HAS_CTK else None
                        ))
                time.sleep(3)

        threading.Thread(target=poll_loop, daemon=True).start()

    def toggle_stremio_watcher(self):
        if self.watcher and self.watcher.is_running:
            self.watcher.stop()
            self.watcher = None
            self.status_lbl.configure(text="● STREMIO WATCHER STOPPED", text_color="#ef4444" if HAS_CTK else None)
            self.toggle_btn.configure(text="⚡ Enable Auto-Censor for Stremio", fg_color="#6366f1" if HAS_CTK else None)
            self.log("Stremio Auto-Censor Watcher stopped.")
        else:
            cache_dir = get_stremio_cache_dir()
            if not cache_dir:
                messagebox.showwarning("Stremio Cache Missing", "Stremio cache directory was not found. Please launch Stremio and play a stream first.")
                return

            from autocensor.core.live_subtitle_modifier import LiveSubtitleModifier
            from autocensor.core.live_audio_bleeper import LiveAudioBleeper

            live_sub_modifier = LiveSubtitleModifier(self.dictionary)
            live_bleeper = LiveAudioBleeper()

            def on_stremio_file(file_path: Path):
                selected_solution = self.solution_var.get()
                self.log(f"[STREMIO DETECTED] File: {file_path.name} (Active Solution: {selected_solution.upper()})")

                if selected_solution == "solution_1":
                    # Solution 1: Live In-Place Subtitle & Real-time Audio Bleep Engine
                    if file_path.suffix.lower() in [".srt", ".vtt", ".ass"]:
                        success = live_sub_modifier.process_subtitle_in_place(file_path)
                        if success:
                            self.log(f"[SOLUTION 1 IN-PLACE CLEANED] Modified {file_path.name} directly in Stremio cache!")
                            items = self.processor.sub_engine.parse_subtitle(file_path)
                            timestamps = [(it.start_sec, it.end_sec) for it in items if self.dictionary.find_matches(it.text)]
                            if timestamps:
                                live_bleeper.schedule_bleeps_for_timestamps(timestamps)
                        return
                    elif file_path.suffix.lower() in [".mp4", ".mkv", ".avi"]:
                        # Extract embedded subtitle or check for existing subtitle file
                        extracted_srt = live_sub_modifier.extract_and_clean_embedded_subtitle(file_path)
                        target_sub = extracted_srt or file_path.with_suffix(".srt")

                        if target_sub.exists():
                            items = self.processor.sub_engine.parse_subtitle(target_sub)
                            timestamps = [(it.start_sec, it.end_sec) for it in items if self.dictionary.find_matches(it.text)]
                            if timestamps:
                                self.log(f"[LIVE BLEEP SCHEDULED] Scheduled {len(timestamps)} (طوط) audio bleeps for {file_path.name}")
                                live_bleeper.schedule_bleeps_for_timestamps(timestamps)

                else:
                    # Solution 2: Full FFmpeg Video Re-Muxing Engine (Previous Solution)
                    if file_path.suffix.lower() in [".mp4", ".mkv", ".avi"]:
                        try:
                            res = self.processor.process(
                                video_path=file_path,
                                progress_callback=lambda pct, txt: self.log(f"[{file_path.name}] {txt}")
                            )
                            out_vid = Path(res['output_video'])
                            self.log(f"[SOLUTION 2 SUCCESS] Permanent Censored Video Saved -> {out_vid.name}")
                        except Exception as e:
                            self.log(f"[SOLUTION 2 ERROR] Re-muxing error: {e}")

            self.watcher = WatcherService(watch_dir=cache_dir, callback=on_stremio_file)
            self.watcher.start()

            self.status_lbl.configure(text="● STREMIO WATCHER ACTIVE", text_color="#10b981" if HAS_CTK else None)
            self.toggle_btn.configure(text="Stop Stremio Auto-Censor", fg_color="#ef4444" if HAS_CTK else None)
            self.log(f"Monitoring Stremio cache directory: {cache_dir}")

    def destroy(self):
        self.is_polling = False
        if self.watcher:
            self.watcher.stop()
        super().destroy()
