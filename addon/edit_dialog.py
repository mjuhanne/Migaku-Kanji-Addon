import aqt
from aqt.qt import *

from . import util
from .power_search_bar import PowerSearchBar, ResultsBar

class EditDialog(QDialog):
    def __init__(self, character, item_name, multi_line=False, parent=None):
        super().__init__(parent)

        self.character = character
        self.item_name = item_name
        self.multi_line = multi_line

        readable_name = item_name.replace('_',' ')

        self.original_data = self.get_original_data()
        previous_modified_data = self.get_previous_modified_data()
        if previous_modified_data is None:
            previous_modified_data = self.original_data

        self.setWindowTitle(f"Migaku Kanji - Edit {readable_name} for {character}")
        lyt = QVBoxLayout()
        self.setLayout(lyt)
        lyt.setSpacing(3)

        kanji_label = QLabel(character)
        if character[0] == '[':
            # [primitive] tag -> convert to image
            img = character[1:-1]
            path = util.addon_path('primitives','%s.svg' % img)
            kanji_label.setText('')
            pixmap = QIcon(path).pixmap(QSize(60,60))
            kanji_label.setPixmap(pixmap)

        kanji_label.setStyleSheet('font-size: 40px')
        lyt.addWidget(kanji_label)

        original_label = QLabel(self.original_data)
        button = QPushButton("Reset to original")
        button.clicked.connect(self.on_reset)
        if multi_line:
            original_label.setWordWrap(True)
            original_lyt = QVBoxLayout()
        else:
            original_lyt = QHBoxLayout()
        original_lyt.addWidget(QLabel(f"Original {readable_name}:"))
        if multi_line:
            original_lyt.addItem(QSpacerItem(20, 10, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))
        original_lyt.addWidget(original_label)
        original_lyt.addWidget(button)
        lyt.addLayout(original_lyt)

        lyt.addItem(QSpacerItem(20, 10, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))

        lyt.addWidget(QLabel(f"Enter new {readable_name}:"))
        if multi_line:
            self.new_value_edit = QTextEdit()
            self.new_value_edit.setPlainText(previous_modified_data)
        else:
            self.new_value_edit = QLineEdit(previous_modified_data)
        self.new_value_edit.setStyleSheet(self.get_edit_line_style_sheet())
        lyt.addWidget(self.new_value_edit)

        lyt.addItem(QSpacerItem(20, 10, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))

        self.add_additional_widgets(lyt)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        lyt.addWidget(btns)

        self.resize(475, self.sizeHint().height())

    def get_original_data(self):
        data = aqt.mw.migaku_kanji_db.get_field(self.character,self.item_name)
        if data is not None:
            data = self.process_data_from_db(data)
        return data


    def get_previous_modified_data(self):
        data = aqt.mw.migaku_kanji_db.get_user_modified_field(self.character,self.item_name)
        if data is not None:
            data = self.process_data_from_db(data)
        return data

    def process_data_from_db(self, data):
        # placeholder for post-processor
        return data

    def process_data_to_db(self, data):
        # placeholder for pre-processor
        return data

    def validate_input(self):
        return True

    def add_additional_widgets(self, lyt):
        return

    def get_edit_line_style_sheet(self):
        return ''

    def on_reset(self):
        if self.multi_line:
            self.new_value_edit.setPlainText(self.original_data)
        else:
            self.new_value_edit.setText(self.original_data)

    def save_value_to_db(self, value):
        aqt.mw.migaku_kanji_db.set_user_modified_field(
            self.character, self.item_name, value
        )

    def accept(self):
        if self.validate_input():
            if self.multi_line:
                new_value= self.new_value_edit.toPlainText()
            else:
                new_value= self.new_value_edit.text()
            data_to_db = self.process_data_to_db(new_value)
            self.save_value_to_db(data_to_db)
            super().accept()


class EditPrimitivesDialog(EditDialog):
    def __init__(self, character, parent=None, max_search_results=12):
        self.max_search_results = max_search_results
        super().__init__(character, "primitives", False, parent)

    def get_edit_line_style_sheet(self):
        return 'font-size: 20px'

    def add_additional_widgets(self, lyt):

        lyt.addWidget(QLabel(f"Search primitives by keyword, radical, meaning etc.."))
        self.search_bar_lyt = QVBoxLayout()
        lyt.addLayout(self.search_bar_lyt)
        lyt.addWidget(QLabel(f"Click on result button to add the primitive:"))
        self.results_lyt = QVBoxLayout()
        lyt.addLayout(self.results_lyt)

        bar_height = self.new_value_edit.sizeHint().height()*1.5
        self.power_search_bar = PowerSearchBar( self.search_bar_lyt , self.results_lyt, self.max_search_results,
            bar_height, self.on_primitive_selected, hide_empty_result_buttons=False
        )

        lyt.addItem(QSpacerItem(20, 20, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))

        radicals = aqt.mw.migaku_kanji_db.get_field(self.character,"radicals")
        lyt.addWidget(QLabel(f"Add primitives from radicals:"))
        self.radicals_lyt = QVBoxLayout()
        lyt.addLayout(self.radicals_lyt)

        self.radicals_bar = ResultsBar( self.radicals_lyt, self.max_search_results,
            bar_height, self.on_radical_selected, hide_empty_buttons=True
        )
        self.radicals_bar.set_contents(radicals)


    def process_data_from_db(self, data):
        return ''.join(data)

    def process_data_to_db(self, data):
        return util.custom_list(data)


    def on_primitive_selected(self, primitive):
        current_primitives = self.new_value_edit.text()
        if primitive not in current_primitives:
            self.new_value_edit.setText(current_primitives + primitive)
            self.power_search_bar.clear()

    def on_radical_selected(self, radical):
        primitive = aqt.mw.migaku_kanji_db.search_engine.radical_to_primitive(radical)
        self.on_primitive_selected(primitive)

    def validate_input(self):
        text = self.new_value_edit.text()
        new_primitives = util.custom_list(text)
        for p in new_primitives:
            if not aqt.mw.migaku_kanji_db.does_character_exist(p):
                msg = QMessageBox()
                msg.setIcon(QMessageBox.Warning)
                msg.setText("Invalid primitive: '%s'" % p)
                msg.setWindowTitle("Invalid primitive")
                msg.exec_()
                return False     
        return True


class EditListTypeDialog(EditDialog):
    def __init__(self, character, item_name, parent=None):
        super().__init__(character, item_name, False, parent)


    def process_data_from_db(self, data):
        return ', '.join(data)

    def process_data_to_db(self, data):
        return util.str_to_list(data)


class EditStringTypeDialog(EditDialog):
    def __init__(self, character, item_name, multi_line=False, parent=None):
        super().__init__(character, item_name, multi_line, parent)


class EditUserStoryDialog(EditDialog):
    def __init__(self, character, new_suggested_story, parent=None):
        self.new_suggested_story = new_suggested_story
        super().__init__(character, "user story", True, parent)

    def get_original_data(self):
        return aqt.mw.migaku_kanji_db.get_character_usr_story(self.character)

    def get_previous_modified_data(self):
        return self.new_suggested_story

    def save_value_to_db(self, value):
        aqt.mw.migaku_kanji_db.set_character_usr_story(
            self.character, value
        )
