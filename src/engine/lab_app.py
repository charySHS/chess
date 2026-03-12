from __future__ import annotations

import queue
import threading
import traceback
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

from src.config import AppConfig
from src.engine.lab import LabConfig, LabSummary, default_history_path, load_history_entries, run_lab_cycle
from src.engine.profile import current_engine_profile, default_snapshot_path, load_engine_profile


PIECE_GLYPHS = {
    "K": "K",
    "Q": "Q",
    "R": "R",
    "B": "B",
    "N": "N",
    "P": "P",
    "k": "k",
    "q": "q",
    "r": "r",
    "b": "b",
    "n": "n",
    "p": "p",
}


class EngineLabApp:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("NewChess Engine Lab")
        self.root.geometry("1160x780")
        self.root.minsize(980, 680)

        self.app_config = AppConfig()
        self.message_queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self.worker: threading.Thread | None = None
        self.running = False

        self.snapshot_var = tk.StringVar(value=str(default_snapshot_path()))
        self.snapshot_name_var = tk.StringVar(value="baseline_v1")
        self.training_data_var = tk.StringVar(value=str(self.app_config.training_data_path))
        self.model_output_var = tk.StringVar(value=str(self.app_config.model_path))
        self.depth_var = tk.IntVar(value=2)
        self.rating_games_var = tk.IntVar(value=4)
        self.selfplay_games_var = tk.IntVar(value=6)
        self.max_plies_var = tk.IntVar(value=80)
        self.take_snapshot_var = tk.BooleanVar(value=False)
        self.train_model_var = tk.BooleanVar(value=False)

        self.status_var = tk.StringVar(value="Idle")
        self.rating_var = tk.StringVar(value="Rating: --")
        self.selfplay_var = tk.StringVar(value="Self-play: --")
        self.training_var = tk.StringVar(value="Training: --")
        self.live_game_var = tk.StringVar(value="Live Board: waiting")
        self.last_move_var = tk.StringVar(value="Last Move: --")
        self.history_path = default_history_path()
        self.history_entries = load_history_entries(self.history_path)
        self.current_fen = "8/8/8/8/8/8/8/8 w - - 0 1"

        self._build_ui()
        self._redraw_board()
        self._redraw_charts()
        self.root.after(120, self._poll_messages)

    def run(self) -> None:
        self.root.mainloop()

    def _build_ui(self) -> None:
        self.root.configure(bg="#11151c")
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TFrame", background="#11151c")
        style.configure("Panel.TFrame", background="#182030")
        style.configure("TLabel", background="#11151c", foreground="#f1eadf")
        style.configure("Panel.TLabel", background="#182030", foreground="#f1eadf")
        style.configure("Heading.TLabel", font=("Avenir Next", 20, "bold"), background="#11151c", foreground="#f7f0e5")
        style.configure("Subtle.TLabel", background="#11151c", foreground="#c2b8a9")
        style.configure("Accent.TButton", padding=8)
        style.configure("TCheckbutton", background="#182030", foreground="#f1eadf")

        container = ttk.Frame(self.root)
        container.pack(fill=tk.BOTH, expand=True, padx=18, pady=18)
        container.columnconfigure(0, weight=0)
        container.columnconfigure(1, weight=1)
        container.rowconfigure(0, weight=1)

        controls = ttk.Frame(container, style="Panel.TFrame", padding=18)
        controls.grid(row=0, column=0, sticky="nsew", padx=(0, 14))

        dashboard = ttk.Frame(container, style="Panel.TFrame", padding=18)
        dashboard.grid(row=0, column=1, sticky="nsew")
        dashboard.columnconfigure(0, weight=1)
        dashboard.columnconfigure(1, weight=1)
        dashboard.rowconfigure(2, weight=1)
        dashboard.rowconfigure(3, weight=1)

        ttk.Label(controls, text="Engine Lab", style="Heading.TLabel").pack(anchor="w")
        ttk.Label(
            controls,
            text="Snapshot, rate, self-play, and train from one local runner.",
            style="Subtle.TLabel",
            wraplength=280,
        ).pack(anchor="w", pady=(4, 18))

        self._path_row(controls, "Snapshot", self.snapshot_var, self._choose_snapshot_path)
        self._entry_row(controls, "Snapshot Name", self.snapshot_name_var)
        self._path_row(controls, "Training Data", self.training_data_var, self._choose_training_path)
        self._path_row(controls, "Model Output", self.model_output_var, self._choose_model_output_path)
        self._spin_row(controls, "Search Depth", self.depth_var, 1, 6)
        self._spin_row(controls, "Rating Games", self.rating_games_var, 1, 100)
        self._spin_row(controls, "Self-play Games", self.selfplay_games_var, 1, 200)
        self._spin_row(controls, "Max Plies", self.max_plies_var, 20, 400)

        options = ttk.Frame(controls, style="Panel.TFrame")
        options.pack(fill=tk.X, pady=(10, 18))
        ttk.Checkbutton(options, text="Take fresh snapshot first", variable=self.take_snapshot_var).pack(anchor="w")
        ttk.Checkbutton(options, text="Train value network after self-play", variable=self.train_model_var).pack(anchor="w", pady=(6, 0))

        actions = ttk.Frame(controls, style="Panel.TFrame")
        actions.pack(fill=tk.X)
        self.run_button = ttk.Button(actions, text="Run Lab Cycle", command=self._start_cycle, style="Accent.TButton")
        self.run_button.pack(fill=tk.X)
        ttk.Button(actions, text="Clear Log", command=self._clear_log).pack(fill=tk.X, pady=(8, 0))

        ttk.Label(dashboard, textvariable=self.status_var, style="Heading.TLabel").grid(row=0, column=0, columnspan=2, sticky="w")

        summary = ttk.Frame(dashboard, style="Panel.TFrame")
        summary.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(12, 14))
        for idx in range(3):
            summary.columnconfigure(idx, weight=1)
        self._summary_card(summary, 0, "Rating", self.rating_var)
        self._summary_card(summary, 1, "Self-play", self.selfplay_var)
        self._summary_card(summary, 2, "Training", self.training_var)

        board_frame = ttk.Frame(dashboard, style="Panel.TFrame")
        board_frame.grid(row=2, column=0, sticky="nsew", padx=(0, 10))
        board_frame.columnconfigure(0, weight=1)
        board_frame.rowconfigure(2, weight=1)
        ttk.Label(board_frame, textvariable=self.live_game_var, style="Panel.TLabel", font=("Avenir Next", 14, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(board_frame, textvariable=self.last_move_var, style="Panel.TLabel").grid(row=1, column=0, sticky="w", pady=(4, 10))
        self.board_canvas = tk.Canvas(board_frame, width=360, height=360, bg="#101724", highlightthickness=0)
        self.board_canvas.grid(row=2, column=0, sticky="nsew")

        charts_frame = ttk.Frame(dashboard, style="Panel.TFrame")
        charts_frame.grid(row=2, column=1, sticky="nsew")
        charts_frame.columnconfigure(0, weight=1)
        charts_frame.rowconfigure(1, weight=1)
        charts_frame.rowconfigure(3, weight=1)
        ttk.Label(charts_frame, text="Run Charts", style="Panel.TLabel", font=("Avenir Next", 14, "bold")).grid(row=0, column=0, sticky="w")
        self.elo_canvas = tk.Canvas(charts_frame, width=360, height=170, bg="#101724", highlightthickness=0)
        self.elo_canvas.grid(row=1, column=0, sticky="nsew", pady=(8, 10))
        ttk.Label(charts_frame, text="Recent Runs", style="Panel.TLabel", font=("Avenir Next", 12, "bold")).grid(row=2, column=0, sticky="w")
        self.history_list = tk.Listbox(
            charts_frame,
            background="#0f1624",
            foreground="#f0eadf",
            highlightthickness=0,
            borderwidth=0,
            font=("Menlo", 10),
        )
        self.history_list.grid(row=3, column=0, sticky="nsew", pady=(8, 0))

        log_frame = ttk.Frame(dashboard, style="Panel.TFrame")
        log_frame.grid(row=3, column=0, columnspan=2, sticky="nsew", pady=(14, 0))
        log_frame.rowconfigure(1, weight=1)
        log_frame.columnconfigure(0, weight=1)
        ttk.Label(log_frame, text="Live Log", style="Panel.TLabel", font=("Avenir Next", 14, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 10))
        self.log = scrolledtext.ScrolledText(
            log_frame,
            wrap=tk.WORD,
            font=("Menlo", 11),
            background="#0f1624",
            foreground="#f0eadf",
            insertbackground="#f0eadf",
            relief=tk.FLAT,
            padx=12,
            pady=12,
        )
        self.log.grid(row=1, column=0, sticky="nsew")
        self.log.insert(tk.END, "Ready.\n")
        self.log.configure(state=tk.DISABLED)

    def _path_row(self, parent: ttk.Frame, label: str, variable: tk.StringVar, command) -> None:
        ttk.Label(parent, text=label, style="Panel.TLabel").pack(anchor="w")
        row = ttk.Frame(parent, style="Panel.TFrame")
        row.pack(fill=tk.X, pady=(4, 10))
        ttk.Entry(row, textvariable=variable).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(row, text="Browse", command=command).pack(side=tk.LEFT, padx=(8, 0))

    def _entry_row(self, parent: ttk.Frame, label: str, variable: tk.StringVar) -> None:
        ttk.Label(parent, text=label, style="Panel.TLabel").pack(anchor="w")
        ttk.Entry(parent, textvariable=variable).pack(fill=tk.X, pady=(4, 10))

    def _spin_row(self, parent: ttk.Frame, label: str, variable: tk.IntVar, start: int, end: int) -> None:
        ttk.Label(parent, text=label, style="Panel.TLabel").pack(anchor="w")
        ttk.Spinbox(parent, from_=start, to=end, textvariable=variable, width=8).pack(anchor="w", pady=(4, 10))

    def _summary_card(self, parent: ttk.Frame, column: int, title: str, value_var: tk.StringVar) -> None:
        card = ttk.Frame(parent, style="Panel.TFrame", padding=14)
        card.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 8, 0))
        ttk.Label(card, text=title, style="Panel.TLabel", font=("Avenir Next", 12, "bold")).pack(anchor="w")
        ttk.Label(card, textvariable=value_var, style="Panel.TLabel", wraplength=220).pack(anchor="w", pady=(6, 0))

    def _choose_snapshot_path(self) -> None:
        path = filedialog.asksaveasfilename(initialfile=Path(self.snapshot_var.get()).name or "baseline_v1.json", defaultextension=".json")
        if path:
            self.snapshot_var.set(path)

    def _choose_training_path(self) -> None:
        path = filedialog.asksaveasfilename(initialfile=Path(self.training_data_var.get()).name or "selfplay.jsonl", defaultextension=".jsonl")
        if path:
            self.training_data_var.set(path)

    def _choose_model_output_path(self) -> None:
        path = filedialog.asksaveasfilename(initialfile=Path(self.model_output_var.get()).name or "value_network.npz", defaultextension=".npz")
        if path:
            self.model_output_var.set(path)

    def _clear_log(self) -> None:
        self.log.configure(state=tk.NORMAL)
        self.log.delete("1.0", tk.END)
        self.log.configure(state=tk.DISABLED)

    def _append_log(self, text: str) -> None:
        self.log.configure(state=tk.NORMAL)
        self.log.insert(tk.END, text.rstrip() + "\n")
        self.log.see(tk.END)
        self.log.configure(state=tk.DISABLED)

    def _redraw_board(self) -> None:
        self.board_canvas.delete("all")
        width = int(self.board_canvas.winfo_width() or 360)
        height = int(self.board_canvas.winfo_height() or 360)
        size = min(width, height)
        square = size / 8
        placement = self.current_fen.split()[0]
        pieces: list[str] = []
        for row in placement.split("/"):
            for ch in row:
                if ch.isdigit():
                    pieces.extend(["."] * int(ch))
                else:
                    pieces.append(ch)

        light = "#f2eadf"
        dark = "#c4ab89"
        for idx, piece in enumerate(pieces[:64]):
            row = idx // 8
            col = idx % 8
            x0 = col * square
            y0 = row * square
            color = light if (row + col) % 2 == 0 else dark
            self.board_canvas.create_rectangle(x0, y0, x0 + square, y0 + square, fill=color, width=0)
            if piece != ".":
                self.board_canvas.create_text(
                    x0 + square / 2,
                    y0 + square / 2,
                    text=PIECE_GLYPHS.get(piece, piece),
                    fill="#1c2330" if piece.isupper() else "#7b1f1f",
                    font=("Avenir Next", int(square * 0.42), "bold"),
                )

    def _redraw_charts(self) -> None:
        self._draw_elo_chart()
        self._draw_history_list()

    def _draw_elo_chart(self) -> None:
        self.elo_canvas.delete("all")
        width = int(self.elo_canvas.winfo_width() or 360)
        height = int(self.elo_canvas.winfo_height() or 170)
        self.elo_canvas.create_rectangle(0, 0, width, height, fill="#101724", width=0)
        entries = self.history_entries[-20:]
        if not entries:
            self.elo_canvas.create_text(width / 2, height / 2, text="No run history yet", fill="#c2b8a9", font=("Avenir Next", 13))
            return

        values = [entry.estimated_elo_diff for entry in entries]
        sample_values = [entry.selfplay_samples for entry in entries]
        min_v = min(values + [0.0])
        max_v = max(values + [0.0])
        if abs(max_v - min_v) < 1e-6:
            max_v += 1.0
            min_v -= 1.0

        margin = 24
        chart_w = width - margin * 2
        chart_h = height - margin * 2
        self.elo_canvas.create_text(14, 12, text="Elo diff", anchor="w", fill="#f0eadf", font=("Avenir Next", 11, "bold"))
        self.elo_canvas.create_text(width - 14, 12, text="Samples", anchor="e", fill="#d2b176", font=("Avenir Next", 11, "bold"))

        points = []
        for idx, value in enumerate(values):
            x = margin + (chart_w * idx / max(1, len(values) - 1))
            ratio = (value - min_v) / (max_v - min_v)
            y = margin + chart_h * (1.0 - ratio)
            points.append((x, y))
        for idx in range(1, len(points)):
            self.elo_canvas.create_line(*points[idx - 1], *points[idx], fill="#79c1ff", width=2)
        for x, y in points:
            self.elo_canvas.create_oval(x - 3, y - 3, x + 3, y + 3, fill="#79c1ff", outline="")

        max_samples = max(sample_values) if sample_values else 1
        for idx, samples in enumerate(sample_values):
            x = margin + (chart_w * idx / max(1, len(sample_values) - 1))
            bar_height = (samples / max_samples) * 36 if max_samples else 0
            self.elo_canvas.create_line(x, height - margin, x, height - margin - bar_height, fill="#d2b176", width=4)

    def _draw_history_list(self) -> None:
        self.history_list.delete(0, tk.END)
        for entry in self.history_entries[-12:][::-1]:
            label = (
                f"{entry.timestamp[5:16]}  elo {entry.estimated_elo_diff:>6.1f}  "
                f"samples {entry.selfplay_samples:>4d}  d{entry.depth}"
            )
            self.history_list.insert(tk.END, label)

    def _start_cycle(self) -> None:
        if self.running:
            return
        snapshot_path = Path(self.snapshot_var.get())
        if not snapshot_path.exists() and not self.take_snapshot_var.get():
            messagebox.showerror("Missing snapshot", "Snapshot profile does not exist. Enable 'Take fresh snapshot first' or choose an existing file.")
            return

        self.running = True
        self.run_button.state(["disabled"])
        self.status_var.set("Running lab cycle")
        self.rating_var.set("Rating: running")
        self.selfplay_var.set("Self-play: running")
        self.training_var.set("Training: queued" if self.train_model_var.get() else "Training: skipped")
        self._append_log("Starting lab cycle")
        self.live_game_var.set("Live Board: waiting for first position")
        self.last_move_var.set("Last Move: --")

        config = LabConfig(
            snapshot_path=snapshot_path,
            training_data_path=Path(self.training_data_var.get()),
            model_output_path=Path(self.model_output_var.get()),
            depth=self.depth_var.get(),
            rating_games=self.rating_games_var.get(),
            selfplay_games=self.selfplay_games_var.get(),
            max_plies=self.max_plies_var.get(),
            snapshot_name=self.snapshot_name_var.get().strip() or "baseline_v1",
            take_snapshot=self.take_snapshot_var.get(),
            train_model=self.train_model_var.get(),
        )

        snapshot_profile = load_engine_profile(snapshot_path) if snapshot_path.exists() else None

        def worker() -> None:
            try:
                summary = run_lab_cycle(
                    config,
                    snapshot_profile or current_engine_profile("bootstrap"),
                    progress=lambda msg: self.message_queue.put(("log", msg)),
                    event_callback=lambda event: self.message_queue.put(("event", event)),
                )
            except Exception as exc:  # pragma: no cover - UI path
                self.message_queue.put(("error", "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))))
            else:
                self.message_queue.put(("summary", summary))

        self.worker = threading.Thread(target=worker, daemon=True)
        self.worker.start()

    def _poll_messages(self) -> None:
        try:
            while True:
                kind, payload = self.message_queue.get_nowait()
                if kind == "log":
                    self._append_log(str(payload))
                elif kind == "event":
                    self._handle_event(payload)
                elif kind == "summary":
                    self._handle_summary(payload)
                elif kind == "error":
                    self._handle_error(str(payload))
        except queue.Empty:
            pass
        self.root.after(120, self._poll_messages)

    def _handle_summary(self, summary: LabSummary) -> None:
        self.running = False
        self.run_button.state(["!disabled"])
        self.status_var.set("Lab cycle complete")
        self.rating_var.set(
            f"Rating: {summary.rating.score:.1f}/{summary.rating.games} "
            f"(avg {summary.rating.average:.3f}, elo {summary.rating.estimated_elo_diff:.1f})"
        )
        self.selfplay_var.set(
            f"Self-play: {summary.selfplay.samples_written} samples -> {summary.selfplay.output_path.name}"
        )
        if summary.training is None:
            self.training_var.set("Training: skipped")
        else:
            self.training_var.set(
                f"Training: loss {summary.training.final_loss:.6f} -> {summary.training.output_path.name}"
            )
        self.history_entries = load_history_entries(summary.history_path)
        self._redraw_charts()
        self._append_log("Lab cycle complete")

    def _handle_error(self, payload: str) -> None:
        self.running = False
        self.run_button.state(["!disabled"])
        self.status_var.set("Lab cycle failed")
        self._append_log(payload)
        messagebox.showerror("Engine lab failed", payload)

    def _handle_event(self, payload: object) -> None:
        if not isinstance(payload, dict):
            return
        event_type = payload.get("type")
        if event_type == "board":
            self.current_fen = str(payload.get("fen", self.current_fen))
            stage = str(payload.get("stage", "run")).title()
            game_index = payload.get("game_index", 0)
            games = payload.get("games", 0)
            self.live_game_var.set(f"Live Board: {stage} {game_index}/{games}")
            self.last_move_var.set(
                f"Last Move: {payload.get('last_move', '--')}  |  Ply {payload.get('ply', '--')}"
            )
            self._redraw_board()
        elif event_type == "history_updated":
            self.history_entries = load_history_entries(Path(str(payload.get("path", self.history_path))))
            self._redraw_charts()


def run_engine_lab_app() -> None:
    EngineLabApp().run()
