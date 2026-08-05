import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import logging
from pathlib import Path
from autocensor.core.dictionary import CensorshipDictionary
from autocensor.core.watcher import WatcherService
from autocensor.core.media_processor import MediaProcessor

logger = logging.getLogger(__name__)

try:
    import customtkinter as ctk
    HAS_CTK = True
except ImportError:
    HAS_CTK = False

class WatcherTabFrame(ctk.CTkFrame if HAS_CTK else tk.Frame):
    def __init__(self, master, dictionary: CensorshipDictionary):
        super().__init__(master)
        self.dictionary = dictionary
        self.processor = MediaProcessor(dictionary)
        self.watcher: WatcherService = None
        self.create_widgets()

    def create_widgets(self):
        # Watcher Configuration Frame
        config_frame = ctk.CTkFrame(self) if HAS_CTK else tk.LabelFrame(self, text="Folder Watcher Configuration", padx=10, pady=10)
        config_frame.pack(fill="x", padx=15, pady=10)

        folder_lbl = ctk.CTkLabel(config_frame, text="Monitored Directory:") if HAS_CTK else tk.Label(config_frame, text="Monitored Directory:")
        folder_lbl.grid(row=0, column=0, sticky="w", padx=10, pady=5)

        default_downloads = str(Path.home() / "Downloads")
        self.dir_var = tk.StringVar(value=default_downloads)
        dir_entry = ctk.CTkEntry(config_frame, textvariable=self.dir_var, width=400) if HAS_CTK else tk.Entry(config_frame, textvariable=self.dir_var, width=45)
        dir_entry.grid(row=0, column=1, padx=10, pady=5)

        browse_btn = ctk.CTkButton(config_frame, text="Select Folder", command=self.browse_folder) if HAS_CTK else tk.Button(config_frame, text="Select Folder", command=self.browse_folder)
        browse_btn.grid(row=0, column=2, padx=10, pady=5)

        # Service Status & Toggle
        ctrl_frame = ctk.CTkFrame(self) if HAS_CTK else tk.Frame(self)
        ctrl_frame.pack(fill="x", padx=15, pady=10)

        self.status_badge = ctk.CTkLabel(ctrl_frame, text="● WATCHER STOPPED", text_color="#ef4444", font=("Segoe UI", 12, "bold")) if HAS_CTK else tk.Label(ctrl_frame, text="● WATCHER STOPPED", fg="#ef4444", font=("Segoe UI", 11, "bold"))
        self.status_badge.pack(side="left", padx=10)

        self.toggle_btn = ctk.CTkButton(
            ctrl_frame, text="Start Background Watcher",
            fg_color="#10b981", hover_color="#059669",
            command=self.toggle_watcher
        ) if HAS_CTK else tk.Button(ctrl_frame, text="Start Background Watcher", bg="#10b981", fg="white", command=self.toggle_watcher)
        self.toggle_btn.pack(side="right", padx=10)

        # Activity Log View
        log_frame = ctk.CTkFrame(self) if HAS_CTK else tk.LabelFrame(self, text="Background Activity Log", padx=5, pady=5)
        log_frame.pack(fill="both", expand=True, padx=15, pady=10)

        self.log_list = tk.Listbox(log_frame, bg="#1e293b", fg="#f8fafc", font=("Consolas", 10), selectbackground="#334155")
        log_scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_list.yview)
        self.log_list.configure(yscrollcommand=log_scroll.set)

        self.log_list.pack(side="left", fill="both", expand=True)
        log_scroll.pack(side="right", fill="y")

        self.log("Background Watcher Service ready.")

    def log(self, text: str):
        def _add():
            self.log_list.insert(tk.END, text)
            self.log_list.see(tk.END)
        self.after(0, _add)

    def browse_folder(self):
        folder = filedialog.askdirectory(initialdir=self.dir_var.get())
        if folder:
            self.dir_var.set(folder)

    def toggle_watcher(self):
        if self.watcher and self.watcher.is_running:
            self.watcher.stop()
            self.watcher = None
            self.status_badge.configure(text="● WATCHER STOPPED", text_color="#ef4444" if HAS_CTK else None)
            if not HAS_CTK:
                self.status_badge.configure(fg="#ef4444")
            self.toggle_btn.configure(text="Start Background Watcher", fg_color="#10b981" if HAS_CTK else None)
            self.log("Stopped background watcher service.")
        else:
            watch_dir = Path(self.dir_var.get().strip())
            if not watch_dir.exists():
                messagebox.showerror("Invalid Directory", f"Folder does not exist:\n{watch_dir}")
                return

            def on_file_detected(file_path: Path):
                self.log(f"[DETECTED] New file added: {file_path.name}")
                try:
                    res = self.processor.process(
                        video_path=file_path,
                        progress_callback=lambda pct, txt: self.log(f"[{file_path.name}] {txt}")
                    )
                    self.log(f"[SUCCESS] Automatically cleaned {file_path.name} -> {Path(res['output_video']).name}")
                except Exception as e:
                    self.log(f"[ERROR] Failed to auto-process {file_path.name}: {e}")

            self.watcher = WatcherService(watch_dir=watch_dir, callback=on_file_detected)
            self.watcher.start()

            self.status_badge.configure(text="● WATCHER RUNNING", text_color="#10b981" if HAS_CTK else None)
            if not HAS_CTK:
                self.status_badge.configure(fg="#10b981")
            self.toggle_btn.configure(text="Stop Background Watcher", fg_color="#ef4444" if HAS_CTK else None)
            self.log(f"Monitoring folder: {watch_dir}")
