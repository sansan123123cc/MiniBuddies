"""Trigger, condition, and action editing for one MiniBuddies rule."""

from copy import deepcopy

from PyQt5.QtWidgets import (
    QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QGroupBox,
    QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget, QPushButton, QVBoxLayout, QWidget,
)

from minibuddies.plugins.scenes import PACK_ID
from minibuddies.ui.editor.playback import PlaybackDialog
from minibuddies.ui.editor.steps import Timeline
from minibuddies.ui.editor.widgets import options, show_error, spin


class RuleDialog(QDialog):
    def __init__(self, editor, kind, rule):
        super().__init__(editor)
        self.setWindowTitle("상호작용 규칙" if kind == "interactions" else "개별 동작 규칙")
        self.editor = editor
        self.group = kind == "interactions"
        self.rule = deepcopy(rule)
        self.name = QLineEdit(rule.get("name", ""))
        self.name.setMaxLength(80)
        self.chance_key = "meet_chance" if self.group else "idle_chance"
        self.chance = QDoubleSpinBox()
        self.chance.setRange(0, 100)
        self.chance.setDecimals(4)
        self.chance.setSuffix(" %")
        self.chance.setValue(rule.get(self.chance_key, 0) * 100 or 10)
        trigger_label = "참가자가 가까워질 때" if self.group else "대기를 마칠 때"
        self.trigger = options([("우클릭 메뉴에서 실행", False), (trigger_label, True)], bool(rule.get(self.chance_key)))
        trigger_form = QFormLayout()
        trigger_form.addRow("발동 시점", self.trigger)
        trigger_form.addRow("자동 발동 확률", self.chance)
        self.trigger.currentIndexChanged.connect(lambda: self.chance.setEnabled(bool(self.trigger.currentData())))
        self.chance.setEnabled(bool(self.trigger.currentData()))
        trigger_box = QGroupBox("트리거")
        trigger_box.setLayout(trigger_form)

        self.roles = self.rule.setdefault("roles", []) if self.group else []
        self.characters = self.rule.setdefault("characters", []) if not self.group else []
        if not rule and not self.group and editor.project.kind == "character" and editor.project.id:
            self.characters.append(editor.project.id)
        if not rule and not self.group and editor.project.kind == "skin" and editor.project.target:
            self.characters.append(editor.project.target)
        self.cast = QListWidget()
        self.cast.setMaximumHeight(108)
        self.cast.currentRowChanged.connect(self.select_character)
        add = QPushButton("캐릭터 추가…")
        add.clicked.connect(self.add_character)
        remove = QPushButton("선택 삭제")
        remove.clicked.connect(self.remove_character)
        cast_buttons = QHBoxLayout()
        cast_buttons.addWidget(add)
        cast_buttons.addWidget(remove)
        cast_buttons.addStretch()
        conditions = QVBoxLayout()
        conditions.addWidget(QLabel("함께 참여할 캐릭터 (2~6명)" if self.group else "허용할 캐릭터 (비워두면 팩 범위 전체)"))
        conditions.addLayout(cast_buttons)
        conditions.addWidget(self.cast)
        if self.group:
            self.distance = spin(64, 1200, rule.get("meet_distance", 340), " px")
            self.cooldown = spin(5, 600, rule.get("cooldown_seconds", 40), " 초")
            group_conditions = QFormLayout()
            group_conditions.addRow("참가자 사이 최대 거리", self.distance)
            group_conditions.addRow("자동 재발동 간격", self.cooldown)
            conditions.addLayout(group_conditions)
        condition_box = QGroupBox("조건")
        condition_box.setLayout(conditions)

        self.timeline = Timeline(editor, group=self.group)
        actions = QVBoxLayout()
        actions.addWidget(QLabel("캐릭터별 액션 순서" if self.group else "액션 순서"))
        if not self.group:
            self.speech = QLineEdit(rule.get("say", ""))
            self.speech.setMaxLength(160)
            speech_row = QFormLayout()
            speech_row.addRow("시작 말풍선", self.speech)
            actions.addLayout(speech_row)
        actions.addWidget(self.timeline)
        self.preview_button = QPushButton("전체 참가자 미리 재생…" if self.group else "동작 미리 재생…")
        self.preview_button.setAutoDefault(False)
        self.preview_button.clicked.connect(self.preview_action)
        self.timeline.changed.connect(self.update_preview)
        actions.addWidget(self.preview_button)
        action_box = QGroupBox("액션")
        action_box.setLayout(actions)

        form = QFormLayout()
        form.addRow("규칙 이름", self.name)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        top = QHBoxLayout()
        top.addWidget(trigger_box)
        top.addWidget(condition_box, 2)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(top)
        layout.addWidget(action_box, 1)
        layout.addWidget(buttons)
        self.resize(700, 545)
        self.refresh_cast(0)

    def keys(self):
        return [entry["character"] for entry in self.roles] if self.group else self.characters

    def refresh_cast(self, row):
        self.cast.blockSignals(True)
        self.cast.clear()
        self.cast.addItems([self.editor.character_label(key) for key in self.keys()])
        self.cast.setCurrentRow(min(row, len(self.keys()) - 1))
        self.cast.blockSignals(False)
        self.select_character(self.cast.currentRow())

    def select_character(self, row):
        if self.group:
            if row >= 0:
                role = self.roles[row]
                self.timeline.load(role["steps"], role["character"], self.keys())
            else:
                self.timeline.load([], "", [])
        else:
            actor = self.characters[row] if row >= 0 else self.editor.preview_actor()
            self.timeline.load(self.rule.setdefault("frames", []), actor, [])
        self.update_preview()

    def update_preview(self):
        playable = any(role["steps"] for role in self.roles) if self.group else bool(self.timeline.steps)
        self.preview_button.setEnabled(playable)

    def preview_action(self):
        if self.group:
            sequences = {role["character"]: role["steps"] for role in self.roles}
            opening_speech = ""
        else:
            sequences = {self.timeline.actor: self.timeline.steps}
            opening_speech = self.speech.text()
        try:
            dialog = PlaybackDialog(self, self.editor, sequences, group=self.group, opening_speech=opening_speech)
        except (TypeError, ValueError) as error:
            show_error(self, error)
            return
        dialog.exec_()
        dialog.deleteLater()

    def add_character(self):
        if self.group and len(self.roles) >= 6:
            show_error(self, "참가자는 최대 6명이에요.")
            return
        keys = [key for key in self.editor.known_characters() if key not in self.keys()]
        by_label = {self.editor.character_label(key): key for key in keys}
        value, ok = QInputDialog.getItem(self, "캐릭터 추가", "캐릭터를 고르거나 ID를 입력하세요.", list(by_label), 0, True)
        if not ok:
            return
        key = by_label.get(value, value.strip())
        if not PACK_ID.fullmatch(key) or key in self.keys():
            show_error(self, "중복되지 않은 캐릭터 ID를 입력하세요.")
            return
        if self.group:
            self.roles.append({"character": key, "steps": []})
        else:
            self.characters.append(key)
        self.refresh_cast(len(self.keys()) - 1)

    def remove_character(self):
        row = self.cast.currentRow()
        if row >= 0:
            if self.group:
                key = self.roles[row]["character"]
                if any(step.get("effect", {}).get("target") == key for role in self.roles if role["character"] != key for step in role["steps"]):
                    show_error(self, "이 캐릭터가 다른 참가자의 효과 대상이에요. 해당 효과의 대상을 먼저 바꾸세요.")
                    return
                self.roles.pop(row)
            else:
                self.characters.pop(row)
            self.refresh_cast(row)

    def accept(self):
        name = self.name.text().strip()
        if not name:
            show_error(self, "규칙 이름을 입력하세요.")
            return
        if self.group and (len(self.roles) < 2 or any(not role["steps"] for role in self.roles)):
            show_error(self, "참가자를 두 명 이상 고르고, 참가자마다 액션을 하나 이상 추가하세요.")
            return
        if not self.group and not self.rule["frames"]:
            show_error(self, "액션을 하나 이상 추가하세요.")
            return
        self.rule["name"] = name
        self.rule[self.chance_key] = self.chance.value() / 100 if self.trigger.currentData() else 0
        if self.group:
            self.rule.update(meet_distance=self.distance.value(), cooldown_seconds=self.cooldown.value())
        else:
            self.rule["say"] = self.speech.text()
        super().accept()


