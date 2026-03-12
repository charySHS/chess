from __future__ import annotations

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Ellipse, Line, RoundedRectangle
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import BooleanProperty, ListProperty, NumericProperty, ObjectProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.modalview import ModalView
from kivy.uix.scrollview import ScrollView
from kivy.uix.screenmanager import FadeTransition, Screen, ScreenManager
from kivy.uix.tabbedpanel import TabbedPanel

from src.ui.theme import Theme, build_theme, next_theme_name
from src.ui_kivy.controller import GameController


KV = """
<GlassCard@BoxLayout>:
    card_color: 1, 1, 1, 0.065
    canvas.before:
        Color:
            rgba: self.card_color
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [34, 34, 34, 34]
        Color:
            rgba: 1, 1, 1, 0.06
        Line:
            rounded_rectangle: (self.x + dp(1), self.y + dp(1), self.width - dp(2), self.height - dp(2), 34)
            width: 0.95

<GlassButton@Button>:
    background_normal: ""
    background_down: ""
    background_color: 0, 0, 0, 0
    color: 1, 1, 1, 1
    bold: False
    text_size: self.width - dp(26), None
    halign: "left"
    valign: "middle"
    canvas.before:
        Color:
            rgba: (1, 1, 1, 0.16) if self.state == "down" else (1, 1, 1, 0.055)
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [28, 28, 28, 28]
        Color:
            rgba: 1, 1, 1, 0.05
        Line:
            rounded_rectangle: (self.x + dp(1), self.y + dp(1), self.width - dp(2), self.height - dp(2), 28)
            width: 0.9

<InfoTabs@TabbedPanel>:
    do_default_tab: False
    tab_height: dp(34)
    tab_width: dp(112)
    background_color: 0, 0, 0, 0
    border: 0, 0, 0, 0
    strip_border: 0, 0, 0, 0
    strip_image: ""
    content_background: ""
    canvas.before:
        Color:
            rgba: 1, 1, 1, 0.05
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [24, 24, 24, 24]
        Color:
            rgba: 1, 1, 1, 0.08
        Line:
            rounded_rectangle: (self.x + dp(1), self.y + dp(1), self.width - dp(2), self.height - dp(2), 24)
            width: 1.0

<MenuScreen>:
    name: "menu"
    BoxLayout:
        orientation: "vertical"
        padding: dp(24), dp(22), dp(24), dp(18)
        spacing: dp(16)
        canvas.before:
            Color:
                rgba: app.background_rgba
            Rectangle:
                pos: self.pos
                size: self.size
            Color:
                rgba: app.secondary_rgba
            Ellipse:
                pos: self.width * 0.58, self.height * 0.52
                size: self.width * 0.34, self.width * 0.34
            Color:
                rgba: app.glow_rgba
            Ellipse:
                pos: self.width * 0.04, self.height * 0.70
                size: self.width * 0.22, self.width * 0.22
            Color:
                rgba: 1, 1, 1, 0.06
            Ellipse:
                pos: self.width * 0.72, self.height * 0.14
                size: self.width * 0.16, self.width * 0.16
        BoxLayout:
            size_hint_y: None
            height: dp(28)
            Label:
                text: app.atmosphere_tag
                color: 0.96, 0.98, 1, 0.9
                font_size: "13sp"
                bold: True
                halign: "left"
                text_size: self.size
        BoxLayout:
            orientation: "vertical" if app.compact_layout else "horizontal"
            spacing: dp(16)
            GlassCard:
                orientation: "vertical"
                padding: dp(26)
                spacing: dp(18)
                size_hint_x: 1 if app.compact_layout else 0.48
                size_hint_y: None if app.compact_layout else 1
                height: dp(452) if app.compact_layout else self.minimum_height
                card_color: 1, 1, 1, 0.05
                Label:
                    text: "NewChess"
                    size_hint_y: None
                    height: dp(62)
                    color: 1, 1, 1, 1
                    font_size: "38sp" if app.compact_layout else "46sp"
                    bold: False
                    halign: "left"
                    valign: "middle"
                    text_size: self.width, None
                Label:
                    text: app.hero_copy
                    size_hint_y: None
                    height: dp(74)
                    color: 0.94, 0.97, 1, 0.86
                    font_size: "17sp"
                    halign: "left"
                    valign: "top"
                    text_size: self.width, None
                Label:
                    text: "Quick Start"
                    size_hint_y: None
                    height: dp(22)
                    color: 0.95, 0.98, 1, 0.72
                    font_size: "13sp"
                    bold: True
                    halign: "left"
                    text_size: self.size
                GlassButton:
                    text: "Play Local Game\\nPass-and-play from one board with room to think."
                    size_hint_y: None
                    height: dp(58)
                    on_release: app.start_local_game()
                GlassButton:
                    text: "Play vs Engine\\nA focused solo room against the local engine."
                    size_hint_y: None
                    height: dp(58)
                    on_release: app.start_engine_game()
                GlassButton:
                    text: "Theme: " + root.theme_name + "\\nShift between sunlight, moonlight, and warm field tones."
                    size_hint_y: None
                    height: dp(58)
                    on_release: app.cycle_theme()
                Label:
                    text: "The shell stays light by keeping only the primary actions here."
                    size_hint_y: None
                    height: dp(22)
                    color: 0.94, 0.97, 1, 0.62
                    font_size: "13sp"
                    halign: "left"
                    text_size: self.size
                GlassButton:
                    text: "Quit\\nClose the app."
                    size_hint_y: None
                    height: dp(52)
                    on_release: app.stop()
            InfoTabs:
                size_hint_x: 1 if app.compact_layout else 0.52
                tab_pos: "top_mid"
                TabbedPanelItem:
                    text: "Overview"
                    BoxLayout:
                        orientation: "vertical"
                        padding: dp(18)
                        spacing: dp(12)
                        Label:
                            text: app.overview_copy
                            color: 0.95, 0.98, 1, 0.9
                            halign: "left"
                            valign: "top"
                            text_size: self.width, None
                        GlassCard:
                            padding: dp(14)
                            card_color: 1, 1, 1, 0.03
                            Label:
                                text: app.overview_subcopy
                                color: 0.94, 0.97, 1, 0.74
                                halign: "left"
                                valign: "top"
                                text_size: self.width, None
                TabbedPanelItem:
                    text: "Updates"
                    BoxLayout:
                        orientation: "vertical"
                        padding: dp(16)
                        spacing: dp(10)
                        GlassButton:
                            text: app.update_items[0]["title"] + "\\n" + app.update_items[0]["summary"]
                            size_hint_y: None
                            height: dp(74)
                            on_release: app.open_update(0)
                        GlassButton:
                            text: app.update_items[1]["title"] + "\\n" + app.update_items[1]["summary"]
                            size_hint_y: None
                            height: dp(74)
                            on_release: app.open_update(1)
                        GlassButton:
                            text: app.update_items[2]["title"] + "\\n" + app.update_items[2]["summary"]
                            size_hint_y: None
                            height: dp(74)
                            on_release: app.open_update(2)
                        Widget:
                TabbedPanelItem:
                    text: "Field Notes"
                    ScrollView:
                        do_scroll_x: False
                        bar_width: dp(4)
                        Label:
                            text: app.notes_copy
                            size_hint_y: None
                            height: self.texture_size[1]
                            padding: dp(18), dp(18)
                            color: 0.95, 0.98, 1, 0.84
                            halign: "left"
                            valign: "top"
                            text_size: self.width - dp(36), None
        Label:
            size_hint_y: None
            height: dp(18)
            text: "Tabs keep deeper notes available only when you want them."
            color: 0.95, 0.98, 1, 0.58
            font_size: "13sp"
            halign: "left"
            text_size: self.size

<GameScreen>:
    name: "game"
    BoxLayout:
        orientation: "vertical"
        padding: dp(18)
        spacing: dp(12)
        canvas.before:
            Color:
                rgba: app.background_rgba
            Rectangle:
                pos: self.pos
                size: self.size
            Color:
                rgba: app.secondary_rgba
            Ellipse:
                pos: self.width * 0.62, self.height * 0.46
                size: self.width * 0.34, self.width * 0.34
        GlassCard:
            size_hint_y: None
            height: dp(58)
            padding: dp(16)
            card_color: 1, 1, 1, 0.075
            Label:
                text: root.status_text
                color: 1, 1, 1, 1
                font_size: "17sp"
                halign: "left"
                valign: "middle"
                text_size: self.size
        BoxLayout:
            orientation: "vertical" if app.compact_layout else "horizontal"
            spacing: dp(12)
            BoxLayout:
                orientation: "vertical"
                size_hint_x: 1 if app.compact_layout else 0.68
                spacing: dp(10)
                ChessBoardView:
                    id: board_view
                    controller: root.controller
                    board_theme: app.theme
                    size_hint_y: None
                    height: self.width
                BoxLayout:
                    size_hint_y: None
                    height: dp(42)
                    spacing: dp(8)
                    GlassButton:
                        text: "Reset"
                        on_release: root.reset_board()
                    GlassButton:
                        text: "Undo"
                        on_release: root.undo_move()
                    GlassButton:
                        text: "Flip"
                        on_release: root.flip_board()
                    GlassButton:
                        text: "Menu"
                        on_release: app.show_menu()
            InfoTabs:
                size_hint_x: 1 if app.compact_layout else 0.32
                tab_pos: "top_mid"
                TabbedPanelItem:
                    text: "Overview"
                    BoxLayout:
                        orientation: "vertical"
                        padding: dp(16)
                        spacing: dp(10)
                        GlassCard:
                            orientation: "vertical"
                            padding: dp(14)
                            spacing: dp(8)
                            card_color: 1, 1, 1, 0.05
                            Label:
                                text: "Match"
                                size_hint_y: None
                                height: dp(22)
                                color: 1, 1, 1, 1
                                bold: True
                                halign: "left"
                                text_size: self.size
                            Label:
                                text: root.detail_text
                                color: 0.94, 0.97, 1, 0.84
                                halign: "left"
                                valign: "top"
                                text_size: self.width, None
                        GlassCard:
                            orientation: "vertical"
                            padding: dp(14)
                            spacing: dp(8)
                            card_color: 1, 1, 1, 0.04
                            Label:
                                text: "Captures"
                                size_hint_y: None
                                height: dp(22)
                                color: 1, 1, 1, 1
                                bold: True
                                halign: "left"
                                text_size: self.size
                            Label:
                                text: root.captures_text
                                color: 0.94, 0.97, 1, 0.84
                                halign: "left"
                                valign: "top"
                                text_size: self.width, None
                TabbedPanelItem:
                    text: "Analysis"
                    BoxLayout:
                        orientation: "vertical"
                        padding: dp(16)
                        spacing: dp(10)
                        GlassCard:
                            orientation: "vertical"
                            padding: dp(14)
                            spacing: dp(8)
                            card_color: 1, 1, 1, 0.05
                            Label:
                                text: "Engine"
                                size_hint_y: None
                                height: dp(22)
                                color: 1, 1, 1, 1
                                bold: True
                                halign: "left"
                                text_size: self.size
                            Label:
                                text: root.engine_text
                                color: 0.94, 0.97, 1, 0.84
                                halign: "left"
                                valign: "top"
                                text_size: self.width, None
                        GlassCard:
                            orientation: "vertical"
                            padding: dp(14)
                            spacing: dp(8)
                            card_color: 1, 1, 1, 0.04
                            Label:
                                text: "Review"
                                size_hint_y: None
                                height: dp(22)
                                color: 1, 1, 1, 1
                                bold: True
                                halign: "left"
                                text_size: self.size
                            Label:
                                text: root.review_text
                                color: 0.94, 0.97, 1, 0.84
                                halign: "left"
                                valign: "top"
                                text_size: self.width, None
                TabbedPanelItem:
                    text: "History"
                    ScrollView:
                        do_scroll_x: False
                        bar_width: dp(4)
                        Label:
                            text: root.moves_text
                            size_hint_y: None
                            height: self.texture_size[1]
                            padding: dp(18), dp(18)
                            color: 0.94, 0.97, 1, 0.84
                            halign: "left"
                            valign: "top"
                            text_size: self.width - dp(36), None
"""


