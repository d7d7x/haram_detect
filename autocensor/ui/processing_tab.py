import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import logging
from pathlib import Path
from autocensor.config import MODE_BEEP, MODE_MUTE, MODE_SUBTITLE_ONLY
from autocensor.core.dictionary import CensorshipDictionary
from autocensor.core.media_processor import MediaProcessor

logger = logging.getLogger(__name__)

try:
    import customtkinter as ctk
    HAS_CTK = True
except ImportError:
    HAS_CTK = False

class ProcessingTabFrame(ctk.CTkFrame if HAS_CTK else tk.Frame):
    def __init__(self, master, dictionary: CensorshipDictionary):
        super().__init__(master)
        self.dictionary = dictionary
        self.processor = MediaProcessor(dictionary)
        self.create_widgets()

    def create_widgets(self):
        # File Inputs Frame
        inputs_frame = ctk.CTkFrame(self) if HAS_CTK else tk.LabelFrame(self, text="File Selection", padx=10, pady=10)
        inputs_frame.pack(fill="x", padx=15, pady=10)

        # Video File Selection
        v_lbl = ctk.CTkLabel(inputs_frame, text="Video File:") if HAS_CTK else tk.Label(inputs_frame, text="Video File:")
        v_lbl.grid(row=0, column=0, sticky="w", padx=10, pady=5)

        self.video_path_var = tk.StringVar()
        v_entry = ctk.CTkEntry(inputs_frame, textvariable=self.video_path_var, width=420, placeholder_text="Drag & drop or select video file (.mp4, .mkv, .avi)...") if HAS_CTK else tk.Entry(inputs_frame, textvariable=self.video_path_var, width=50)
        v_entry.grid(row=0, column=1, padx=10, pady=5)

        v_btn = ctk.CTkButton(inputs_frame, text="Browse", width=90, command=self.browse_video) if HAS_CTK else tk.Button(inputs_frame, text="Browse", command=self.browse_video)
        v_btn.grid(row=0, column=2, padx=10, pady=5)

        # Subtitle File Selection
        s_lbl = ctk.CTkLabel(inputs_frame, text="Subtitle File (Optional):") if HAS_CTK else tk.Label(inputs_frame, text="Subtitle File:")
        s_lbl.grid(row=1, column=0, sticky="w", padx=10, pady=5)

        self.sub_path_var = tk.StringVar()
        s_entry = ctk.CTkEntry(inputs_frame, textvariable=self.sub_path_var, width=420, placeholder_text="Select custom .srt, .ass, or .vtt file (Auto-detects if empty)") if HAS_CTK else tk.Entry(inputs_frame, textvariable=self.sub_path_var, width=50)
        s_entry.grid(row=1, column=1, padx=10, pady=5)

        s_btn = ctk.CTkButton(inputs_frame, text="Browse", width=90, command=self.browse_subtitle) if HAS_CTK else tk.Button(inputs_frame, text="Browse", command=self.browse_subtitle)
        s_btn.grid(row=1, column=2, padx=10, pady=5)

        # Settings & Controls Frame
        settings_frame = ctk.CTkFrame(self) if HAS_CTK else tk.LabelFrame(self, text="Censorship Mode & Actions", padx=10, pady=10)
        settings_frame.pack(fill="x", padx=15, pady=10)

        m_lbl = ctk.CTkLabel(settings_frame, text="Audio Censorship Mode:") if HAS_CTK else tk.Label(settings_frame, text="Audio Mode:")
        m_lbl.pack(side="left", padx=10)

        self.mode_var = tk.StringVar(value=MODE_BEEP)
        mode_options = [
            ("1kHz BEEP Tone (طوط)", MODE_BEEP),
            ("Mute Audio", MODE_MUTE),
            ("Subtitle Replacement Only", MODE_SUBTITLE_ONLY)
        ]

        for text, val in mode_options:
            if HAS_CTK:
                ctk.CTkRadioButton(settings_frame, text=text, variable=self.mode_var, value=val).pack(side="left", padx=10)
            else:
                tk.Radiobutton(settings_frame, text=text, variable=self.mode_var, value=val).pack(side="left", padx=10)

        self.start_btn = ctk.CTkButton(
            settings_frame, text="▶ Process Video Now",
            fg_color="#6366f1", hover_color="#4f46e5",
            font=("Segoe UI", 13, "bold"),
            height=38,
            command=self.start_processing
        ) if HAS_CTK else tk.Button(settings_frame, text="▶ Process Video Now", bg="#6366f1", fg="white", font=("Segoe UI", 11, "bold"), command=self.start_processing)
        self.start_btn.pack(side="right", padx=10)

        # Progress Frame
        progress_frame = ctk.CTkFrame(self) if HAS_CTK else tk.Frame(self)
        progress_frame.pack(fill="x", padx=15, pady=5)

        self.status_lbl = ctk.CTkLabel(progress_frame, text="Ready for ingestion.", text_color="#94a3b8") if HAS_CTK else tk.Label(progress_frame, text="Ready.")
        self.status_lbl.pack(anchor="w", padx=5)

        if HAS_CTK:
            self.progress_bar = ctk.CTkProgressBar(progress_frame, width=600)
            self.progress_bar.set(0.0)
            self.progress_bar.pack(fill="x", padx=5, pady=5)
        else:
            self.progress_bar = ttk.Progressbar(progress_frame, maximum=100)
            self.progress_bar.pack(fill="x", padx=5, pady=5)

        # Detection Log Table
        log_frame = ctk.CTkFrame(self) if HAS_CTK else tk.LabelFrame(self, text="Detection Log", padx=5, pady=5)
        log_frame.pack(fill="both", expand=True, padx=15, pady=10)

        cols = ("time", "original", "censored", "terms")
        self.log_tree = ttk.Treeview(log_frame, columns=cols, show="headings", height=8)

        self.log_tree.heading("time", text="Timestamp")
        self.log_tree.heading("original", text="Original Subtitle Line")
        self.log_tree.heading("censored", text="Censored Subtitle Line")
        self.log_tree.heading("terms", text="Detected Prohibited Terms")

        self.log_tree.column("time", width=140, anchor="center")
        self.log_tree.column("original", width=250, anchor="w")
        self.log_tree.column("censored", width=250, anchor="w")
        self.log_tree.column("terms", width=180, anchor="w")

        tree_scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_tree.yview)
        self.log_tree.configure(yscrollcommand=tree_scroll.set)

        self.log_tree.pack(side="left", fill="both", expand=True)
        tree_scroll.pack(side="right", fill="y")

    def browse_video(self):
        file_path = filedialog.askopenfilename(
            filetypes=[("Video Files", "*.mp4 *.mkv *.avi *.mov *.webm"), ("All Files", "*.*")]
        )
        if file_path:
            self.video_path_var.set(file_path)

    def browse_subtitle(self):
        file_path = filedialog.askopenfilename(
            filetypes=[("Subtitle Files", "*.srt *.vtt *.ass"), ("All Files", "*.*")]
        )
        if file_path:
            self.sub_path_var.set(file_path)

    def start_processing(self):
        video_str = self.video_path_var.get().strip()
        if not video_str:
            messagebox.showwarning("Input Missing", "Please select a video file to process.")
            return

        video_path = Path(video_str)
        if not video_path.exists():
            messagebox.showerror("File Error", f"File does not exist:\n{video_str}")
            return

        sub_str = self.sub_path_var.get().strip()
        sub_path = Path(sub_str) if sub_str else None

        mode = self.mode_var.get()
        self.start_btn.configure(state="disabled")

        for item in self.log_tree.get_children():
            self.log_tree.delete(item)

        def progress_update(pct: float, text: str):
            def gui():
                self.status_lbl.configure(text=text)
                if HAS_CTK:
                    self.progress_bar.set(pct)
                else:
                    self.progress_bar["value"] = pct * 100
            self.after(0, gui)

        def run_pipeline():
            try:
                result = self.processor.process(
                    video_path=video_path,
                    subtitle_path=sub_path,
                    mode=mode,
                    progress_callback=progress_update
                )

                def on_done():
                    self.start_btn.configure(state="normal")
                    count = result["detections_count"]
                    for d in result["detections"]:
                        time_range = f"{d.get('start_str', '')} -> {d.get('end_str', '')}"
                        self.log_tree.insert("", "end", values=(
                            time_range,
                            d.get("original", ""),
                            d.get("censored", ""),
                            ", ".join(d.get("matched_terms", []))
                        ))

                    messagebox.showinfo(
                        "Processing Complete!",
                        f"Successfully generated clean media!\n\nOutput: {Path(result['output_video']).name}\nCensored Events: {count}"
                    )

                self.after(0, on_done)

            except Exception as e:
                logger.error(f"Processing error: {e}")
                def on_err():
                    self.start_btn.configure(state="normal")
                    self.status_lbl.configure(text="Error occurred during processing.")
                    messagebox.showerror("Processing Failed", f"An error occurred:\n{e}")
                self.after(0, on_err)

        threading.Thread(target=run_pipeline, daemon=True).start()
