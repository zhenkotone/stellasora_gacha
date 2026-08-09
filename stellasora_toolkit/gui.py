from __future__ import annotations

import argparse
import json
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Any

from PIL import Image, ImageDraw, ImageOps, ImageTk

from .app_updater import UPDATE_MANIFEST_URL, AppUpdate, check_for_update, download_update
from .catalog import (
    format_random_attr,
    gacha_item_name,
    gem_type_name,
    register_gacha_resource,
    table_values,
    traveler_name,
)
from .resource_manager import DEFAULT_MANIFEST_URL, update_resources
from .service import Snapshot, extract_snapshot, load_latest_snapshot
from .gacha_stats import (
    CATEGORY_DISC_LIMITED,
    CATEGORY_DISC_STANDARD,
    CATEGORY_TRAVELER_LIMITED,
    CATEGORY_TRAVELER_STANDARD,
    PoolStats,
    build_category_stat,
    build_pool_stats,
    classify_history_category,
)


BG = "#eaf2f8"
PANEL = "#fdfefe"
INK = "#31445b"
MUTED = "#71839a"
LINE = "#cfdae6"
ACCENT = "#5a89a7"
ACCENT_DARK = "#476d8b"
WARM = "#c58b68"
HEADER = "#607d98"
POOL_COLORS = ("#7776aa", "#4d9ba0", "#5d82a9", "#8e6d9c")
APP_VERSION = "1.1.4"
GACHA_CATEGORY_ORDER = (
    CATEGORY_TRAVELER_LIMITED,
    CATEGORY_DISC_LIMITED,
    CATEGORY_TRAVELER_STANDARD,
    CATEGORY_DISC_STANDARD,
)
GACHA_CATEGORY_NAMES = {
    CATEGORY_TRAVELER_LIMITED: "旅人限时招募",
    CATEGORY_DISC_LIMITED: "秘纹限时招募",
    CATEGORY_TRAVELER_STANDARD: "旅人常驻招募",
    CATEGORY_DISC_STANDARD: "秘纹常驻招募",
}


