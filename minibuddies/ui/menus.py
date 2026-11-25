"""Pet context menus, system tray and settings entry."""

import datetime
import os
from PyQt5.QtCore import QPoint, QTimer, Qt
from PyQt5.QtWidgets import QApplication, QMenu
from minibuddies.catalog import APP_NAME, F, OUTFIT_NAME, SCENE_MENU, SQUADS, SQUAD_NAME, TRANSFORM
from minibuddies.features.dorothy import DMODE
from minibuddies.features.costumes import _ev_menu
from minibuddies.features.costumes import _ev_menu_all
from minibuddies.features.outfit_music import _osong_menu
from minibuddies.features.pepero import _pepero_day
from minibuddies.features import touhou
from minibuddies.runtime import BASE, _crash_write
from minibuddies.ui.dialogs import SettingsDialog


class AppMenus:
    def plugin_interaction_menu(self, menu, pet):
        library = self.plugins.interactions
        choices = list(library.enabled(self, pet))
        if not choices:
            return
        submenu = menu.addMenu("플러그인 상호작용")
        submenu.setToolTipsVisible(True)
        for pack, interaction in choices:
            item = submenu.addAction(f"{pack.label} · {interaction.label}")
            item.setEnabled(library.formation(self, interaction, pet) is not None)
            item.setToolTip("참여 펫을 같은 모니터, 같은 바닥에 가까이 두세요.")
            item.triggered.connect(lambda _checked, p=pack, i=interaction: library.play(self, p, i, pet))

    def plugin_menu(self, menu, pet):
        from PyQt5.QtCore import QUrl
        from PyQt5.QtGui import QDesktopServices
        from PyQt5.QtWidgets import QMessageBox

        library = self.plugins
        submenu = menu.addMenu("플러그인")

        def open_folder():
            try:
                library.root.mkdir(parents=True, exist_ok=True)
            except OSError as error:
                QMessageBox.warning(None, "플러그인", str(error))
                return
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(library.root)))

        submenu.addAction("플러그인 폴더 열기", open_folder)

        def assign(toggle, pack_id, enabled):
            if library.bind(self, pet.char, pack_id, enabled):
                return
            toggle.blockSignals(True)
            toggle.setChecked(not enabled)
            toggle.blockSignals(False)
            QMessageBox.warning(None, "플러그인", "캐릭터 연결을 저장하지 못했어요.")

        selected = library.selected(self.cfg, pet.char)
        for pack in library.available(pet.char):
            options = submenu.addMenu(pack.label)
            toggle = options.addAction("이 캐릭터에 연결")
            toggle.setCheckable(True)
            toggle.setChecked(pack.id in selected)
            toggle.toggled.connect(lambda checked, item=toggle, pack_id=pack.id: assign(item, pack_id, checked))
            if pack.id in selected:
                options.addSeparator()
                for action in library.actions_for(pack, pet.char):
                    item = options.addAction(action.label)
                    item.triggered.connect(lambda _checked, p=pack, a=action: library.play(pet, p, a))
                    item.setEnabled(library.can_play_action(pet, action))

    def menu(self, pos, who):
        """우클릭 메뉴: 놀이·부르기만. 설정은 '환경설정…' 창으로"""
        top = QMenu()
        m = QMenu("다 같이 · 부르기 · 놀이")          # 캐릭터와 상관없는 메뉴는 한 칸 안으로
        # 1) 멤버
        if self.one_each and len(self.roster) >= 2:
            rm = m.addMenu("멤버 부르기")
            full = [sq for sq, mm in SQUADS.items() if all(c in self.roster for c in mm)]
            if len(full) >= 2 or len(self.roster) > 4:
                rm.addAction(f"다 같이 부르기 ({len(self.roster)}명)", lambda: self.set_team(self.roster))
            for sq in full:
                if set(SQUADS[sq]) != set(self.roster):
                    rm.addAction(f"{SQUAD_NAME[sq]}만 부르기", lambda sq=sq: self.set_team(SQUADS[sq]))
            rm.addSeparator()
            grouped = [(SQUAD_NAME[sq], [c for c in SQUADS[sq] if c in self.roster]) for sq in SQUADS]
            grouped = [(n, mm) for n, mm in grouped if mm]
            loose = [c for c in self.roster if not any(c in mm for _, mm in grouped)]
            if loose:
                grouped.append(("그 밖의 친구들", loose))
            for gname, mm in grouped:
                gm = rm.addMenu(gname) if len(grouped) > 1 and len(mm) > 1 else rm
                for c in mm:
                    act = gm.addAction(f"{self.chars[c]['label']} 부르기")
                    act.setCheckable(True); act.setChecked(c in self.team)
                    act.triggered.connect(lambda _=False, c=c: self.toggle_member(c))
        if self.one_each and self.team:
            absent = [c for c in self.live_team() if not any(b.char == c for b in self.buddies)]
            if absent:
                cm = m.addMenu("외출한 친구 부르기")
                cm.addAction("모두 다 부르기", lambda: [QTimer.singleShot(i * 500, lambda c=c: self.add(None, "drop", c))
                                                     for i, c in enumerate([c for c in self.team
                                                                            if not any(b.char == c for b in self.buddies)])])
                cm.addSeparator()
                for c in absent:
                    sc = cm.addMenu(self.chars[c]["label"])
                    for t, ent in [("하늘에서 뚝", "drop"), ("바닥에서 빼꼼", "peek"), ("우산 타고", "umbrella"), ("밧줄 타고", "rope")]:
                        sc.addAction(t, lambda c=c, ent=ent: self.add(pos.x(), ent, c))
        if not self.one_each:
            cm = m.addMenu("부르기")
            for name in (self.team or [self.mode]):
                label = self.chars[name]["label"]
                sm_c = cm.addMenu(label) if len(self.team or [self.mode]) > 1 else cm
                for lab, ent in [("하늘에서", "drop"), ("바닥에서 빼꼼", "peek"), ("우산 타고", "umbrella"), ("밧줄 타고", "rope")]:
                    sm_c.addAction(lab, lambda ent=ent, name=name: self.add(pos.x(), ent, name))
            cm.addSeparator()
            cm.addAction("비 내리기 (8마리)", lambda: self.rain(8))
            cm.addAction("이 아이 보내기 (풍선/땅굴)", lambda: self.leave(who) if who.surface else self.remove(who))
            cm.addAction("절반 보내기", lambda: [self.remove() for _ in range(len(self.buddies) // 2)])
            if len(self.chars) > 1 and not self.team:
                mm = m.addMenu("캐릭터 바꾸기")
                for n, c in self.chars.items():
                    act = mm.addAction(c["label"], lambda n=n: self.switch_char(n))
                    act.setCheckable(True); act.setChecked(self.mode == n)
        if m.actions():
            m.addSeparator()
        # 2) 합동 장면 (그룹이 여럿이면 한 메뉴 안에 그룹별로)
        sqs = [sq for sq in self.scene_squads() if self.scenes_ok(sq)]
        if sqs:
            top = m.addMenu("합동 장면" if len(self.scene_sets) > 1 else "4인 합동 장면")
            for sq in sqs:
                sm2 = top.addMenu(f"{SQUAD_NAME[sq]}") if len(self.scene_sets) > 1 else top
                for lab, k in SCENE_MENU[sq]:
                    sm2.addAction(lab, lambda k=k, sq=sq: self.group_event("scene:%s:%s" % (sq, k), force=True))
        # 3) 같이 놀기: 단체 놀이 + 둘이 놀기 + 다 같이
        pl = m.addMenu("같이 놀기")
        self.plugin_interaction_menu(pl, who)
        touhou.add_group_menu(self, pl, who)
        if self.team and len(self.team) >= 3:
            for lab, k in [("기차놀이", "train"), ("인간 탑 쌓기", "tower"), ("단체사진 찰칵", "photo"),
                           ("손잡고 나란히", "hands"), ("수다 타임", "chat"), ("노래방", "karaoke")]:
                pl.addAction(lab, lambda k=k: self.group_event(k, force=True))
            pl.addSeparator()
        if self.team:
            for lab, k in [("술래잡기", "tag"), ("간식 나눠 먹기", "snack"), ("노래하고 춤추기", "dance"),
                           ("나란히 낮잠", "nap"), ("달려가서 인사", "greet")]:
                pl.addAction(lab, lambda k=k: self.duo_event(k, force=True))
            pl.addSeparator()
        if who is None:                                  # 캐릭터를 우클릭했을 땐 위쪽 "OO의 빼빼로 놀이"로
            if _pepero_day():  # 빼빼로 놀이는 11월 11일에만
                pl.addAction("빼빼로데이 놀이", lambda: self.pepero_event(force=True))
            pl.addAction(self.weather_label(), lambda: self.weather_event(force=True))
            _ev_menu_all(self, pl)  # 다 같이 이벤트 코스튬
        pl.addAction("숨바꼭질 (바닥에 숨은 애들 찾기)", self.hide_and_seek)
        pl.addAction("다 같이 하늘에서 떨어지기", self.all_drop)
        for lab, st, t, af in [("다 같이 만세!", "cheer", 90, None), ("다 같이 노래!", "sing", 300, None),
                               ("다 같이 춤!", "dance", 300, None), ("다 같이 재우기", "yawn", 90, "sleep")]:
            pl.addAction(lab, lambda st=st, t=t, af=af: [setattr(b, "vx", 0) or b.set(st, t, after=af)
                                                       for b in self.buddies if b.surface])
        # ── 여기부터 우클릭한 캐릭터 전용 메뉴 ──
        lab = self.chars[who.char]["label"]
        top.addSection(lab)
        ah = top.addAction(self.aff_text(who.char)); ah.setEnabled(False)
        top.addAction(f"{lab}에게 물어보기…", lambda: self.ask_claude(who))
        ofs = self.outfits.get(who.char, {})
        if len(ofs) > 1:                             # 옷 갈아입기는 우클릭 바로 아래 (한 번에 고르게)
            om = top.addMenu(f"{lab} 모습 바꾸기" if who.char in TRANSFORM else f"{lab} 옷 갈아입기")
            for of in ofs:
                a = om.addAction(OUTFIT_NAME.get(of, of), lambda of=of: self.set_outfit(who.char, of))
                a.setCheckable(True); a.setChecked(self.outfit.get(who.char) == of)
        wm = QMenu(f"{lab}이랑 놀기")              # 이 아이 전용 동작·이벤트는 한 칸 안으로
        self.plugin_menu(wm, who)
        touhou.add_pet_menu(self, wm, who)
        lst = self.chars[who.char].get("persona") or []
        if lst:
            pm = wm.addMenu("개성 동작")
            for i, it in enumerate(lst):
                pm.addAction(it[5][0], lambda i=i: self.force_persona(who, i))
        if who.has_frame(F["shoot_ready"]):
            wm.addAction("사격 개시! (뒷모습)", lambda: (self.ground(who), who.do_shoot()))
        if who.char in ("scarlet", "dorothy") and self.apple_pair():
            wm.addAction("홍북이의 사과 베기 (도로롱)", self.apple_cut)
        if who.char in ("blanc", "noir") and self.pole_pair():
            wm.addAction("블랑·누아르 폴댄스 쇼", self.pole_show)
        if who.char in ("blanc", "noir"):
            pc = wm.addAction("구석에서 계속 폴댄스", lambda: self.pole_corner_set(not self.cfg.get("pole_corner")))
            pc.setCheckable(True); pc.setChecked(bool(self.cfg.get("pole_corner")))
        if who.char in TRANSFORM and TRANSFORM[who.char]["alt"] in self.outfits.get(who.char, {}):
            alt_on = self.outfit.get(who.char) == TRANSFORM[who.char]["alt"]
            wm.addAction("변신 풀기" if alt_on else f"변신! ({OUTFIT_NAME.get(TRANSFORM[who.char]['alt'])})",
                          lambda: self.transform(who.char))
        _osong_menu(self, wm, who)  # 변신 노래 켜고 끄기
        _ev_menu(self, wm, who)  # 계절 이벤트 코스튬
        _dm = DMODE.get(f"{who.char}@{self.outfit.get(who.char)}")  # 도로시 모드 변신 (피나 전개 / 일반 모드)
        if _dm and who.has_frame(116):
            wm.addAction(_dm["menu"], lambda: self.dmode_play(who, force=True))
        if _pepero_day():
            wm.addAction(f"{lab}의 빼빼로 놀이", lambda: self.pepero_event(force=True, who=who))
        if self.one_each:
            wm.addAction("잠깐 외출 보내기", lambda: self.leave(who, travel=True) if who.surface else None)
        if wm.actions():
            top.addMenu(wm)
        top.addSeparator()
        if m.actions():
            top.addMenu(m)
        mu = top.addMenu("노래 틀기 ♪")
        for it in self.music_list():
            mu.addAction(it.get("name") or it.get("url"), lambda it=it: self.play_music(it))
        if len(self.music_list()) > 1:
            mu.addAction("아무거나 틀기", lambda: self.play_music())
        if getattr(self, "music_on", None):
            mu.addSeparator()
            if getattr(self, "yt_proc", None) and self.yt_proc.poll() is None:
                mu.addAction("플레이어 창 숨기기" if getattr(self, "yt_shown", False) else "플레이어 창 보기 (곡 넘기기·로그인)",
                             lambda: self.player_show(not getattr(self, "yt_shown", False)))
            mu.addAction(f"노래 끄기 ({self.music_on})", self.stop_music)
        mu.addSeparator()
        mu.addAction("노래 목록 편집…", lambda: self.open_settings("알림·노래"))
        rems = self.cfg.get("reminders", [])
        if rems:
            rm_ = top.addMenu(f"예약 알림 ({len(rems)})")
            for i, r in enumerate(rems):
                rm_.addAction(f"{r['label']}  {r['text'][:30]}  — 취소", lambda i=i: self.cancel_reminder(i))
        cm_ = top.addMenu("Claude")
        cm_.addAction("사용량 보기", self.open_usage)
        bm = cm_.addMenu("관심사 브리핑")
        bm.addAction("지금 브리핑 받기", lambda: self.start_briefing(force=True))
        bm.addAction("오늘 브리핑 보기", self.open_briefing)
        bon = bm.addAction("매일 자동으로 받기")
        bon.setCheckable(True); bon.setChecked(self.cfg.get("brief_on", False))
        bon.triggered.connect(lambda on: (self.cfg.__setitem__("brief_on", bool(on)), self.save_cfg()))
        bm.addAction("키워드·시간 설정…", lambda: self.open_settings("Claude"))
        top.addSeparator()
        self.passthru_menu(top)             # 터치 OFF · 투명도
        # 켜고 끄는 옵션(마중·수다·커서·항상 위·수면·제자리 …)은 환경설정 '화면·움직임' / 'AI 연결' 탭으로 옮김
        top.addAction("캐릭터 고르기 (받기·지우기)…", self.open_char_picker)
        top.addAction("환경설정…", self.open_settings)
        top.addAction("종료", self.qapp.quit)
        def _menus(mn, seen, par=None, act=None):
            if any(mn is s[0] for s in seen):
                return
            seen.append((mn, par, act))
            for ac in mn.actions():
                if ac.menu():
                    _menus(ac.menu(), seen, mn, ac)
        def _beside(mm, par, ac):
            """하위 메뉴는 언제나 그 항목 바로 옆에 (밑으로 떨어져 나가지 않게)"""
            try:
                if not (mm.isVisible() and par.isVisible()):
                    return
                r = par.actionGeometry(ac)
                y0 = par.mapToGlobal(r.topLeft()).y()
                pl = par.mapToGlobal(QPoint(0, 0)).x()
                pr = pl + par.width()
                sc = QApplication.screenAt(QPoint(pl, y0)) or QApplication.primaryScreen()
                g = sc.availableGeometry()
                w, h = mm.width(), mm.height()
                x = pr - 2 if pr - 2 + w <= g.right() + 1 else max(g.left(), pl - w + 2)
                y = max(g.top(), min(y0 - 4, g.bottom() + 1 - h))
                if abs(mm.x() - x) > 2 or abs(mm.y() - y) > 2:
                    mm.move(x, y)
            except Exception:
                pass
        allm = []
        _menus(top, allm)
        for mm, par, ac in allm:  # 메뉴(하위 메뉴 포함)는 캐릭터보다 위에
            if par is None:
                mm.setWindowFlag(Qt.WindowStaysOnTopHint, True)
            else:  # 하위 메뉴에 창 플래그를 다시 걸면 위치가 엉뚱해짐 → 맨 위는 raise_popups 가 맡고, 자리는 항목 옆으로
                mm.aboutToShow.connect(lambda mm=mm, par=par, ac=ac: QTimer.singleShot(0, lambda: _beside(mm, par, ac)))
            mm.aboutToShow.connect(lambda: QTimer.singleShot(0, self.raise_popups))
        # 맨 위 메뉴도 화면(작업표시줄 제외) 안에 다 보이게: 아래가 모자라면 위로 펼치고, 너무 길면 스크롤
        def _fit_top(mm, p):
            try:
                sc = QApplication.screenAt(p) or QApplication.primaryScreen()
                g = sc.availableGeometry()
                mm.ensurePolished()
                sh = mm.sizeHint()
                if sh.height() > g.height():
                    mm.setStyleSheet(mm.styleSheet() + " QMenu { menu-scrollable: 1; }")
                    mm.setMaximumHeight(g.height())
                    sh = mm.sizeHint()
                w, h = sh.width(), min(sh.height(), g.height())
                x = max(g.left(), min(p.x(), g.right() + 1 - w))
                y = p.y() if p.y() + h <= g.bottom() + 1 else p.y() - h
                y = max(g.top(), min(y, g.bottom() + 1 - h))
                return QPoint(x, y), g
            except Exception:
                return p, None
        mpos, _g = _fit_top(top, pos)
        def _keep_in(mm=top, g=_g):
            try:
                if g is None or not mm.isVisible():
                    return
                x = max(g.left(), min(mm.x(), g.right() + 1 - mm.width()))
                y = max(g.top(), min(mm.y(), g.bottom() + 1 - mm.height()))
                if x != mm.x() or y != mm.y():
                    mm.move(x, y)
            except Exception:
                pass
        top.aboutToShow.connect(lambda: QTimer.singleShot(0, _keep_in))
        QTimer.singleShot(0, self.raise_popups)
        top.exec_(mpos)

    def setup_tray(self):
        """작업표시줄 알림 영역 아이콘: 클릭하면 환경설정, 우클릭하면 메뉴"""
        try:
            from PyQt5.QtWidgets import QSystemTrayIcon
            from PyQt5.QtGui import QIcon
            if not QSystemTrayIcon.isSystemTrayAvailable():
                return
            ip = os.path.join(BASE, "icon.ico")
            icon = QIcon(ip) if os.path.exists(ip) else self.qapp.windowIcon()
            self.tray = QSystemTrayIcon(icon)
            self.tray.setToolTip(APP_NAME)
            tm = QMenu()
            tm.addAction("캐릭터 고르기 (받기·지우기)…", self.open_char_picker)
            tm.addAction("환경설정…", self.open_settings)
            self.passthru_tray(tm)
            st = tm.addAction("한 자리에 있기")
            st.setCheckable(True)
            tm.aboutToShow.connect(lambda: st.setChecked(bool(self.cfg.get("stay", False))))
            st.triggered.connect(lambda on: self.set_stay(on))
            sm = tm.addAction("수면 모드 (구석에서 자기)")
            sm.setCheckable(True)
            tm.aboutToShow.connect(lambda: sm.setChecked(bool(self.cfg.get("sleep_mode", False))))
            sm.triggered.connect(lambda on: self.set_sleep(on))
            rs = tm.addAction("제자리 모드 (그 자리에서 책·게임·뒹굴)")
            rs.setCheckable(True)
            tm.aboutToShow.connect(lambda: rs.setChecked(bool(self.cfg.get("rest_mode", False))))
            rs.triggered.connect(lambda on: self.set_rest(on))
            tm.addSeparator()
            tm.addAction("코덱무관플레이어", lambda: self.open_app("player"))
            tm.addAction("이름표 (이미지 파일명 편집기)", lambda: self.open_app("nametag"))
            tm.addAction("Claude 이력 관리…", self.open_claude_history)
            tm.addAction("Claude 사용량 보기", self.open_usage)
            tm.addSeparator()
            tm.addAction("종료", self.qapp.quit)
            self.tray_menu = tm
            self.tray.setContextMenu(tm)
            self.tray.activated.connect(lambda r: self.open_settings() if r in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick) else None)
            self.tray.show()
        except Exception as ex:
            _crash_write(f"\n트레이 아이콘을 못 만들었어요: {ex}\n")


    def open_settings(self, tab=None):
        d = self.settings_dlg
        try:
            if d is not None and d.isVisible():          # 이미 열려 있으면 앞으로만
                d.raise_(); d.activateWindow(); return
        except RuntimeError:                              # 지워진 창이면 새로 만듦
            pass
        if d is not None:
            try:
                d.deleteLater()
            except RuntimeError:
                pass
        try:
            self.settings_dlg = SettingsDialog(self)      # 열 때마다 지금 설정으로 새로 채움
        except Exception:
            import traceback
            msg = traceback.format_exc()
            _crash_write(f"\n[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] 환경설정 창 오류\n{msg}")
            self.settings_dlg = None
            try:
                from PyQt5.QtWidgets import QMessageBox
                QMessageBox.warning(None, APP_NAME, "환경설정 창을 여는 중 오류가 났어요.\n" + msg.strip().splitlines()[-1] + "\n(crash.log 에 자세히 적어 뒀어요)")
            except Exception:
                pass
            return
        if tab:
            try:
                tw = self.settings_dlg.tabs
                for i in range(tw.count()):
                    if tw.tabText(i) == tab:
                        tw.setCurrentIndex(i)
            except Exception:
                pass
        self.settings_dlg.show(); self.settings_dlg.raise_(); self.settings_dlg.activateWindow()