def rgba(color: tuple[int, int, int] | tuple[int, int, int, int]) -> tuple[float, float, float, float]:
    if len(color) == 3:
        r, g, b = color
        a = 255
    else:
        r, g, b, a = color
    return (r / 255.0, g / 255.0, b / 255.0, a / 255.0)


class SquareButton(Button):
    square = NumericProperty(-1)
    highlighted = BooleanProperty(False)
    selected = BooleanProperty(False)
    is_light = BooleanProperty(True)
    board_theme = ObjectProperty(allownone=True)

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.background_normal = ""
        self.background_down = ""
        self.background_color = (0, 0, 0, 0)
        self.bold = True
        self.bind(
            pos=self._redraw,
            size=self._redraw,
            highlighted=self._redraw,
            selected=self._redraw,
            board_theme=self._redraw,
            is_light=self._redraw,
        )

    def _redraw(self, *_args) -> None:
        if self.board_theme is None:
            return
        base = self.board_theme.light_square if self.is_light else self.board_theme.dark_square
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*rgba(base))
            RoundedRectangle(pos=self.pos, size=self.size, radius=[10, 10, 10, 10])
            Color(1, 1, 1, 0.08)
            Line(rounded_rectangle=(self.x, self.y, self.width, self.height, 10), width=1.0)
            if self.highlighted:
                Color(*rgba(self.board_theme.legal_quiet_fill))
                RoundedRectangle(
                    pos=(self.x + dp(9), self.y + dp(9)),
                    size=(self.width - dp(18), self.height - dp(18)),
                    radius=[18, 18, 18, 18],
                )
            if self.selected:
                Color(*rgba((*self.board_theme.selected_outline, 255)))
                Line(
                    rounded_rectangle=(self.x + dp(5), self.y + dp(5), self.width - dp(10), self.height - dp(10), 12),
                    width=2.0,
                )


