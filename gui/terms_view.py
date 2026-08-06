import json
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem, QLineEdit,
    QPushButton, QLabel, QCheckBox, QComboBox, QGroupBox, QFileDialog, QMessageBox, QTextEdit
)
from core.models import TermList, SanitizationAction, TranscriptSegment
from core.config_manager import ConfigManager
from core.term_matcher import TermMatcher

class TermsView(QWidget):
    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.term_lists = config_manager.term_lists
        self.current_list: Optional[TermList] = None
        self.init_ui()

    def init_ui(self):
        main_layout = QHBoxLayout(self)

        # Left Column: Term Lists
        left_layout = QVBoxLayout()
        left_layout.addWidget(QLabel("Term Categories:"))

        self.list_widget = QListWidget()
        self.list_widget.currentRowChanged.connect(self.on_category_selected)
        left_layout.addWidget(self.list_widget)

        btn_row = QHBoxLayout()
        btn_add_cat = QPushButton("New Category")
        btn_add_cat.clicked.connect(self.add_category)
        btn_del_cat = QPushButton("Delete Category")
        btn_del_cat.clicked.connect(self.delete_category)
        btn_row.addWidget(btn_add_cat)
        btn_row.addWidget(btn_del_cat)
        left_layout.addLayout(btn_row)

        io_row = QHBoxLayout()
        btn_import = QPushButton("Import JSON")
        btn_import.clicked.connect(self.import_json)
        btn_export = QPushButton("Export JSON")
        btn_export.clicked.connect(self.export_json)
        io_row.addWidget(btn_import)
        io_row.addWidget(btn_export)
        left_layout.addLayout(io_row)

        main_layout.addLayout(left_layout, 1)

        # Right Column: Details & Editing
        right_layout = QVBoxLayout()
        details_group = QGroupBox("Category Details & Patterns")
        d_layout = QVBoxLayout(details_group)

        self.cat_name_input = QLineEdit()
        self.cat_enabled_cb = QCheckBox("Enable Category")
        
        self.action_combo = QComboBox()
        for act in SanitizationAction:
            self.action_combo.addItem(act.value, act)

        self.regex_cb = QCheckBox("Use Regex Patterns")

        d_layout.addWidget(QLabel("Category Name:"))
        d_layout.addWidget(self.cat_name_input)
        d_layout.addWidget(self.cat_enabled_cb)
        d_layout.addWidget(QLabel("Assigned Action:"))
        d_layout.addWidget(self.action_combo)
        d_layout.addWidget(self.regex_cb)

        d_layout.addWidget(QLabel("Forbidden Patterns (one per line):"))
        self.patterns_edit = QTextEdit()
        d_layout.addWidget(self.patterns_edit)

        btn_save = QPushButton("Save Category Changes")
        btn_save.clicked.connect(self.save_current_category)
        d_layout.addWidget(btn_save)

        right_layout.addWidget(details_group)

        # Test Matcher Box
        test_group = QGroupBox("Test Term Matcher Playground")
        t_layout = QVBoxLayout(test_group)

        self.test_input = QLineEdit("O God, protect us from polytheistic idols!")
        btn_test = QPushButton("Test Matcher")
        btn_test.clicked.connect(self.run_test_matcher)
        self.test_result_label = QLabel("Matches: None")

        t_layout.addWidget(self.test_input)
        t_layout.addWidget(btn_test)
        t_layout.addWidget(self.test_result_label)

        right_layout.addWidget(test_group)
        main_layout.addLayout(right_layout, 2)

        self.load_list_widget()

    def load_list_widget(self):
        self.list_widget.clear()
        for t in self.term_lists:
            item = QListWidgetItem(t.name)
            self.list_widget.addItem(item)
        if self.term_lists:
            self.list_widget.setCurrentRow(0)

    def on_category_selected(self, row: int):
        if 0 <= row < len(self.term_lists):
            self.current_list = self.term_lists[row]
            self.cat_name_input.setText(self.current_list.name)
            self.cat_enabled_cb.setChecked(self.current_list.enabled)
            self.action_combo.setCurrentText(self.current_list.action.value)
            self.regex_cb.setChecked(self.current_list.is_regex)
            self.patterns_edit.setPlainText("\n".join(self.current_list.patterns))

    def save_current_category(self):
        if not self.current_list:
            return
        self.current_list.name = self.cat_name_input.text().strip()
        self.current_list.enabled = self.cat_enabled_cb.isChecked()
        self.current_list.action = SanitizationAction(self.action_combo.currentText())
        self.current_list.is_regex = self.regex_cb.isChecked()
        patterns = [p.strip() for p in self.patterns_edit.toPlainText().splitlines() if p.strip()]
        self.current_list.patterns = patterns

        self.config_manager.save_terms(self.term_lists)
        self.load_list_widget()
        QMessageBox.information(self, "Terms Saved", "Term list updated and persisted.")

    def add_category(self):
        new_cat = TermList(
            id=f"user_cat_{len(self.term_lists)+1}",
            name="New Term Category",
            enabled=True,
            action=SanitizationAction.BLACK_MUTE,
            patterns=["sample_pattern"],
            is_regex=False
        )
        self.term_lists.append(new_cat)
        self.config_manager.save_terms(self.term_lists)
        self.load_list_widget()
        self.list_widget.setCurrentRow(len(self.term_lists) - 1)

    def delete_category(self):
        row = self.list_widget.currentRow()
        if 0 <= row < len(self.term_lists):
            del self.term_lists[row]
            self.config_manager.save_terms(self.term_lists)
            self.load_list_widget()

    def import_json(self):
        file, _ = QFileDialog.getOpenFileName(self, "Import Terms JSON", "", "JSON Files (*.json)")
        if file:
            try:
                with open(file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                imported = [TermList(**item) for item in data.get("term_lists", [])]
                self.term_lists.extend(imported)
                self.config_manager.save_terms(self.term_lists)
                self.load_list_widget()
                QMessageBox.information(self, "Import Success", "Term list imported successfully.")
            except Exception as e:
                QMessageBox.critical(self, "Import Error", f"Failed to import: {e}")

    def export_json(self):
        file, _ = QFileDialog.getSaveFileName(self, "Export Terms JSON", "terms.json", "JSON Files (*.json)")
        if file:
            try:
                serialized = [t.__dict__ for t in self.term_lists]
                with open(file, "w", encoding="utf-8") as f:
                    json.dump({"term_lists": serialized}, f, indent=2)
                QMessageBox.information(self, "Export Success", "Terms exported successfully.")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Failed to export: {e}")

    def run_test_matcher(self):
        sample_text = self.test_input.text()
        dummy_seg = TranscriptSegment(start=0.0, end=5.0, text=sample_text)
        matcher = TermMatcher(self.term_lists)
        matches = matcher.find_matches([dummy_seg])
        if matches:
            res = ", ".join([f"'{m.matched_text}' ({m.matched_term})" for m in matches])
            self.test_result_label.setText(f"Matches found: {res}")
        else:
            self.test_result_label.setText("No matches found.")