class RuleList(QWidget):
    def __init__(self, editor):
        super().__init__()
        self.editor = editor
        self.rules = QListWidget()
        self.index = []
        tools = QHBoxLayout()
        for label, callback in (("개별 동작 추가", lambda: self.add("actions")),
                                ("상호작용 추가", lambda: self.add("interactions")),
                                ("편집", self.edit), ("삭제", self.remove)):
            button = QPushButton(label)
            button.clicked.connect(callback)
            tools.addWidget(button)
        tools.addStretch(1)
        layout = QVBoxLayout(self)
        layout.addLayout(tools)
        layout.addWidget(self.rules)
        self.rules.itemDoubleClicked.connect(self.edit)

    def refresh(self, selected=None):
        self.rules.clear()
        self.index.clear()
        for kind, label in (("actions", "개별 동작"), ("interactions", "상호작용")):
            for index, rule in enumerate(self.editor.project.rules.get(kind, [])):
                self.index.append((kind, index))
                self.rules.addItem(f"{rule['name']} · {label}")
        if selected in self.index:
            self.rules.setCurrentRow(self.index.index(selected))
        elif self.index:
            self.rules.setCurrentRow(0)

    def add(self, kind):
        values = self.editor.project.rules.setdefault(kind, [])
        if len(values) >= (24 if kind == "actions" else 16):
            show_error(self, "이 팩에 넣을 수 있는 규칙 수를 넘었어요.")
            return
        self.open_rule(kind, len(values), {})

    def edit(self):
        row = self.rules.currentRow()
        if row >= 0:
            kind, index = self.index[row]
            self.open_rule(kind, index, self.editor.project.rules[kind][index])

    def open_rule(self, kind, index, rule):
        self.editor.sync_metadata()
        dialog = RuleDialog(self.editor, kind, rule)
        if dialog.exec_() == QDialog.Accepted:
            if any(existing is not rule and existing["name"] == dialog.rule["name"]
                   for group in ("actions", "interactions") for existing in self.editor.project.rules.get(group, [])):
                show_error(self, "팩에 같은 이름의 규칙이 이미 있어요.")
                return
            self.editor.project.rules[kind][index:index + 1] = [dialog.rule]
            self.editor.changed()
            self.refresh((kind, index))

    def remove(self):
        row = self.rules.currentRow()
        if row >= 0:
            kind, index = self.index[row]
            del self.editor.project.rules[kind][index]
            self.editor.changed()
            self.refresh()