class ChessBoardView(GridLayout):
    controller = ObjectProperty(allownone=True)
    board_theme = ObjectProperty(allownone=True)

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.cols = 8
        self.spacing = dp(4)
        self.squares: list[SquareButton] = []
        for _ in range(64):
            button = SquareButton(font_size="34sp", color=(0.08, 0.1, 0.14, 1))
            button.bind(on_release=self._handle_press)
            self.squares.append(button)
            self.add_widget(button)
        self.bind(controller=self.refresh, board_theme=self.refresh, size=self._sync_font_sizes)

    def _sync_font_sizes(self, *_args) -> None:
        button_size = max(18, min(self.width / 15.5, 42))
        for button in self.squares:
            button.font_size = f"{button_size}sp"

    def _handle_press(self, button: SquareButton) -> None:
        if self.controller is None:
            return
        moved = self.controller.select_or_move(button.square)
        self.refresh()
        if self.controller.pending_promotion is not None:
            PromotionModal(self.controller, on_choose=self.refresh).open()
            return
        if moved and self.controller.result.is_over:
            self.refresh()

    def refresh(self, *_args) -> None:
        if self.controller is None or self.board_theme is None:
            return
        legal_targets = self.controller.legal_targets()
        self._sync_font_sizes()
        for index, square in enumerate(self.controller.display_squares()):
            button = self.squares[index]
            button.square = square
            button.text = self.controller.glyph_at(square)
            row = square // 8
            col = square % 8
            button.is_light = (row + col) % 2 == 0
            button.highlighted = square in legal_targets
            button.selected = square == self.controller.selected_square
            button.board_theme = self.board_theme


