import os
import sys
import time
import uuid
import threading
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import logging
from pathlib import Path

from autocensor.core.dictionary import CensorshipDictionary
from autocensor.core.watcher import WatcherService
from autocensor.core.media_processor import MediaProcessor
from autocensor.core.mpv_ipc_controller import MPVIPCController
from autocensor.utils.stremio_utils import (
    get_stremio_cache_dir,
    find_mpv_executable,
    find_external_player,
    get_active_stremio_stream_info
)

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
        # Top Header & Status Card
        card = ctk.CTkFrame(self) if HAS_CTK else tk.LabelFrame(self, text="Stremio Integration Status", padx=15, pady=15)
        card.pack(fill="x", padx=15, pady=10)

        cache_dir = get_stremio_cache_dir()
        mpv_path = find_mpv_executable()

        c_status = f"✓ {cache_dir}" if cache_dir else "⚠ Not detected"
        c_color = "#10b981" if cache_dir else "#f59e0b"

        self.c_lbl = ctk.CTkLabel(card, text=f"Stremio Cache Folder: {c_status}", font=("Segoe UI", 12, "bold"), text_color=c_color) if HAS_CTK else tk.Label(card, text=f"Stremio Cache Folder: {c_status}", fg=c_color, font=("Segoe UI", 10, "bold"))
        self.c_lbl.pack(anchor="w", pady=2)

        self.stream_lbl = ctk.CTkLabel(card, text="Stremio Streaming Server (http://127.0.0.1:11470): ONLINE | Standby", font=("Segoe UI", 12), text_color="#64748b") if HAS_CTK else tk.Label(card, text="Stremio Streaming Server: ONLINE | Standby", fg="#64748b", font=("Segoe UI", 10))
        self.stream_lbl.pack(anchor="w", pady=2)

        p_status = f"✓ MPV Found: {mpv_path.name}" if mpv_path else "⚠ MPV Not Found in standard paths"
        p_color = "#10b981" if mpv_path else "#ef4444"
        self.p_lbl = ctk.CTkLabel(card, text=f"MPV Executable: {p_status}", font=("Segoe UI", 11), text_color=p_color) if HAS_CTK else tk.Label(card, text=f"MPV Executable: {p_status}", fg=p_color, font=("Segoe UI", 9))
        self.p_lbl.pack(anchor="w", pady=2)

        # Direct Stream Link / Magnet Launcher Section (New User Request)
        link_card = ctk.CTkFrame(self) if HAS_CTK else tk.LabelFrame(self, text="Paste Stremio Stream Link or Magnet", padx=10, pady=10)
        link_card.pack(fill="x", padx=15, pady=5)

        link_top_row = ctk.CTkFrame(link_card) if HAS_CTK else tk.Frame(link_card)
        link_top_row.pack(fill="x", pady=2)

        s_lbl = ctk.CTkLabel(link_top_row, text="Paste Stream Link:", font=("Segoe UI", 11, "bold")) if HAS_CTK else tk.Label(link_top_row, text="Paste Stream Link:", font=("Segoe UI", 9, "bold"))
        s_lbl.pack(side="left", padx=5)

        self.stream_url_var = tk.StringVar()
        if HAS_CTK:
            self.stream_url_entry = ctk.CTkEntry(link_top_row, textvariable=self.stream_url_var, placeholder_text="Paste copied Stremio stream link or magnet link here...", width=360)
            self.stream_url_entry.pack(side="left", padx=5, fill="x", expand=True)

            paste_btn = ctk.CTkButton(link_top_row, text="📋 Paste", width=80, command=self.paste_stream_url)
            paste_btn.pack(side="left", padx=4)

            play_stream_btn = ctk.CTkButton(link_top_row, text="🎬 Play & Censor Stream", fg_color="#10b981", hover_color="#059669", font=("Segoe UI", 12, "bold"), width=160, command=self.play_pasted_stream)
            play_stream_btn.pack(side="left", padx=4)
        else:
            self.stream_url_entry = tk.Entry(link_top_row, textvariable=self.stream_url_var, width=40)
            self.stream_url_entry.pack(side="left", padx=5, fill="x", expand=True)

            paste_btn = tk.Button(link_top_row, text="📋 Paste", command=self.paste_stream_url)
            paste_btn.pack(side="left", padx=4)

            play_stream_btn = tk.Button(link_top_row, text="🎬 Play & Censor Stream", bg="#10b981", fg="white", font=("Segoe UI", 10, "bold"), command=self.play_pasted_stream)
            play_stream_btn.pack(side="left", padx=4)

        # MPV Path & IPC Test Configuration Box
        cfg_frame = ctk.CTkFrame(self) if HAS_CTK else tk.LabelFrame(self, text="MPV IPC Engine Configuration", padx=10, pady=10)
        cfg_frame.pack(fill="x", padx=15, pady=5)

        # Row 1: Executable Selector
        path_row = ctk.CTkFrame(cfg_frame) if HAS_CTK else tk.Frame(cfg_frame)
        path_row.pack(fill="x", pady=4)

        mpv_lbl = ctk.CTkLabel(path_row, text="MPV Executable Path:", font=("Segoe UI", 11, "bold")) if HAS_CTK else tk.Label(path_row, text="MPV Path:", font=("Segoe UI", 9, "bold"))
        mpv_lbl.pack(side="left", padx=5)

        self.mpv_path_var = tk.StringVar(value=str(mpv_path) if mpv_path else "")
        if HAS_CTK:
            self.mpv_entry = ctk.CTkEntry(path_row, textvariable=self.mpv_path_var, width=320)
            self.mpv_entry.pack(side="left", padx=5, fill="x", expand=True)

            browse_btn = ctk.CTkButton(path_row, text="Browse...", width=80, command=self.browse_mpv_path)
            browse_btn.pack(side="left", padx=4)

            test_btn = ctk.CTkButton(path_row, text="🧪 Test MPV Connection", fg_color="#10b981", hover_color="#059669", width=140, command=self.test_mpv_ipc)
            test_btn.pack(side="left", padx=4)
        else:
            self.mpv_entry = tk.Entry(path_row, textvariable=self.mpv_path_var, width=35)
            self.mpv_entry.pack(side="left", padx=5, fill="x", expand=True)

            browse_btn = tk.Button(path_row, text="Browse...", command=self.browse_mpv_path)
            browse_btn.pack(side="left", padx=4)

            test_btn = tk.Button(path_row, text="🧪 Test MPV", command=self.test_mpv_ipc)
            test_btn.pack(side="left", padx=4)

        # Row 2: Action Options
        act_row = ctk.CTkFrame(cfg_frame) if HAS_CTK else tk.Frame(cfg_frame)
        act_row.pack(fill="x", pady=4)

        mode_lbl = ctk.CTkLabel(act_row, text="Censorship Action:", font=("Segoe UI", 11, "bold")) if HAS_CTK else tk.Label(act_row, text="Action:", font=("Segoe UI", 9, "bold"))
        mode_lbl.pack(side="left", padx=5)

        self.action_var = tk.StringVar(value="delete_mute")
        if HAS_CTK:
            ctk.CTkRadioButton(act_row, text="⚡ Delete Forbidden Words + IPC Audio Mute (Recommended)", variable=self.action_var, value="delete_mute").pack(side="left", padx=10)
            ctk.CTkRadioButton(act_row, text="🔊 Fallback Legacy Beep Mode", variable=self.action_var, value="legacy_beep").pack(side="left", padx=10)
        else:
            tk.Radiobutton(act_row, text="⚡ Delete Words + Mute Audio", variable=self.action_var, value="delete_mute").pack(side="left", padx=10)
            tk.Radiobutton(act_row, text="🔊 Legacy Beep Mode", variable=self.action_var, value="legacy_beep").pack(side="left", padx=10)

        # Toggle Button Bar
        action_frame = ctk.CTkFrame(self) if HAS_CTK else tk.Frame(self)
        action_frame.pack(fill="x", padx=15, pady=8)

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
        log_frame = ctk.CTkFrame(self) if HAS_CTK else tk.LabelFrame(self, text="Stremio Live MPV Monitor Log", padx=5, pady=5)
        log_frame.pack(fill="both", expand=True, padx=15, pady=10)

        self.log_list = tk.Listbox(log_frame, bg="#1e293b", fg="#f8fafc", font=("Consolas", 10), selectbackground="#334155")
        log_scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_list.yview)
        self.log_list.configure(yscrollcommand=log_scroll.set)

        self.log_list.pack(side="left", fill="both", expand=True)
        log_scroll.pack(side="right", fill="y")

        self.log("AutoCensor MPV IPC Stremio Controller ready.")

    def log(self, text: str):
        def _add():
            self.log_list.insert(tk.END, text)
            self.log_list.see(tk.END)
        self.after(0, _add)

    def paste_stream_url(self):
        """Paste clipboard content into stream link field."""
        try:
            clipboard_text = self.clipboard_get()
            if clipboard_text:
                self.stream_url_var.set(clipboard_text.strip())
                self.log("Pasted stream link from clipboard into launcher field.")
        except Exception as e:
            self.log(f"Clipboard read notice: {e}")

    def play_pasted_stream(self):
        """Launch MPV IPC stream for the pasted URL/magnet link."""
        url = self.stream_url_var.get().strip()
        if not url:
            messagebox.showwarning("Missing Stream Link", "Please paste a copied Stremio stream link or magnet link first.")
            return

        mpv_exe = self.mpv_path_var.get().strip() or None
        self.log(f"Launching live MPV IPC censorship for pasted link...")
        from autocensor.stremio_proxy import handle_stremio_stream
        threading.Thread(
            target=handle_stremio_stream,
            args=(url, mpv_exe),
            daemon=True
        ).start()

    def browse_mpv_path(self):
        filename = filedialog.askopenfilename(
            title="Select MPV Executable",
            filetypes=[("Executable Files", "*.exe"), ("All Files", "*.*")]
        )
        if filename:
            self.mpv_path_var.set(filename)
            self.p_lbl.configure(text=f"✓ MPV Path Selected: {Path(filename).name}", text_color="#10b981" if HAS_CTK else None)

    def test_mpv_ipc(self):
        """Test MPV IPC connection by launching a test MPV instance."""
        mpv_path = self.mpv_path_var.get().strip()
        if not mpv_path or not Path(mpv_path).exists():
            messagebox.showerror("MPV Not Found", "Please select a valid mpv.exe executable path first.")
            return

        def _run_test():
            self.log("Testing MPV JSON IPC named pipe connection...")
            pipe_name = f"autocensor_test_pipe_{uuid.uuid4().hex[:6]}"
            cmd = [
                mpv_path,
                "--idle",
                f"--input-ipc-server=\\\\.\\pipe\\{pipe_name}",
                "--no-terminal"
            ]
            try:
                proc = subprocess.Popen(cmd)
                ipc = MPVIPCController(pipe_name=pipe_name)
                connected = ipc.connect(timeout=6.0)
                if connected:
                    time_pos = ipc.get_time_pos()
                    ipc.mute(True)
                    time.sleep(0.5)
                    ipc.mute(False)
                    ipc.send_command("quit")
                    proc.wait(timeout=3.0)
                    self.log("✅ MPV IPC Connection Test PASSED successfully!")
                    self.after(0, lambda: messagebox.showinfo("IPC Test Success", "MPV JSON IPC named pipe connected and responded successfully!"))
                else:
                    self.log("❌ MPV IPC Test FAILED: Pipe connection timed out.")
                    if proc.poll() is None:
                        proc.kill()
                    self.after(0, lambda: messagebox.showerror("IPC Test Failed", "Could not connect to MPV IPC pipe."))
            except Exception as e:
                self.log(f"❌ MPV IPC Test Error: {e}")
                self.after(0, lambda: messagebox.showerror("IPC Test Error", str(e)))

        threading.Thread(target=_run_test, daemon=True).start()

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
                            text="Stremio Streaming Server: ONLINE | Standby",
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

            def on_stremio_file(file_path: Path):
                self.log(f"[STREMIO CACHE DETECTED] File: {file_path.name}")
                if file_path.suffix.lower() in [".mp4", ".mkv", ".avi", ".srt", ".vtt", ".ass"]:
                    mpv_exe = self.mpv_path_var.get().strip() or None
                    from autocensor.stremio_proxy import handle_stremio_stream
                    threading.Thread(
                        target=handle_stremio_stream,
                        args=(str(file_path), mpv_exe),
                        daemon=True
                    ).start()

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