class StellaSoraApp:
    def __init__(self, root: tk.Tk, output_dir: Path):
        self.root = root
        self.output_dir = output_dir
        self._cleanup_stale_update_files()
        self.snapshot: Snapshot | None = None
        self.events: queue.Queue[tuple[str, Any]] = queue.Queue()
        self.gacha_rows: dict[str, dict] = {}
        self.emblem_rows: dict[str, dict] = {}
        self.avatar_images: list[ImageTk.PhotoImage] = []
        self.pool_columns = tk.IntVar(value=self._load_pool_columns())
        self.busy = False
        self.update_checking = False

        self.root.title("星塔旅人数据工具")
        self._set_window_icon()
        self.root.geometry("1180x760")
        self.root.minsize(940, 620)
        self.root.configure(bg=BG)
        self._configure_styles()
        self._build_ui()
        self.root.after(100, self._poll_events)
        self._load_latest()
        if getattr(sys, "frozen", False):
            self.root.after(1600, lambda: self.check_app_update(silent=True))

    def _set_window_icon(self) -> None:
        resource_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
        icon_path = resource_root / "assets" / "app_icon.png"
        if not icon_path.exists():
            return
        try:
            self.app_icon = tk.PhotoImage(file=str(icon_path))
            self.root.iconphoto(True, self.app_icon)
        except tk.TclError:
            pass

    def _configure_styles(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("App.TFrame", background=BG)
        style.configure("Panel.TFrame", background=PANEL)
        style.configure("Header.TFrame", background=HEADER)
        style.configure("Header.TLabel", background=HEADER, foreground="#ffffff", font=("Microsoft YaHei UI", 18, "bold"))
        style.configure("HeaderSub.TLabel", background=HEADER, foreground="#e4edf5", font=("Microsoft YaHei UI", 9))
        style.configure("Metric.TLabel", background=PANEL, foreground=INK, font=("Microsoft YaHei UI", 20, "bold"))
        style.configure("MetricName.TLabel", background=PANEL, foreground=MUTED, font=("Microsoft YaHei UI", 9))
        style.configure("TLabel", background=BG, foreground=INK, font=("Microsoft YaHei UI", 9))
        style.configure("TButton", font=("Microsoft YaHei UI", 9), padding=(12, 7), borderwidth=0)
        style.configure("Accent.TButton", background=ACCENT, foreground="#ffffff")
        style.map("Accent.TButton", background=[("active", ACCENT_DARK), ("disabled", "#adc0cf")])
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", padding=(18, 9), font=("Microsoft YaHei UI", 10), background="#dbe6ef")
        style.map("TNotebook.Tab", background=[("selected", PANEL)], foreground=[("selected", ACCENT_DARK)])
        style.configure("Treeview", rowheight=30, font=("Microsoft YaHei UI", 9), background=PANEL, fieldbackground=PANEL, bordercolor=LINE)
        style.configure("Treeview.Heading", font=("Microsoft YaHei UI", 9, "bold"), background="#e4edf5", foreground=INK, padding=(6, 7))
        style.map("Treeview", background=[("selected", "#dceaf4")], foreground=[("selected", INK)])
        style.configure("Horizontal.TProgressbar", troughcolor="#d7e2eb", background=ACCENT, borderwidth=0)
        style.configure("Layout.TRadiobutton", background=PANEL, foreground=INK, font=("Microsoft YaHei UI", 9), padding=(5, 0))

    @staticmethod
    def _cleanup_stale_update_files() -> None:
        if not getattr(sys, "frozen", False):
            return
        for path in Path(sys.executable).resolve().parent.glob("stellasora-update-*.exe"):
            try:
                path.unlink()
            except OSError:
                pass

    def _build_ui(self) -> None:
        self.root.rowconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=1)
        self.app_canvas = tk.Canvas(self.root, background=BG, highlightthickness=0, borderwidth=0)
        self.app_scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=self.app_canvas.yview)
        self.app_canvas.configure(yscrollcommand=self.app_scrollbar.set)
        self.app_canvas.grid(row=0, column=0, sticky="nsew")
        self.app_scrollbar.grid(row=0, column=1, sticky="ns")
        self.app_content = ttk.Frame(self.app_canvas, style="App.TFrame")
        app_window = self.app_canvas.create_window((0, 0), window=self.app_content, anchor="nw")
        self.app_content.bind(
            "<Configure>",
            lambda _event: self.app_canvas.configure(scrollregion=self.app_canvas.bbox("all")),
        )
        self.app_canvas.bind(
            "<Configure>",
            lambda event: self.app_canvas.itemconfigure(app_window, width=event.width),
        )
        self.app_canvas.bind("<Enter>", lambda _event: self.app_canvas.bind_all("<MouseWheel>", self._scroll_app))
        self.app_canvas.bind("<Leave>", lambda _event: self.app_canvas.unbind_all("<MouseWheel>"))

        header = ttk.Frame(self.app_content, style="Header.TFrame", padding=(24, 17))
        header.pack(fill="x")
        header.columnconfigure(1, weight=1)
        title_box = ttk.Frame(header, style="Header.TFrame")
        title_box.grid(row=0, column=0, sticky="w")
        ttk.Label(title_box, text="星塔旅人数据工具", style="Header.TLabel").pack(anchor="w")
        ttk.Label(title_box, text="四类卡池与五星记录", style="HeaderSub.TLabel").pack(anchor="w", pady=(2, 0))
        actions = ttk.Frame(header, style="Header.TFrame")
        actions.grid(row=0, column=2, sticky="e")
        self.open_button = ttk.Button(actions, text="打开导出目录", command=self._open_exports)
        self.open_button.pack(side="left", padx=(0, 8))
        self.resource_button = ttk.Button(actions, text="更新角色资源", command=self.update_resources)
        self.resource_button.pack(side="left", padx=(0, 8))
        self.update_button = ttk.Button(actions, text="检查更新", command=self.check_app_update)
        self.update_button.pack(side="left", padx=(0, 8))
        self.refresh_button = ttk.Button(actions, text="刷新游戏数据", style="Accent.TButton", command=self.refresh)
        self.refresh_button.pack(side="left")

        body = ttk.Frame(self.app_content, style="App.TFrame", padding=(20, 16, 20, 12))
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(2, weight=1)

        metrics = ttk.Frame(body, style="App.TFrame")
        metrics.grid(row=0, column=0, sticky="ew")
        for column in range(4):
            metrics.columnconfigure(column, weight=1, uniform="metric")
        self.metric_groups = self._metric(metrics, 0, "招募分类", "#7776aa")
        self.metric_pulls = self._metric(metrics, 1, "抽取结果", "#4d9ba0")
        self.metric_emblems = self._metric(metrics, 2, "五星记录", "#5d82a9")
        self.metric_characters = self._metric(metrics, 3, "归档组数", "#8e6d9c")

        status_row = ttk.Frame(body, style="App.TFrame")
        status_row.grid(row=1, column=0, sticky="ew", pady=(13, 10))
        status_row.columnconfigure(0, weight=1)
        self.status_var = tk.StringVar(value="等待读取")
        ttk.Label(status_row, textvariable=self.status_var, foreground=MUTED).grid(row=0, column=0, sticky="w")
        self.progress = ttk.Progressbar(status_row, mode="indeterminate", length=180)
        self.progress.grid(row=0, column=1, sticky="e")
        self.progress.grid_remove()

        self.notebook = ttk.Notebook(body)
        self.notebook.grid(row=2, column=0, sticky="nsew")
        self._build_five_star_tab()
        self._build_gacha_tab()

    def _scroll_app(self, event) -> None:
        self.app_canvas.yview_scroll(int(-event.delta / 120), "units")

    def _metric(self, parent: ttk.Frame, column: int, name: str, color: str) -> tk.StringVar:
        frame = ttk.Frame(parent, style="Panel.TFrame", padding=(16, 12))
        frame.grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else 5, 0 if column == 3 else 5))
        strip = tk.Frame(frame, width=4, height=48, bg=color)
        strip.pack(side="left", fill="y", padx=(0, 12))
        content = ttk.Frame(frame, style="Panel.TFrame")
        content.pack(side="left", fill="both")
        value = tk.StringVar(value="-")
        ttk.Label(content, textvariable=value, style="Metric.TLabel").pack(anchor="w")
        ttk.Label(content, text=name, style="MetricName.TLabel").pack(anchor="w")
        return value

    def _toolbar(self, parent: ttk.Frame, variable: tk.StringVar, callback) -> ttk.Frame:
        bar = ttk.Frame(parent, style="Panel.TFrame", padding=(12, 10))
        ttk.Label(bar, text="筛选", background=PANEL, foreground=MUTED).pack(side="left", padx=(0, 8))
        entry = ttk.Entry(bar, textvariable=variable, width=34)
        entry.pack(side="left")
        variable.trace_add("write", lambda *_args: callback())
        return bar

    def _build_gacha_tab(self) -> None:
        tab = ttk.Frame(self.notebook, style="Panel.TFrame")
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(1, weight=1)
        self.notebook.add(tab, text="招募记录")
        self.gacha_filter = tk.StringVar()
        self._toolbar(tab, self.gacha_filter, self._fill_gacha).grid(row=0, column=0, sticky="ew")
        columns = ("time", "gid", "mode", "count", "items")
        self.gacha_tree = ttk.Treeview(tab, columns=columns, show="headings", selectmode="browse")
        headings = {"time": "时间", "gid": "记录 ID", "mode": "类型", "count": "数量", "items": "结果"}
        widths = {"time": 170, "gid": 110, "mode": 80, "count": 65, "items": 620}
        for column in columns:
            self.gacha_tree.heading(column, text=headings[column])
            self.gacha_tree.column(column, width=widths[column], minwidth=60, stretch=column == "items")
        scroll = ttk.Scrollbar(tab, orient="vertical", command=self.gacha_tree.yview)
        self.gacha_tree.configure(yscrollcommand=scroll.set)
        self.gacha_tree.grid(row=1, column=0, sticky="nsew")
        scroll.grid(row=1, column=1, sticky="ns")
        self.gacha_tree.bind("<Double-1>", self._show_gacha_detail)

    def _build_five_star_tab(self) -> None:
        tab = ttk.Frame(self.notebook, style="Panel.TFrame")
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(0, weight=1)
        self.notebook.add(tab, text="五星一览")
        self.stats_content = ttk.Frame(tab, style="App.TFrame")
        self.stats_content.grid(row=0, column=0, sticky="ew")

    def _fill_five_star_stats(self) -> None:
        for child in self.stats_content.winfo_children():
            child.destroy()
        self.avatar_images.clear()
        if self.snapshot is None:
            return
        categories = self.snapshot.gacha_categories or {1: self.snapshot.gacha}
        semantic_categories: dict[str, list[dict]] = {}
        for groups in categories.values():
            category = classify_history_category(groups)
            semantic_categories.setdefault(category, []).extend(groups)
        total_five = sum(
            len(pool.five_stars)
            for category, groups in semantic_categories.items()
            if category in GACHA_CATEGORY_NAMES
            for pool in build_pool_stats(groups)
        )
        loaded_count = sum(category in semantic_categories for category in GACHA_CATEGORY_ORDER)

        intro = ttk.Frame(self.stats_content, style="Panel.TFrame", padding=(18, 14))
        intro.pack(fill="x", padx=12, pady=(12, 8))
        ttk.Label(
            intro,
            text=f"五星记录  {total_five}",
            background=PANEL,
            foreground=INK,
            font=("Microsoft YaHei UI", 14, "bold"),
        ).pack(side="left")
        ttk.Label(
            intro,
            text=f"已加载分类 {loaded_count}/4 · 间隔抽数按同一卡池独立计算",
            background=PANEL,
            foreground=MUTED,
        ).pack(side="right", padx=(16, 0))
        layout_switch = ttk.Frame(intro, style="Panel.TFrame")
        layout_switch.pack(side="right")
        ttk.Radiobutton(
            layout_switch,
            text="双列",
            variable=self.pool_columns,
            value=2,
            command=self._refresh_pool_layout,
            style="Layout.TRadiobutton",
        ).pack(side="left")
        ttk.Radiobutton(
            layout_switch,
            text="单列",
            variable=self.pool_columns,
            value=1,
            command=self._refresh_pool_layout,
            style="Layout.TRadiobutton",
        ).pack(side="left")

        stats_by_category = {
            category: build_category_stat(semantic_categories.get(category, []))
            for category in GACHA_CATEGORY_ORDER
        }
        pool_grid = ttk.Frame(self.stats_content, style="App.TFrame")
        pool_grid.pack(fill="x", padx=12, pady=(2, 8))
        grid_columns = self.pool_columns.get()
        for column in range(grid_columns):
            pool_grid.columnconfigure(column, weight=1, uniform="pool-column")
        color_index = 0
        for index, category in enumerate(GACHA_CATEGORY_ORDER):
            name = GACHA_CATEGORY_NAMES[category]
            category_stat = stats_by_category[category]
            panel = ttk.Frame(pool_grid, style="App.TFrame")
            panel.grid(
                row=index // grid_columns,
                column=index % grid_columns,
                sticky="nsew",
                padx=(0, 6) if grid_columns == 2 and index % grid_columns == 0 else (6, 0) if grid_columns == 2 else 0,
                pady=(0, 8),
            )
            pool_grid.rowconfigure(index // grid_columns, weight=1)
            self._build_category_heading(name, category_stat is not None, panel)
            if category_stat is None:
                self._build_missing_category(panel)
                continue
            self._build_pool_section(category_stat, POOL_COLORS[color_index % len(POOL_COLORS)], name, panel)
            color_index += 1

    def _refresh_pool_layout(self) -> None:
        self._save_pool_columns()
        if self.snapshot is not None:
            self._fill_five_star_stats()

    def _load_pool_columns(self) -> int:
        try:
            settings = json.loads((self.output_dir / "ui_settings.json").read_text(encoding="utf-8"))
            return int(settings.get("pool_columns")) if int(settings.get("pool_columns")) in (1, 2) else 2
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return 2

    def _save_pool_columns(self) -> None:
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            (self.output_dir / "ui_settings.json").write_text(
                json.dumps({"pool_columns": self.pool_columns.get()}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError:
            pass

    def _build_category_heading(self, name: str, loaded: bool, parent: ttk.Frame | None = None) -> None:
        container = parent or self.stats_content
        heading = ttk.Frame(container, style="App.TFrame", padding=(4, 8, 4, 4))
        heading.pack(fill="x")
        ttk.Label(
            heading,
            text=name,
            background=BG,
            foreground=ACCENT_DARK if loaded else MUTED,
            font=("Microsoft YaHei UI", 9, "bold"),
        ).pack(side="left")
        ttk.Label(
            heading,
            text="已加载" if loaded else "未加载",
            background=BG,
            foreground=ACCENT if loaded else WARM,
        ).pack(side="right")

    def _build_missing_category(self, parent: ttk.Frame | None = None) -> None:
        container = parent or self.stats_content
        frame = ttk.Frame(container, style="Panel.TFrame", padding=(16, 14))
        frame.pack(fill="both", expand=True)
        ttk.Label(
            frame,
            text="该分类尚未进入游戏历史缓存，请在游戏中打开对应卡池的招募记录后再刷新。",
            background=PANEL,
            foreground=MUTED,
        ).pack(anchor="w")

    def _build_pool_section(
        self,
        pool: PoolStats,
        color: str,
        category_name: str,
        parent: ttk.Frame | None = None,
    ) -> None:
        container = parent or self.stats_content
        section = ttk.Frame(container, style="Panel.TFrame")
        section.pack(fill="both", expand=True)
        header = tk.Frame(section, background=color, height=103)
        header.pack(fill="x")
        header.pack_propagate(False)

        title = tk.Frame(header, background=color)
        title.pack(side="left", fill="both", expand=True, padx=25, pady=16)
        tk.Label(
            title,
            text=category_name,
            background=color,
            foreground="#ffffff",
            font=("Microsoft YaHei UI", 19, "bold"),
        ).pack(anchor="w")
        date_text = f"{self._format_date(pool.start_time)}  -  {self._format_date(pool.end_time)}"
        tk.Label(
            title,
            text=date_text,
            background=color,
            foreground="#eef5fa",
            font=("Microsoft YaHei UI", 11),
        ).pack(anchor="w", pady=(4, 0))

        summary = tk.Frame(header, background=self._darken(color))
        summary.pack(side="right", fill="y", padx=(0, 18), pady=12)
        self._pool_metric(summary, str(pool.total_pulls), "总抽数")
        self._pool_metric(summary, str(len(pool.five_stars)), "五星")
        average = "-" if pool.average_pulls is None else str(pool.average_pulls)
        self._pool_metric(summary, average, "平均抽数")

        hits = tk.Frame(section, background=PANEL)
        hits.pack(fill="x", padx=18, pady=(15, 18))
        if not pool.five_stars:
            tk.Label(
                hits,
                text="该卡池的已加载记录中暂无五星角色",
                background=PANEL,
                foreground=MUTED,
                font=("Microsoft YaHei UI", 10),
                pady=20,
            ).pack(anchor="w")
            return
        last_columns = 0

        def render_tiles(_event=None) -> None:
            nonlocal last_columns
            columns = max(1, hits.winfo_width() // 144)
            if columns == last_columns and hits.winfo_children():
                return
            last_columns = columns
            for child in hits.winfo_children():
                child.destroy()
            for index, pull in enumerate(pool.five_stars):
                tile = tk.Frame(hits, background=PANEL, width=126, height=128)
                tile.grid(row=index // columns, column=index % columns, padx=9, pady=5, sticky="nw")
                tile.grid_propagate(False)
                photo = self._avatar_photo(pull.item_id, pull.kind, color)
                self.avatar_images.append(photo)
                tk.Label(tile, image=photo, background=PANEL, borderwidth=0).place(x=19, y=0, width=88, height=88)
                badge_color = "#4d9ba0" if pull.pity <= 30 else WARM if pull.pity <= 60 else "#b97a8a"
                tk.Label(
                    tile,
                    text=f"{pull.pity} 抽",
                    background=badge_color,
                    foreground="#ffffff",
                    font=("Microsoft YaHei UI", 9, "bold"),
                    padx=7,
                    pady=3,
                ).place(x=61, y=66)
                tk.Label(
                    tile,
                    text=pull.name,
                    background="#f8fbfe",
                    foreground=INK,
                    font=("Microsoft YaHei UI", 9),
                ).place(x=6, y=98, width=114, height=25)

        hits.bind("<Configure>", render_tiles)
        self.root.after_idle(render_tiles)

    @staticmethod
    def _pool_metric(parent: tk.Frame, value: str, label: str) -> None:
        box = tk.Frame(parent, background=parent.cget("background"), width=51)
        box.pack(side="left", fill="y", padx=2)
        box.pack_propagate(False)
        tk.Label(
            box,
            text=value,
            background=box.cget("background"),
            foreground="#ffffff",
            font=("Microsoft YaHei UI", 16, "bold"),
        ).pack(pady=(10, 0))
        tk.Label(
            box,
            text=label,
            background=box.cget("background"),
            foreground="#e5ebe7",
            font=("Microsoft YaHei UI", 10),
        ).pack()

    @staticmethod
    def _darken(color: str) -> str:
        red, green, blue = (int(color[index : index + 2], 16) for index in (1, 3, 5))
        return f"#{int(red * .72):02x}{int(green * .72):02x}{int(blue * .72):02x}"

    @staticmethod
    def _format_date(timestamp: int) -> str:
        try:
            return datetime.fromtimestamp(timestamp).strftime("%Y.%m.%d")
        except (ValueError, OSError, OverflowError):
            return "未知日期"

    def _avatar_photo(self, item_id: int, kind: str, border_color: str) -> ImageTk.PhotoImage:
        folder = "travelers" if kind == "traveler" else "discs"
        resource_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
        external_path = self.output_dir / "assets" / folder / f"{item_id}.png"
        path = external_path if external_path.exists() else resource_root / "assets" / folder / f"{item_id}.png"
        size = 88
        try:
            source = Image.open(path).convert("RGBA")
            source = ImageOps.fit(source, (size - 6, size - 6), method=Image.Resampling.LANCZOS)
        except OSError:
            source = Image.new("RGBA", (size - 6, size - 6), "#dbe6ef")
            draw = ImageDraw.Draw(source)
            draw.text((12, 28), str(item_id), fill=INK)
        mask = Image.new("L", source.size, 0)
        ImageDraw.Draw(mask).ellipse((0, 0, source.width - 1, source.height - 1), fill=255)
        source.putalpha(mask)
        canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(canvas)
        draw.ellipse((0, 0, size - 1, size - 1), fill=border_color)
        canvas.alpha_composite(source, (3, 3))
        return ImageTk.PhotoImage(canvas)

    def _build_emblem_tab(self) -> None:
        tab = ttk.Frame(self.notebook, style="Panel.TFrame")
        tab.columnconfigure(0, weight=3)
        tab.columnconfigure(1, weight=2)
        tab.rowconfigure(1, weight=1)
        self.notebook.add(tab, text="角色纹章")
        self.emblem_filter = tk.StringVar()
        self._toolbar(tab, self.emblem_filter, self._fill_emblems).grid(row=0, column=0, columnspan=2, sticky="ew")
        columns = ("traveler", "slot", "name", "lock", "attrs")
        self.emblem_tree = ttk.Treeview(tab, columns=columns, show="headings", selectmode="browse")
        headings = {"traveler": "旅人", "slot": "槽位", "name": "纹章", "lock": "锁定", "attrs": "随机词条"}
        widths = {"traveler": 120, "slot": 86, "name": 150, "lock": 65, "attrs": 420}
        for column in columns:
            self.emblem_tree.heading(column, text=headings[column])
            self.emblem_tree.column(column, width=widths[column], minwidth=60, stretch=column == "attrs")
        scroll = ttk.Scrollbar(tab, orient="vertical", command=self.emblem_tree.yview)
        self.emblem_tree.configure(yscrollcommand=scroll.set)
        self.emblem_tree.grid(row=1, column=0, sticky="nsew")
        scroll.grid(row=1, column=0, sticky="nse")
        self.emblem_tree.bind("<<TreeviewSelect>>", self._show_emblem_detail)

        detail = ttk.Frame(tab, style="Panel.TFrame", padding=(14, 10))
        detail.grid(row=1, column=1, sticky="nsew")
        detail.rowconfigure(1, weight=1)
        detail.columnconfigure(0, weight=1)
        ttk.Label(detail, text="纹章明细", background=PANEL, font=("Microsoft YaHei UI", 11, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 8))
        self.detail_text = tk.Text(
            detail,
            wrap="word",
            relief="flat",
            borderwidth=0,
            background="#f3f8fc",
            foreground=INK,
            font=("Microsoft YaHei UI", 9),
            padx=12,
            pady=10,
            state="disabled",
        )
        self.detail_text.grid(row=1, column=0, sticky="nsew")

    def _load_latest(self) -> None:
        snapshot = load_latest_snapshot(self.output_dir)
        if snapshot is None:
            self.status_var.set("暂无本地数据，请启动并登录游戏后刷新")
            return
        self._apply_snapshot(snapshot)
        self.status_var.set("已加载最近一次本地数据")

    def refresh(self) -> None:
        if self.busy:
            return
        self.busy = True
        self.refresh_button.state(["disabled"])
        self.progress.grid()
        self.progress.start(12)
        self.status_var.set("正在读取游戏数据")

        def work() -> None:
            try:
                snapshot = extract_snapshot(
                    self.output_dir,
                    progress=lambda message: self.events.put(("progress", message)),
                )
                self.events.put(("complete", snapshot))
            except Exception as error:
                self.events.put(("error", error))

        threading.Thread(target=work, name="stellasora-reader", daemon=True).start()

    def update_resources(self) -> None:
        if self.busy:
            return
        self.busy = True
        self.refresh_button.state(["disabled"])
        self.resource_button.state(["disabled"])
        self.progress.grid()
        self.progress.start(12)
        self.status_var.set("正在检查角色资源")

        def work() -> None:
            try:
                items, downloaded = update_resources(
                    DEFAULT_MANIFEST_URL,
                    self.output_dir / "assets",
                    progress=lambda message: self.events.put(("progress", message)),
                )
                self.events.put(("resources_complete", (items, downloaded)))
            except Exception as error:
                self.events.put(("resources_error", error))

        threading.Thread(target=work, name="stellasora-resources", daemon=True).start()

    def check_app_update(self, silent: bool = False) -> None:
        if self.busy or self.update_checking:
            return
        if not getattr(sys, "frozen", False):
            if not silent:
                messagebox.showinfo("检查更新", "源码运行模式不会自动替换程序，请使用打包后的 exe。", parent=self.root)
            return
        self.update_checking = True
        self.update_button.state(["disabled"])
        if not silent:
            self.status_var.set("正在检查软件更新")

        def work() -> None:
            try:
                update = check_for_update(UPDATE_MANIFEST_URL, APP_VERSION)
                self.events.put(("app_update_result", (update, silent)))
            except Exception as error:
                self.events.put(("app_update_error", (error, silent)))

        threading.Thread(target=work, name="stellasora-update-check", daemon=True).start()

    def _download_app_update(self, update: AppUpdate) -> None:
        self.busy = True
        self.refresh_button.state(["disabled"])
        self.resource_button.state(["disabled"])
        self.update_button.state(["disabled"])
        self.progress.grid()
        self.progress.start(12)
        self.status_var.set(f"正在下载软件更新 {update.version}")

        def work() -> None:
            try:
                path = download_update(
                    update,
                    Path(sys.executable).resolve().parent,
                    progress=lambda message: self.events.put(("progress", message)),
                )
                self.events.put(("app_update_downloaded", (update, path)))
            except Exception as error:
                self.events.put(("app_update_download_error", error))

        threading.Thread(target=work, name="stellasora-update-download", daemon=True).start()

    def _install_app_update(self, downloaded_path: Path) -> None:
        target = Path(sys.executable).resolve()
        quote = lambda value: "'" + str(value).replace("'", "''") + "'"
        command = (
            f"$process = Get-Process -Id {os.getpid()} -ErrorAction SilentlyContinue; "
            f"if ($process) {{ Wait-Process -Id {os.getpid()} -ErrorAction SilentlyContinue }}; "
            "Start-Sleep -Seconds 2; "
            "$installed = $false; "
            "for ($attempt = 0; $attempt -lt 20; $attempt++) { "
            f"try {{ Copy-Item -LiteralPath {quote(downloaded_path)} -Destination {quote(target)} -Force -ErrorAction Stop; "
            f"Remove-Item -LiteralPath {quote(downloaded_path)} -Force; $installed = $true; break }} "
            "catch { Start-Sleep -Seconds 1 } }; "
            f"if ($installed) {{ Start-Process -FilePath {quote(target)} -WorkingDirectory {quote(target.parent)} }}"
        )
        subprocess.Popen(
            ["powershell.exe", "-NoProfile", "-WindowStyle", "Hidden", "-Command", command],
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        self.root.destroy()

    def _poll_events(self) -> None:
        try:
            while True:
                event, payload = self.events.get_nowait()
                if event == "progress":
                    self.status_var.set(str(payload))
                elif event == "complete":
                    self._apply_snapshot(payload)
                    self._finish_busy()
                    self.status_var.set(f"读取完成 · {datetime.now():%H:%M:%S}")
                elif event == "error":
                    self._finish_busy()
                    self.status_var.set("读取失败")
                    messagebox.showerror("读取失败", str(payload), parent=self.root)
                elif event == "resources_complete":
                    items, downloaded = payload
                    for item in items:
                        try:
                            register_gacha_resource(
                                int(item["id"]),
                                str(item["kind"]),
                                str(item["name"]),
                                int(item.get("rarity", 5)),
                            )
                        except (KeyError, TypeError, ValueError):
                            continue
                    self._finish_busy()
                    if self.snapshot is not None:
                        self._fill_five_star_stats()
                    self.status_var.set(f"角色资源更新完成 · 新增 {downloaded} 个")
                elif event == "resources_error":
                    self._finish_busy()
                    self.status_var.set("角色资源更新失败")
                    messagebox.showerror("资源更新失败", str(payload), parent=self.root)
                elif event == "app_update_result":
                    update, silent = payload
                    self.update_checking = False
                    self.update_button.state(["!disabled"])
                    if update is None:
                        if not silent:
                            self.status_var.set(f"当前已是最新版 {APP_VERSION}")
                            messagebox.showinfo("检查更新", f"当前已是最新版 {APP_VERSION}。", parent=self.root)
                    else:
                        notes = f"\n\n{update.notes}" if update.notes else ""
                        if messagebox.askyesno(
                            "发现软件更新",
                            f"发现新版本 {update.version}，是否立即下载并安装？{notes}",
                            parent=self.root,
                        ):
                            self._download_app_update(update)
                elif event == "app_update_error":
                    error, silent = payload
                    self.update_checking = False
                    self.update_button.state(["!disabled"])
                    if not silent:
                        self.status_var.set("软件更新检查失败")
                        messagebox.showerror("检查更新失败", str(error), parent=self.root)
                elif event == "app_update_downloaded":
                    update, path = payload
                    self._finish_busy()
                    self.update_button.state(["!disabled"])
                    self.status_var.set(f"软件更新 {update.version} 下载完成")
                    messagebox.showinfo("更新就绪", "软件将关闭、安装更新并自动重新启动。", parent=self.root)
                    self._install_app_update(path)
                elif event == "app_update_download_error":
                    self._finish_busy()
                    self.update_button.state(["!disabled"])
                    self.status_var.set("软件下载失败")
                    messagebox.showerror("软件下载失败", str(payload), parent=self.root)
        except queue.Empty:
            pass
        self.root.after(100, self._poll_events)

    def _finish_busy(self) -> None:
        self.busy = False
        self.progress.stop()
        self.progress.grid_remove()
        self.refresh_button.state(["!disabled"])
        self.resource_button.state(["!disabled"])

    def _apply_snapshot(self, snapshot: Snapshot) -> None:
        self.snapshot = snapshot
        categories = snapshot.gacha_categories or {1: snapshot.gacha}
        loaded_categories = sum(
            classify_history_category(groups) in GACHA_CATEGORY_NAMES for groups in categories.values()
        )
        self.metric_groups.set(str(loaded_categories))
        self.metric_pulls.set(str(snapshot.pull_count))
        categories = snapshot.gacha_categories or {1: snapshot.gacha}
        self.metric_emblems.set(str(sum(len(build_category_stat(groups).five_stars) for groups in categories.values() if build_category_stat(groups))))
        self.metric_characters.set(str(len(snapshot.gacha)))
        self._fill_five_star_stats()
        self._fill_gacha()

    @staticmethod
    def _format_time(value: Any) -> str:
        try:
            return datetime.fromtimestamp(int(value)).strftime("%Y-%m-%d %H:%M:%S")
        except (TypeError, ValueError, OSError, OverflowError):
            return "-"

    def _fill_gacha(self) -> None:
        if not hasattr(self, "gacha_tree"):
            return
        self.gacha_tree.delete(*self.gacha_tree.get_children())
        self.gacha_rows.clear()
        if self.snapshot is None:
            return
        needle = self.gacha_filter.get().strip().casefold()
        for group in reversed(self.snapshot.gacha):
            ids = group.get("Ids", [])
            names = [gacha_item_name(value) for value in ids]
            haystack = " ".join([str(group.get("Gid", "")), *names]).casefold()
            if needle and needle not in haystack:
                continue
            iid = self.gacha_tree.insert(
                "",
                "end",
                values=(
                    self._format_time(group.get("Time")),
                    group.get("Gid", "-"),
                    "十连" if len(ids) > 1 else "单抽",
                    len(ids),
                    "、".join(names),
                ),
            )
            self.gacha_rows[iid] = group

    def _fill_emblems(self) -> None:
        if not hasattr(self, "emblem_tree"):
            return
        self.emblem_tree.delete(*self.emblem_tree.get_children())
        self.emblem_rows.clear()
        if self.snapshot is None:
            return
        needle = self.emblem_filter.get().strip().casefold()
        for emblem in self.snapshot.emblems:
            attrs = [format_random_attr(value) for value in table_values(emblem.get("tbRandomAttr"))]
            traveler = traveler_name(emblem.get("nCharId"))
            name = str(emblem.get("sName") or f"纹章 #{emblem.get('nGemId', '?')}")
            haystack = " ".join([traveler, name, str(emblem.get("nGemId", "")), *attrs]).casefold()
            if needle and needle not in haystack:
                continue
            iid = self.emblem_tree.insert(
                "",
                "end",
                values=(
                    traveler,
                    gem_type_name(emblem.get("nType")),
                    name,
                    "是" if emblem.get("bLock") else "否",
                    " · ".join(attrs) or "无随机词条",
                ),
            )
            self.emblem_rows[iid] = emblem

    def _show_gacha_detail(self, _event=None) -> None:
        selected = self.gacha_tree.selection()
        if not selected:
            return
        group = self.gacha_rows.get(selected[0])
        if not group:
            return
        names = "\n".join(f"{index}. {gacha_item_name(value)} ({value})" for index, value in enumerate(group.get("Ids", []), 1))
        messagebox.showinfo(
            "招募记录",
            f"时间：{self._format_time(group.get('Time'))}\n记录 ID：{group.get('Gid')}\n\n{names}",
            parent=self.root,
        )

    def _show_emblem_detail(self, _event=None) -> None:
        selected = self.emblem_tree.selection()
        emblem = self.emblem_rows.get(selected[0]) if selected else None
        if emblem is None:
            return
        attrs = "\n".join(f"  {format_random_attr(attr)}" for attr in table_values(emblem.get("tbRandomAttr"))) or "  无"
        potentials = json.dumps(emblem.get("tbPotentialAffix", []), ensure_ascii=False, indent=2)
        text = (
            f"{emblem.get('sName', '未命名纹章')}\n"
            f"旅人：{traveler_name(emblem.get('nCharId'))} ({emblem.get('nCharId')})\n"
            f"类型：{gem_type_name(emblem.get('nType'))}\n"
            f"纹章 ID：{emblem.get('nGemId')}\n"
            f"锁定：{'是' if emblem.get('bLock') else '否'}\n\n"
            f"随机词条\n{attrs}\n\n"
            f"潜能词条\n{potentials}"
        )
        self.detail_text.configure(state="normal")
        self.detail_text.delete("1.0", "end")
        self.detail_text.insert("1.0", text)
        self.detail_text.configure(state="disabled")

    def _open_exports(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":
            os.startfile(self.output_dir)  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["xdg-open", str(self.output_dir)])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="星塔旅人数据工具桌面界面")
    default_root = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path.cwd()
    parser.add_argument("--output", type=Path, default=default_root / "exports")
    parser.add_argument("--smoke-test", action="store_true", help=argparse.SUPPRESS)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = tk.Tk()
    StellaSoraApp(root, args.output.resolve())
    if args.smoke_test:
        root.update_idletasks()
        root.destroy()
        return 0
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