class PromotionModal(ModalView):
    def __init__(self, controller: GameController, on_choose, **kwargs) -> None:
        super().__init__(size_hint=(None, None), size=(dp(330), dp(150)), auto_dismiss=False, **kwargs)
        self.controller = controller
        self.on_choose = on_choose
        root = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(12))
        root.add_widget(Label(text="Choose Promotion", color=(1, 1, 1, 1), size_hint_y=None, height=dp(24)))
        row = BoxLayout(spacing=dp(10))
        for code in ("Q", "R", "B", "N"):
            button = Button(text=code)
            button.bind(on_release=self._choose)
            row.add_widget(button)
        root.add_widget(row)
        self.add_widget(root)

    def _choose(self, button: Button) -> None:
        self.controller.choose_promotion(button.text)
        self.dismiss()
        self.on_choose()


class UpdateDetailModal(ModalView):
    def __init__(self, item: dict[str, str | tuple[str, ...]], **kwargs) -> None:
        super().__init__(size_hint=(0.72, 0.72), auto_dismiss=True, **kwargs)
        root = BoxLayout(orientation="vertical", padding=dp(20), spacing=dp(14))
        title = Label(text=item["title"], color=(1, 1, 1, 1), size_hint_y=None, height=dp(34), font_size="24sp", bold=True, halign="left")
        title.bind(size=lambda instance, _value: setattr(instance, "text_size", instance.size))
        summary = Label(text=item["summary"], color=(0.94, 0.97, 1, 0.84), size_hint_y=None, height=dp(44), halign="left", valign="top")
        summary.bind(size=lambda instance, _value: setattr(instance, "text_size", (instance.width, None)))
        scroll = ScrollView(do_scroll_x=False, bar_width=dp(4))
        body = Label(text="\n\n".join(item["body"]), color=(0.94, 0.97, 1, 0.84), halign="left", valign="top", size_hint_y=None)
        body.bind(width=lambda instance, value: setattr(instance, "text_size", (value, None)))
        body.bind(texture_size=lambda instance, value: setattr(instance, "height", value[1]))
        scroll.add_widget(body)
        close_button = Button(text="Close", size_hint_y=None, height=dp(42))
        close_button.bind(on_release=lambda *_args: self.dismiss())
        root.add_widget(title)
        root.add_widget(summary)
        root.add_widget(scroll)
        root.add_widget(close_button)
        self.add_widget(root)


