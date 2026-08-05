import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import logging
from pathlib import Path
from autocensor.core.dictionary import CensorshipDictionary, CensorshipTerm

logger = logging.getLogger(__name__)

try:
    import customtkinter as ctk
    HAS_CTK = True
except ImportError:
    HAS_CTK = False

class DictionaryTabFrame(ctk.CTkFrame if HAS_CTK else tk.Frame):
    def __init__(self, master, dictionary: CensorshipDictionary):
        super().__init__(master)
        self.dictionary = dictionary
        self.create_widgets()
        self.refresh_table()

    def create_widgets(self):
        # Header / Controls bar
        control_frame = ctk.CTkFrame(self) if HAS_CTK else tk.Frame(self)
        control_frame.pack(fill="x", padx=15, pady=10)

        # Search box
        search_lbl = ctk.CTkLabel(control_frame, text="Search:") if HAS_CTK else tk.Label(control_frame, text="Search:")
        search_lbl.pack(side="left", padx=5)

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *args: self.refresh_table())
        search_entry = ctk.CTkEntry(control_frame, textvariable=self.search_var, width=180) if HAS_CTK else tk.Entry(control_frame, textvariable=self.search_var, width=20)
        search_entry.pack(side="left", padx=5)

        # Category Filter
        cat_lbl = ctk.CTkLabel(control_frame, text="Category:") if HAS_CTK else tk.Label(control_frame, text="Category:")
        cat_lbl.pack(side="left", padx=(15, 5))

        self.category_var = tk.StringVar(value="All")
        categories = ["All", "Polytheism", "Inappropriate Phrase", "Profanity", "Custom"]
        if HAS_CTK:
            cat_menu = ctk.CTkOptionMenu(control_frame, variable=self.category_var, values=categories, command=lambda v: self.refresh_table())
        else:
            cat_menu = ttk.Combobox(control_frame, textvariable=self.category_var, values=categories, state="readonly", width=15)
            cat_menu.bind("<<ComboboxSelected>>", lambda e: self.refresh_table())
        cat_menu.pack(side="left", padx=5)

        # Action Buttons
        btn_frame = ctk.CTkFrame(control_frame) if HAS_CTK else tk.Frame(control_frame)
        btn_frame.pack(side="right", padx=5)

        add_btn = ctk.CTkButton(btn_frame, text="+ Add Term", fg_color="#10b981", hover_color="#059669", command=self.open_add_dialog) if HAS_CTK else tk.Button(btn_frame, text="+ Add Term", bg="#10b981", fg="white", command=self.open_add_dialog)
        add_btn.pack(side="left", padx=5)

        del_btn = ctk.CTkButton(btn_frame, text="Delete Selected", fg_color="#ef4444", hover_color="#dc2626", command=self.delete_selected) if HAS_CTK else tk.Button(btn_frame, text="Delete Selected", bg="#ef4444", fg="white", command=self.delete_selected)
        del_btn.pack(side="left", padx=5)

        export_btn = ctk.CTkButton(btn_frame, text="Export JSON", command=self.export_json) if HAS_CTK else tk.Button(btn_frame, text="Export JSON", command=self.export_json)
        export_btn.pack(side="left", padx=5)

        # Table View (Treeview)
        table_frame = ctk.CTkFrame(self) if HAS_CTK else tk.Frame(self)
        table_frame.pack(fill="both", expand=True, padx=15, pady=10)

        columns = ("id", "term", "language", "category", "match_type", "replacement")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=12)

        self.tree.heading("id", text="ID")
        self.tree.heading("term", text="Prohibited Term")
        self.tree.heading("language", text="Lang")
        self.tree.heading("category", text="Category")
        self.tree.heading("match_type", text="Match Type")
        self.tree.heading("replacement", text="Replacement")

        self.tree.column("id", width=60, anchor="center")
        self.tree.column("term", width=220, anchor="w")
        self.tree.column("language", width=60, anchor="center")
        self.tree.column("category", width=140, anchor="w")
        self.tree.column("match_type", width=100, anchor="center")
        self.tree.column("replacement", width=120, anchor="center")

        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def refresh_table(self):
        """Populate treeview based on search query and category filter."""
        for item in self.tree.get_children():
            self.tree.delete(item)

        query = self.search_var.get().lower().strip()
        cat = self.category_var.get()

        for term in self.dictionary.terms:
            if cat != "All" and term.category != cat:
                continue
            if query and not (query in term.term.lower() or query in term.category.lower()):
                continue

            self.tree.insert("", "end", values=(
                term.id,
                term.term,
                term.language.upper(),
                term.category,
                term.match_type,
                term.replacement
            ))

    def open_add_dialog(self):
        """Dialog window to add a new term."""
        dlg = ctk.CTkToplevel(self) if HAS_CTK else tk.Toplevel(self)
        dlg.title("Add Prohibited Term")
        dlg.geometry("400x380")
        dlg.grab_set()

        # Term Entry
        ctk.CTkLabel(dlg, text="Term:").pack(anchor="w", padx=20, pady=(15, 2)) if HAS_CTK else tk.Label(dlg, text="Term:").pack(anchor="w", padx=20)
        term_entry = ctk.CTkEntry(dlg, width=340) if HAS_CTK else tk.Entry(dlg, width=40)
        term_entry.pack(padx=20, pady=5)

        # Language
        ctk.CTkLabel(dlg, text="Language:").pack(anchor="w", padx=20, pady=(10, 2)) if HAS_CTK else tk.Label(dlg, text="Language:").pack(anchor="w", padx=20)
        lang_var = tk.StringVar(value="ar")
        if HAS_CTK:
            ctk.CTkOptionMenu(dlg, variable=lang_var, values=["ar", "en"]).pack(anchor="w", padx=20, pady=5)
        else:
            ttk.Combobox(dlg, textvariable=lang_var, values=["ar", "en"], state="readonly").pack(anchor="w", padx=20, pady=5)

        # Category
        ctk.CTkLabel(dlg, text="Category:").pack(anchor="w", padx=20, pady=(10, 2)) if HAS_CTK else tk.Label(dlg, text="Category:").pack(anchor="w", padx=20)
        cat_var = tk.StringVar(value="Polytheism")
        if HAS_CTK:
            ctk.CTkOptionMenu(dlg, variable=cat_var, values=["Polytheism", "Inappropriate Phrase", "Profanity", "Custom"]).pack(anchor="w", padx=20, pady=5)
        else:
            ttk.Combobox(dlg, textvariable=cat_var, values=["Polytheism", "Inappropriate Phrase", "Profanity", "Custom"], state="readonly").pack(anchor="w", padx=20, pady=5)

        # Replacement
        ctk.CTkLabel(dlg, text="Replacement Text:").pack(anchor="w", padx=20, pady=(10, 2)) if HAS_CTK else tk.Label(dlg, text="Replacement Text:").pack(anchor="w", padx=20)
        rep_entry = ctk.CTkEntry(dlg, width=340) if HAS_CTK else tk.Entry(dlg, width=40)
        rep_entry.insert(0, "(طوط)")
        rep_entry.pack(padx=20, pady=5)

        def save():
            text = term_entry.get().strip()
            if not text:
                messagebox.showwarning("Validation Error", "Please enter a valid term.", parent=dlg)
                return

            new_term = CensorshipTerm(
                term=text,
                language=lang_var.get(),
                category=cat_var.get(),
                match_type="word",
                replacement=rep_entry.get().strip() or "[BEEP]"
            )
            self.dictionary.add_term(new_term)
            self.dictionary.save()
            self.refresh_table()
            dlg.destroy()

        save_btn = ctk.CTkButton(dlg, text="Save Term", fg_color="#6366f1", command=save) if HAS_CTK else tk.Button(dlg, text="Save Term", bg="#6366f1", fg="white", command=save)
        save_btn.pack(pady=20)

    def delete_selected(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Select Term", "Please select a term to delete.")
            return

        for item in selected:
            vals = self.tree.item(item, "values")
            term_id = vals[0]
            self.dictionary.remove_term(term_id)

        self.dictionary.save()
        self.refresh_table()

    def export_json(self):
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON Files", "*.json")])
        if path:
            self.dictionary.save(Path(path))
            messagebox.showinfo("Export Successful", f"Dictionary exported to:\n{path}")
