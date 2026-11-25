"""Character and outfit settings tabs."""

import os
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from minibuddies.catalog import DORO_MOTION_DIR, FRANCHISE, SQUADS, SQUAD_NAME
from minibuddies.desktop import CHAR_SCREEN
from minibuddies.runtime import CHARS_DIR


class CharacterTabs:
    # 캐릭터: 등장시킬 멤버 고르기 (그룹별 체크)
    def tab_chars(self):
        """캐릭터 고르기 — 위 검색칸(초성 가능) + 왼쪽 작품 목록(고른 수) + 오른쪽 작품별·그룹별 체크"""
        from PyQt5.QtWidgets import QScrollArea, QLineEdit, QListWidget
        w = QWidget(); lay = QVBoxLayout(w)
        szbox = QGroupBox("크기"); sf = QFormLayout(szbox)
        self.size_form(sf)
        lay.addWidget(szbox)

        top = QHBoxLayout()
        self.pick_search = QLineEdit()
        self.pick_search.setPlaceholderText("🔍 이름·작품·그룹으로 찾기  (초성도 돼요: ㅎㄹㄹㅇㅂ)")
        self.pick_search.setClearButtonEnabled(True)
        self.pick_search.setStyleSheet("QLineEdit{padding:6px 8px;border:1px solid #f0bcd6;border-radius:8px;background:#fff;}")
        self.pick_search.textChanged.connect(lambda _=None: self.pick_filter())
        top.addWidget(self.pick_search, 1)
        self.pick_only = QCheckBox("고른 친구만")
        self.pick_only.toggled.connect(lambda _=False: self.pick_filter())
        top.addWidget(self.pick_only)
        for lab, fn in [("전체 선택", lambda: self.pick_set(self.app.roster)), ("전체 해제", lambda: self.pick_set([]))]:
            bt = QPushButton(lab); bt.clicked.connect(fn); top.addWidget(bt)
        lay.addLayout(top)
        self.pick_count = QLabel("")
        self.pick_count.setStyleSheet("color:#8a5a75;padding:2px 2px 4px 2px;")
        lay.addWidget(self.pick_count)

        fr = []
        used = set()
        for fname, sqs in FRANCHISE:
            sqs = [sq for sq in sqs if any(c in self.app.roster for c in SQUADS.get(sq, []))]
            if sqs:
                fr.append((fname, sqs)); used.update(sqs)
        rest_sq = [sq for sq in SQUADS if sq not in used and any(c in self.app.roster for c in SQUADS[sq])]
        if rest_sq:
            fr.append(("그 밖의 작품", rest_sq))
        loose = [c for c in self.app.roster if not any(c in SQUADS[sq] for _, sqs in fr for sq in sqs)]
        if loose:
            fr.append(("그 밖의 친구들", [None]))

        body = QHBoxLayout()
        self.fr_list = QListWidget()
        self.fr_list.setFixedWidth(200)
        self.fr_list.setStyleSheet(
            "QListWidget{background:#fff;border:1px solid #f0c8dc;border-radius:8px;outline:0;}"
            "QListWidget::item{padding:7px 8px;border-radius:6px;}"
            "QListWidget::item:selected{background:#ffd6ea;color:#7a2350;}"
            "QListWidget::item:hover{background:#fff0f7;}")
        body.addWidget(self.fr_list)
        page = QWidget(); pl = QVBoxLayout(page)
        self.fr_sections = []                      # [이름, 제목, [(상자, 격자, 멤버, 체크들, 모니터칸)], 목록 항목]
        for fname, sqs in fr:
            head = QLabel(fname)
            head.setStyleSheet("font-size:15px;font-weight:bold;color:#c8467e;padding:10px 2px 2px 2px;")
            pl.addWidget(head)
            boxes = []
            for sq in sqs:
                mem = loose if sq is None else [c for c in SQUADS[sq] if c in self.app.roster]
                if not mem:
                    continue
                box = QGroupBox(SQUAD_NAME.get(sq, "그 밖의 친구들"))
                g = QGridLayout(box)
                only = QPushButton("모두 선택")                 # 누를 때마다 이 그룹 모두 선택 ↔ 모두 해제
                only.setMaximumWidth(120)
                only.clicked.connect(lambda _=False, mem=mem: self.group_toggle(mem))
                self.group_btns.append((mem, only))
                g.addWidget(only, 0, 3)
                mc = None
                if len(QApplication.screens()) > 1:            # 모니터가 여럿이면 그룹마다 띄울 모니터
                    mc = QComboBox()
                    mc.addItem("모니터: 기본(화면 탭 설정)", "")
                    for i, sc in enumerate(QApplication.screens()):
                        gg = sc.geometry()
                        mc.addItem(f"모니터 {i + 1}" + (" (주)" if sc is QApplication.primaryScreen() else "")
                                   + f" {gg.width()}x{gg.height()}", sc.name())
                    mc.setCurrentIndex(max(0, mc.findData(CHAR_SCREEN.get(mem[0], ""))))
                    self.group_scr.append((mem, mc))
                    g.addWidget(mc, 1000, 0, 1, 4)
                cbs = []
                for n, c in enumerate(mem):
                    lab = self.app.chars[c]["label"]
                    if c in self.app.outfits and len(self.app.outfits[c]) > 1:
                        lab += f" ({len(self.app.outfits[c])}가지 모습)"
                    cb = QCheckBox(lab); cb.setChecked(c in self.app.team)
                    cb.toggled.connect(lambda _=False: self.group_labels())
                    cb._key = " ".join([lab, c, SQUAD_NAME.get(sq, "") if sq else "", fname]).lower()
                    self.picks[c] = cb
                    g.addWidget(cb, n // 3, n % 3)
                    cbs.append((c, cb))
                pl.addWidget(box)
                boxes.append((box, g, mem, cbs, mc))
            self.fr_list.addItem(fname)
            self.fr_sections.append([fname, head, boxes, self.fr_list.item(self.fr_list.count() - 1)])
        self.pick_none = QLabel("찾는 친구가 없어요. 이름 일부나 초성으로도 찾아 보세요.")
        self.pick_none.setStyleSheet("color:#a07890;padding:20px;")
        self.pick_none.hide()
        pl.addWidget(self.pick_none)
        pl.addStretch(1)
        self.pick_scroll = QScrollArea(); self.pick_scroll.setWidgetResizable(True); self.pick_scroll.setWidget(page)
        self.pick_scroll.setMinimumHeight(340)
        body.addWidget(self.pick_scroll, 1)
        lay.addLayout(body, 1)
        self.fr_list.itemClicked.connect(lambda it: self.pick_jump(it))
        # 왼쪽에서 고른 작품만 오른쪽에 보이기 (검색하거나 '고른 친구만'을 켜면 모든 작품에서 찾기)
        self.pick_fr = self.fr_sections[0][0] if self.fr_sections else None
        if self.fr_sections:
            self.fr_list.setCurrentItem(self.fr_sections[0][3])
        self.pick_filter()
        self.pick_note = QLabel("처음 켤 때는 엘리시아만 나와요. 여기서 고르면 다음에 켤 때도 그대로예요.")
        self.pick_note.setWordWrap(True)
        lay.addWidget(self.pick_note)
        return w

    @staticmethod
    def _cho(s):
        """한글 → 초성 (검색에서 'ㅎㄹ' 로 '홀로라이브' 찾기)"""
        t = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ"
        return "".join(t[(ord(ch) - 0xAC00) // 588] if "가" <= ch <= "힣" else ch for ch in s)

    def pick_filter(self):
        """검색어·'고른 친구만' 에 맞는 캐릭터만 보이게 — 격자를 다시 채워서 빈칸 없이"""
        q = self.pick_search.text().strip().lower().replace(" ", "")
        only = self.pick_only.isChecked()
        any_vis = False
        for sec in self.fr_sections:
            fname, head, boxes, item = sec
            fr_ok = bool(q or only) or getattr(self, "pick_fr", None) in (None, fname)
            sec_vis = False
            sec_any = False
            for box, g, mem, cbs, mc in boxes:
                for c, cb in cbs:
                    g.removeWidget(cb)
                n = 0
                for c, cb in cbs:
                    k = cb._key.replace(" ", "")
                    ok = (not q or q in k or q in self._cho(k)) and (not only or cb.isChecked())
                    sec_any = sec_any or ok
                    ok = ok and fr_ok
                    cb.setVisible(ok)
                    if ok:
                        g.addWidget(cb, n // 3, n % 3); n += 1
                box.setVisible(n > 0)
                sec_vis = sec_vis or n > 0
            head.setVisible(sec_vis)
            item.setHidden(not sec_any)
            any_vis = any_vis or sec_vis
        self.pick_none.setVisible(not any_vis)
        self.pick_scroll.verticalScrollBar().setValue(0)
        self.group_labels()

    def pick_jump(self, item):
        """왼쪽 작품 이름 누르면 오른쪽엔 그 작품만 보이게 (검색어·'고른 친구만'은 풀고)"""
        for fname, head, boxes, it in self.fr_sections:
            if it is item:
                self.pick_fr = fname
                for wdg, fn in ((self.pick_search, lambda: self.pick_search.clear()),
                                (self.pick_only, lambda: self.pick_only.setChecked(False))):
                    wdg.blockSignals(True); fn(); wdg.blockSignals(False)
                self.pick_filter()
                return

    def pick_follow(self, v):
        """스크롤하면 왼쪽 목록에서 지금 보고 있는 작품을 표시"""
        cur = None
        for fname, head, boxes, it in self.fr_sections:
            if head.isVisible() and head.y() <= v + 40:
                cur = it
        if cur is None:
            return
        self.fr_list.blockSignals(True)
        self.fr_list.setCurrentItem(cur)
        self.fr_list.blockSignals(False)

    # 의상: 캐릭터별 옷 고르기 + 알아서 갈아입기
    def tab_outfit(self):
        w = QWidget(); f = QFormLayout(w)
        # 캐릭터별 옷 고르기는 우클릭 메뉴 '옷 갈아입기'로 (여기엔 켜고 끄는 것만)
        on = QLabel("옷은 캐릭터를 우클릭 → '옷 갈아입기'에서 골라요."); on.setWordWrap(True); on.setStyleSheet("color:#9a8592;")
        f.addRow("", on)
        self.oauto = QCheckBox("가끔(12~25분마다) 알아서 옷 갈아입기")
        self.oauto.setChecked(self.app.cfg.get("outfit_auto", True))
        f.addRow("", self.oauto)
        self.doro_mo = None
        if "dorothy" in self.app.outfits and os.path.exists(os.path.join(CHARS_DIR, DORO_MOTION_DIR, "0.png")):
            self.doro_mo = QCheckBox("도로롱 모션 버전 쓰기")
            self.doro_mo.setChecked(bool(self.app.cfg.get("doro_motion", False)))
            self.doro_mo.toggled.connect(self.doro_motion_warn)
            f.addRow("", self.doro_mo)
            dn = QLabel("동작이 훨씬 많지만 생김새가 원본과 달라요."); dn.setWordWrap(True); dn.setStyleSheet("color:#887;")
            f.addRow("", dn)
        return w

    def doro_motion_warn(self, on):
        if not on:
            return
        from PyQt5.QtWidgets import QMessageBox
        r = QMessageBox.question(self, "도로롱 모션 버전",
                                 "모션 버전 도로롱은 원래 도로롱과 모습이 많이 달라요!\n"
                                 "(머리가 훨씬 크고, 강아지처럼 네 발로 걸어 다니는 모습이에요)\n\n"
                                 "대신 걷기·매달리기·개성 동작·사격 같은 움직임이 훨씬 많아요.\n그래도 바꿀까요?",
                                 QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if r != QMessageBox.Yes:
            self.doro_mo.blockSignals(True); self.doro_mo.setChecked(False); self.doro_mo.blockSignals(False)

    def pick_set(self, which):
        for c, cb in self.picks.items():
            cb.setChecked(c in which)

    def group_toggle(self, mem):
        """그룹 버튼: 다 켜져 있으면 그 그룹만 모두 끄고, 아니면 그 그룹만 모두 켬 (다른 그룹은 그대로)"""
        on = not all(self.picks[c].isChecked() for c in mem if c in self.picks)
        for c in mem:
            if c in self.picks:
                self.picks[c].setChecked(on)
        self.group_labels()

    def group_labels(self):
        for mem, bt in getattr(self, "group_btns", []):
            full = all(self.picks[c].isChecked() for c in mem if c in self.picks)
            bt.setText("모두 해제" if full else "모두 선택")
        # 왼쪽 작품 목록에 '고른 수/전체', 위에 전체 고른 수
        for fname, head, boxes, item in getattr(self, "fr_sections", []):
            cs = [cb for box, g, mem, cbs, mc in boxes for c, cb in cbs]
            on = sum(cb.isChecked() for cb in cs)
            item.setText(f"{fname}   {on}/{len(cs)}")
            head.setText(f"{fname}  ·  {on}/{len(cs)}")
        if hasattr(self, "pick_count"):
            on = sum(cb.isChecked() for cb in self.picks.values())
            self.pick_count.setText(f"고른 친구 {on}명  ·  전체 {len(self.picks)}명")