class MenuScreen(Screen):
    theme_name = StringProperty("")


class GameScreen(Screen):
    controller = ObjectProperty(allownone=True)
    status_text = StringProperty("")
    detail_text = StringProperty("")
    engine_text = StringProperty("")
    review_text = StringProperty("")
    captures_text = StringProperty("")
    moves_text = StringProperty("")

    def refresh(self) -> None:
        if self.controller is None:
            return
        self.status_text = self.controller.status_text()
        self.detail_text = "\n".join(self.controller.detail_lines())
        self.engine_text = "\n".join(self.controller.engine_lines())
        self.review_text = self.controller.review_text()
        self.captures_text = self.controller.captures_text()
        self.moves_text = "\n".join(self.controller.move_rows()[-18:]) or "1. --"
        self.ids.board_view.refresh()

    def reset_board(self) -> None:
        self.controller.reset_board()
        self.refresh()

    def undo_move(self) -> None:
        self.controller.undo_last_move()
        self.refresh()

    def flip_board(self) -> None:
        self.controller.toggle_flip()
        self.refresh()

    def show_menu(self) -> None:
        self.manager.current = "menu"


class KivyRoot(ScreenManager):
    app = ObjectProperty(allownone=True)


class NewChessKivyApp(App):
    background_rgba = ListProperty([0.0, 0.0, 0.0, 1.0])
    secondary_rgba = ListProperty([0.0, 0.0, 0.0, 0.0])
    glow_rgba = ListProperty([0.0, 0.0, 0.0, 0.0])
    compact_layout = BooleanProperty(False)
    atmosphere_tag = StringProperty("")
    hero_copy = StringProperty("")
    overview_copy = StringProperty("")
    overview_subcopy = StringProperty("")
    notes_copy = StringProperty("")

    def __init__(self, theme: Theme, **kwargs) -> None:
        super().__init__(**kwargs)
        if Window is not None:
            Window.minimum_width = 940
            Window.minimum_height = 720
            Window.size = (1280, 860)
            Window.bind(size=self._handle_window_resize)
        self.theme = theme
        self.controller = GameController()
        self.root_manager: KivyRoot | None = None
        self.update_items = [
            {
                "title": "Liquid glass atmosphere",
                "summary": "The shell is moving toward a softer meadow daylight or moonlit calm mood.",
                "body": (
                    "The idea is to make the app feel luminous and open without becoming glossy noise.",
                    "Daylight themes should feel like air, grass, and warm glass. Night themes should feel quiet, silver-blue, and spacious.",
                    "The visual system should stay simple enough that the chessboard still feels like the center of gravity.",
                ),
            },
            {
                "title": "Less clutter, more layers",
                "summary": "Dense sidebars are being replaced by tabs and quieter information grouping.",
                "body": (
                    "Instead of showing every category at once, the Kivy UI now keeps deeper detail in tabs you can open intentionally.",
                    "That keeps the first impression calmer while still preserving access to engine notes, history, and design context.",
                    "This is a better fit for a refined desktop app than stacking five small cards beside the board.",
                ),
            },
            {
                "title": "Responsive shell",
                "summary": "The layout now adapts more gracefully as the window changes width.",
                "body": (
                    "On narrower windows, the menu and game screens collapse into vertical compositions instead of forcing a rigid desktop split.",
                    "The chessboard remains square and the supporting information moves into a secondary column or stacked tabs depending on width.",
                    "This keeps the app usable while giving you more room to continue polishing the visual language later.",
                ),
            },
        ]
        self._sync_palette()
        self._handle_window_resize(Window, Window.size if Window is not None else (1280, 860))

    def build(self):
        Builder.load_string(KV)
        manager = KivyRoot(transition=FadeTransition(duration=0.18))
        manager.app = self
        menu = MenuScreen()
        menu.theme_name = self.theme.name.title()
        game = GameScreen()
        game.controller = self.controller
        manager.add_widget(menu)
        manager.add_widget(game)
        self.root_manager = manager
        Clock.schedule_interval(self._tick, 1 / 12)
        return manager

    def on_start(self) -> None:
        self._refresh_views()

    def start_local_game(self) -> None:
        self.show_game("local")

    def start_engine_game(self) -> None:
        self.show_game("engine")

    def show_menu(self) -> None:
        if self.root_manager is not None:
            self.root_manager.current = "menu"

    def show_game(self, mode: str) -> None:
        self.controller.configure_mode(mode)
        self.root_manager.current = "game"
        self._refresh_views()

    def cycle_theme(self) -> None:
        self.theme = build_theme(next_theme_name(self.theme.name))
        self._sync_palette()
        if self.root_manager is not None:
            self.root_manager.get_screen("menu").theme_name = self.theme.name.title()
            self.root_manager.get_screen("game").ids.board_view.board_theme = self.theme
        self._refresh_views()

    def open_update(self, index: int) -> None:
        UpdateDetailModal(self.update_items[index]).open()

    def _tick(self, _dt: float) -> None:
        if self.root_manager is None:
            return
        if self.root_manager.current == "game" and self.controller.maybe_make_engine_move():
            self._refresh_views()

    def _refresh_views(self) -> None:
        if self.root_manager is None:
            return
        self.root_manager.get_screen("menu").theme_name = self.theme.name.title()
        self.root_manager.get_screen("game").ids.board_view.board_theme = self.theme
        self.root_manager.get_screen("game").refresh()

    def _handle_window_resize(self, _window, size) -> None:
        width, _height = size
        self.compact_layout = width < 1180

    def _sync_palette(self) -> None:
        presets = {
            "glass": {
                "background": (0.67, 0.76, 0.56, 1.0),
                "secondary": (1.0, 0.95, 0.77, 0.18),
                "glow": (1.0, 1.0, 1.0, 0.16),
                "tag": "SUNLIT MEADOW",
                "hero": "A bright, airy chess room with liquid-glass surfaces and softer structure.",
                "overview": "Glass remains present, but the mood is now closer to open daylight than generic dark tech. Primary controls stay near at hand; deeper notes live in tabs when you want them.",
                "subcopy": "This should feel elegant first, modern second, and only then technical.",
                "notes": "Field Notes\n\nThe daylight look should read as grass, warm air, and reflective glass rather than a synthetic blue dashboard.\n\nDocumentation belongs in the tabs, not sprayed across the surface.\n\nThe board should remain the anchor point even when the shell gets more atmospheric.",
            },
            "midnight": {
                "background": (0.15, 0.20, 0.31, 1.0),
                "secondary": (0.78, 0.83, 1.0, 0.16),
                "glow": (0.93, 0.95, 1.0, 0.10),
                "tag": "MOONLIT FIELD",
                "hero": "A quieter shell for night play, silver-blue and calm without losing clarity.",
                "overview": "The moonlit look keeps the same structure but shifts the emotional tone toward stillness and focus. Tabs preserve clarity by tucking away secondary detail until you ask for it.",
                "subcopy": "The goal is a nocturnal version of the same meadow atmosphere, not a loud gamer dark mode.",
                "notes": "Field Notes\n\nMoonlight should feel soft and directional, not flat. Borders should fade, controls should hover, and the board should read almost like porcelain under cool light.\n\nThe interface should stay readable from the first glance even when the palette goes darker.",
            },
            "ivory": {
                "background": (0.84, 0.76, 0.62, 1.0),
                "secondary": (1.0, 0.94, 0.88, 0.18),
                "glow": (1.0, 1.0, 1.0, 0.12),
                "tag": "GOLDEN FIELD",
                "hero": "A warmer meadow palette with parchment light and softer contrast.",
                "overview": "Ivory is the warm-weather companion to the clear glass look. It trims harsh contrast and keeps the shell approachable and tactile.",
                "subcopy": "This one should feel lived-in and elegant rather than glossy and pristine.",
                "notes": "Field Notes\n\nThis warm palette is useful when the colder clear-glass mood feels too sterile. The same structure stays in place, but the atmosphere becomes softer and more human.\n\nIt should still read as one product family with the daylight and moonlight versions.",
            },
        }
        palette = presets.get(self.theme.name, presets["glass"])
        self.background_rgba = list(palette["background"])
        self.secondary_rgba = list(palette["secondary"])
        self.glow_rgba = list(palette["glow"])
        self.atmosphere_tag = palette["tag"]
        self.hero_copy = palette["hero"]
        self.overview_copy = palette["overview"]
        self.overview_subcopy = palette["subcopy"]
        self.notes_copy = palette["notes"]


def run_kivy_app(theme: Theme) -> None:
    NewChessKivyApp(theme=theme).run()
