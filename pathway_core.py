#!/usr/bin/env python3
"""
Pathway Plotter
===============
A small desktop tool for drawing energy-pathway style figures.

* Every pathway is a row, every step is a column (step i of every pathway is
  drawn at the same x position).
* Each step has: a name (written above it), a value (its y position) and an
  "activation" checkbox. Normal steps are drawn as solid horizontal plateaus,
  activation steps as dashed parabolic arches.
* Blank steps are skipped and the neighbouring steps are joined by a dashed line.
* Projects can be saved to / loaded from a JSON file, figures exported as PNG.

Requirements:  pip install matplotlib numpy   (tkinter ships with Python)
Run:           python pathway_plotter.py
"""

import json
import os
import sys
import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox, ttk

import numpy as np
from matplotlib.figure import Figure
from matplotlib.lines import Line2D

# ----------------------------------------------------------------------------
# Settings
# ----------------------------------------------------------------------------
MAX_PATHWAYS = 10

# black, blue, red, yellow first (as requested), then six more picked from the
# Okabe-Ito colour-blind-safe palette plus grey / dark purple.
COLORS = [
    "#000000",  # black
    "#0072B2",  # blue
    "#D55E00",  # red (vermillion)
    "#F0E442",  # yellow
    "#E69F00",  # orange
    "#56B4E9",  # sky blue
    "#009E73",  # bluish green
    "#CC79A7",  # reddish purple
    "#999999",  # grey
    "#6A3D9A",  # dark purple
]

HALF_WIDTH = 0.3   # half the length of a plateau, in x units (step spacing = 1)
ARCH_REACH = 0.7   # how far an arch extends when it has no neighbouring step
LINE_WIDTH = 2.6

DEFAULT_SIZE_IN = (8.0, 6.0)   # figure width x height in inches (height:width = 3:4)
MIN_IN, MAX_IN = 1.0, 50.0     # allowed range for either side, in inches


# ----------------------------------------------------------------------------
# Drawing (independent of the GUI so it can be reused / tested)
# ----------------------------------------------------------------------------
def parse_value(text):
    """Return float or None (blank / invalid)."""
    try:
        return float(str(text).strip())
    except ValueError:
        return None


def draw_figure(fig, data):
    """Draw the pathways described by `data` onto matplotlib Figure `fig`.

    data = {"title": str, "ylabel": str,
            "pathways": [{"name": str,
                          "steps": [{"name": str, "val": str, "act": bool}, ...]}]}
    """
    fig.clear()
    ax = fig.add_subplot(111)
    pathways = data["pathways"]
    n_steps = max((len(p["steps"]) for p in pathways), default=1)

    all_y = []
    x_left = 1 - HALF_WIDTH   # the first step starts exactly at the y-axis
    claimed = set()           # shapes already drawn by an earlier pathway
    labelled = set()          # positions that already carry a label

    def r(t):
        return round(t, 6)

    def claim(key):
        """True if no earlier pathway has drawn this exact shape yet.
        Shared steps / branches therefore keep the colour of the pathway
        that was entered first."""
        if key in claimed:
            return False
        claimed.add(key)
        return True

    def label(x, y, text):
        text = text.strip()
        if text and (r(x), r(y)) not in labelled:
            labelled.add((r(x), r(y)))
            ax.annotate(text, (x, y), xytext=(0, 6), textcoords="offset points",
                        ha="center", va="bottom", fontsize=10, zorder=5)

    for pi, p in enumerate(pathways):
        color = p.get("color") or COLORS[pi % len(COLORS)]

        # keep only the steps that have a usable value
        pts = []
        for i, s in enumerate(p["steps"]):
            v = parse_value(s.get("val", ""))
            if v is not None:
                pts.append((i + 1, v, bool(s.get("act")), s.get("name", "")))

        for k, (x, v, act, name) in enumerate(pts):
            if not act:
                # solid plateau + label
                if claim(("plateau", r(x), r(v))):
                    ax.plot([x - HALF_WIDTH, x + HALF_WIDTH], [v, v], color=color,
                            lw=LINE_WIDTH, solid_capstyle="round", zorder=3)
                label(x, v, name)
                all_y.append(v)
                # dashed connection to the next step if that is a plateau too
                if k + 1 < len(pts) and not pts[k + 1][2]:
                    x2, v2 = pts[k + 1][0], pts[k + 1][1]
                    if claim(("link", r(x), r(v), r(x2), r(v2))):
                        ax.plot([x + HALF_WIDTH, x2 - HALF_WIDTH], [v, v2], color=color,
                                lw=LINE_WIDTH, ls=(0, (1.2, 2.2)),
                                dash_capstyle="round", zorder=2)
            else:
                # dashed parabolic arch whose apex is the step's value
                prev = next((q for q in reversed(pts[:k]) if not q[2]), None)
                nxt = next((q for q in pts[k + 1:] if not q[2]), None)
                if prev:
                    x0, y0 = prev[0] + HALF_WIDTH, prev[1]
                else:
                    x0, y0 = x - ARCH_REACH, (nxt[1] if nxt else 0.0)
                if nxt:
                    x1, y1 = nxt[0] - HALF_WIDTH, nxt[1]
                else:
                    x1, y1 = x + ARCH_REACH, (prev[1] if prev else 0.0)

                if claim(("arch", r(x0), r(y0), r(x), r(v), r(x1), r(y1))):
                    xl = np.linspace(x0, x, 40)
                    yl = v - (v - y0) * ((x - xl) / (x - x0)) ** 2
                    xr = np.linspace(x, x1, 40)
                    yr = v - (v - y1) * ((xr - x) / (x1 - x)) ** 2
                    ax.plot(np.r_[xl, xr[1:]], np.r_[yl, yr[1:]], color=color,
                            lw=LINE_WIDTH, ls=(0, (1.2, 2.2)), dash_capstyle="round",
                            zorder=2)
                x_left = min(x_left, x0)
                label(x, v, name)
                all_y += [v, y0, y1]

    # axes cosmetics
    ax.set_xlim(x_left, n_steps + 0.6)
    ax.set_xticks([])
    if all_y:
        lo, hi = min(all_y), max(all_y)
        span = (hi - lo) or 1.0
        ax.set_ylim(lo - 0.12 * span, hi + 0.22 * span)
    else:
        ax.set_ylim(-1, 1)
    if data.get("title", "").strip():
        ax.set_title(data["title"].strip(), fontsize=14)
    if data.get("ylabel", "").strip():
        ax.set_ylabel(data["ylabel"].strip())

    if len(pathways) > 1:
        handles = [Line2D([0], [0], color=p.get("color") or COLORS[i % len(COLORS)],
                          lw=LINE_WIDTH, label=p["name"].strip() or f"Pathway {i + 1}")
                   for i, p in enumerate(pathways)]
        ax.legend(handles=handles, loc="best", frameon=True, edgecolor="black",
                  fancybox=False)
    return ax


# ----------------------------------------------------------------------------
# GUI
# ----------------------------------------------------------------------------
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Pathway Plotter")
        self.geometry("1250x850")

        self.file_name = tk.StringVar(value="figure")
        self.chart_title = tk.StringVar()
        self.y_title = tk.StringVar()
        for v in (self.chart_title, self.y_title):
            v.trace_add("write", lambda *_: self.schedule_redraw())

        # figure size (what is saved as PNG; the preview shows the same proportions)
        self._converting = False
        self._last_unit = "in"
        self._size_in = DEFAULT_SIZE_IN
        self.fig_w = tk.StringVar(value=self._fmt(DEFAULT_SIZE_IN[0]))
        self.fig_h = tk.StringVar(value=self._fmt(DEFAULT_SIZE_IN[1]))
        self.fig_unit = tk.StringVar(value="in")
        self.size_msg = tk.StringVar()
        for v in (self.fig_w, self.fig_h):
            v.trace_add("write", lambda *_: self._size_changed())

        self.pathways = []   # [{"name": StringVar, "steps": [{"name","val","act"}]}]
        self.n_steps = 1
        self._pending = None

        self._build_editor()      # packed at the bottom first, so it always keeps its room
        self._build_top_bar()     # settings on the left; buttons and preview on the right

        self._append_pathway("Pathway 1")
        self.rebuild_editor()
        self._size_changed()
        self.schedule_redraw()

    # ---- layout -----------------------------------------------------------
    def _build_top_bar(self):
        top = ttk.Frame(self, padding=8)
        top.pack(side="top", fill="both", expand=True)

        left = ttk.Frame(top)                       # settings column
        left.pack(side="left", anchor="n", padx=(0, 16))
        fields = ttk.Frame(left)
        fields.pack(anchor="w")
        for r, (text, var) in enumerate([("File name:", self.file_name),
                                         ("Chart title (optional):", self.chart_title),
                                         ("Y-axis title (optional):", self.y_title)]):
            ttk.Label(fields, text=text).grid(row=r, column=0, sticky="e", padx=4, pady=2)
            ttk.Entry(fields, textvariable=var, width=30).grid(row=r, column=1, pady=2)

        size = ttk.LabelFrame(left, text="Figure size", padding=(8, 4))
        size.pack(anchor="w", fill="x", pady=(12, 0))
        ttk.Label(size, text="Width").grid(row=0, column=0, sticky="e", padx=4, pady=2)
        ttk.Entry(size, textvariable=self.fig_w, width=7).grid(row=0, column=1, pady=2)
        ttk.Label(size, text="Height").grid(row=1, column=0, sticky="e", padx=4, pady=2)
        ttk.Entry(size, textvariable=self.fig_h, width=7).grid(row=1, column=1, pady=2)
        unit = ttk.Combobox(size, textvariable=self.fig_unit, values=("in", "cm"),
                            width=4, state="readonly")
        unit.grid(row=0, column=2, padx=6)
        unit.bind("<<ComboboxSelected>>", lambda e: self._unit_changed())
        ttk.Button(size, text="Swap", width=6, command=self._swap_size).grid(
            row=1, column=2, padx=6)
        ttk.Label(size, textvariable=self.size_msg, foreground="gray", width=26).grid(
            row=2, column=0, columnspan=3, sticky="w", pady=(2, 0))

        right = ttk.Frame(top)                      # buttons on top, preview below
        right.pack(side="left", fill="both", expand=True)
        buttons = ttk.Frame(right)
        buttons.pack(side="top", anchor="e")
        for text, command in (("Save PNG", self.save_png),
                              ("Save project", self.save_project),
                              ("Load project", self.load_project)):
            ttk.Button(buttons, text=text, width=14, command=command).pack(
                side="left", padx=2)
        self._build_preview(right)

    def _build_editor(self):
        outer = ttk.LabelFrame(self, text="Pathways  (click a color box to change its color)",
                               padding=4)
        outer.pack(side="bottom", fill="x", padx=8, pady=4)

        self.editor_canvas = tk.Canvas(outer, height=230, highlightthickness=0)
        hbar = ttk.Scrollbar(outer, orient="horizontal", command=self.editor_canvas.xview)
        vbar = ttk.Scrollbar(outer, orient="vertical", command=self.editor_canvas.yview)
        self.editor_canvas.configure(xscrollcommand=hbar.set, yscrollcommand=vbar.set)
        hbar.pack(side="bottom", fill="x")
        vbar.pack(side="right", fill="y")
        self.editor_canvas.pack(side="left", fill="both", expand=True)

        self.grid_frame = ttk.Frame(self.editor_canvas)
        self.editor_canvas.create_window((0, 0), window=self.grid_frame, anchor="nw")
        self.grid_frame.bind(
            "<Configure>",
            lambda e: self.editor_canvas.configure(
                scrollregion=self.editor_canvas.bbox("all")))

        # mouse wheel (Shift + wheel scrolls sideways) while over the editor
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.bind_all(seq, self._on_wheel, add="+")

    def _on_wheel(self, event):
        w = self.winfo_containing(event.x_root, event.y_root)
        if w is None or not str(w).startswith(str(self.editor_canvas)):
            return
        if event.num == 4:            # Linux wheel up
            step = -1
        elif event.num == 5:          # Linux wheel down
            step = 1
        elif sys.platform == "darwin":
            step = -event.delta
        else:                         # Windows
            step = -event.delta // 120
        if not step:
            return
        if event.state & 0x1:         # Shift held
            self.editor_canvas.xview_scroll(step, "units")
        else:
            self.editor_canvas.yview_scroll(step, "units")

    def _fit_editor(self):
        """Grow the editor panel to fit its rows (up to ~half the window)."""
        self.update_idletasks()
        want = self.grid_frame.winfo_reqheight() + 24     # + horizontal scrollbar
        limit = max(230, int(self.winfo_height() * 0.5))
        self.editor_canvas.configure(height=max(150, min(want, limit)))

    def _ensure_visible(self, widget):
        """Scroll the editor so that `widget` is fully inside the viewport."""
        cv, gf = self.editor_canvas, self.grid_frame
        cv.update_idletasks()
        top = widget.winfo_rooty() - cv.winfo_rooty()
        left = widget.winfo_rootx() - cv.winfo_rootx()
        bottom, right = top + widget.winfo_height(), left + widget.winfo_width()
        total_h, total_w = max(1, gf.winfo_height()), max(1, gf.winfo_width())
        if top < 0:
            cv.yview_moveto(max(0, (cv.canvasy(0) + top - 8) / total_h))
        elif bottom > cv.winfo_height():
            cv.yview_moveto((cv.canvasy(0) + bottom - cv.winfo_height() + 8) / total_h)
        if left < 0:
            cv.xview_moveto(max(0, (cv.canvasx(0) + left - 8) / total_w))
        elif right > cv.winfo_width():
            cv.xview_moveto((cv.canvasx(0) + right - cv.winfo_width() + 8) / total_w)

    def _build_preview(self, parent):
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        # grey backdrop; the figure is centred in it with the chosen proportions
        self.preview_box = tk.Frame(parent, bg="#d0d0d0")
        self.preview_box.pack(side="top", fill="both", expand=True, pady=(6, 0))
        self.fig = Figure(figsize=DEFAULT_SIZE_IN, dpi=100, layout="constrained")
        self.preview = FigureCanvasTkAgg(self.fig, master=self.preview_box)
        self.preview_widget = self.preview.get_tk_widget()
        self.preview_box.bind("<Configure>", lambda e: self._fit_preview())

    # ---- figure size ------------------------------------------------------
    @staticmethod
    def _fmt(x):
        try:
            return f"{float(x):.2f}".rstrip("0").rstrip(".")
        except (TypeError, ValueError):
            return str(x)

    def _read_size(self):
        """(width, height) in inches from the fields, or None if invalid."""
        try:
            w, h = float(self.fig_w.get()), float(self.fig_h.get())
        except ValueError:
            return None
        k = 2.54 if self.fig_unit.get() == "cm" else 1.0
        w, h = w / k, h / k
        if MIN_IN <= w <= MAX_IN and MIN_IN <= h <= MAX_IN:
            return w, h
        return None

    def _size_changed(self):
        if self._converting:
            return
        size = self._read_size()
        if size:
            self._size_in = size
            w, h = size
            if self.fig_unit.get() == "cm":
                self.size_msg.set(f"= {w:.2f} x {h:.2f} in")
            else:
                self.size_msg.set(f"= {w * 2.54:.1f} x {h * 2.54:.1f} cm")
        else:
            lo, hi = MIN_IN, MAX_IN
            self.size_msg.set(f"Invalid ({lo:g}-{hi:g} in): using last valid")
        self._fit_preview()

    def _unit_changed(self):
        new = self.fig_unit.get()
        if new == self._last_unit:
            return
        k = 2.54 if new == "cm" else 1 / 2.54          # converting from the old unit
        self._converting = True
        for var in (self.fig_w, self.fig_h):
            try:
                var.set(self._fmt(float(var.get()) * k))
            except ValueError:
                pass
        self._converting = False
        self._last_unit = new
        self._size_changed()

    def _swap_size(self):
        w, h = self.fig_w.get(), self.fig_h.get()
        self._converting = True
        self.fig_w.set(h)
        self.fig_h.set(w)
        self._converting = False
        self._size_changed()

    def _set_size_fields(self, w, h, unit):
        unit = unit if unit in ("in", "cm") else "in"
        if w is None or h is None:                      # project saved without a size
            unit, (w, h) = "in", DEFAULT_SIZE_IN
        self._converting = True
        self.fig_unit.set(unit)
        self._last_unit = unit
        self.fig_w.set(self._fmt(w))
        self.fig_h.set(self._fmt(h))
        self._converting = False
        self._size_changed()

    def _fit_preview(self):
        """Show the figure with the chosen proportions, as large as fits."""
        if not hasattr(self, "preview_box"):
            return
        cw, ch = self.preview_box.winfo_width(), self.preview_box.winfo_height()
        if cw < 20 or ch < 20:
            return
        w_in, h_in = self._size_in
        px_per_in = min(cw / w_in, ch / h_in)
        # the figure keeps its real size in inches, so text and line widths look
        # exactly as they will in the saved PNG
        self.fig.set_dpi(px_per_in)
        self.preview_widget.place(relx=0.5, rely=0.5, anchor="center",
                                  width=max(1, int(w_in * px_per_in)),
                                  height=max(1, int(h_in * px_per_in)))
        self.preview.draw_idle()

    # ---- data model -------------------------------------------------------
    def _new_step(self, name="", val="", act=False):
        step = {"name": tk.StringVar(value=name),
                "val": tk.StringVar(value=val),
                "act": tk.BooleanVar(value=act)}
        for var in step.values():
            var.trace_add("write", lambda *_: self.schedule_redraw())
        return step

    def _default_color(self):
        """First default colour that no pathway is using yet."""
        used = {p["color"].lower() for p in self.pathways}
        return next((c for c in COLORS if c.lower() not in used),
                    COLORS[len(self.pathways) % len(COLORS)])

    def _valid_color(self, color):
        try:
            self.winfo_rgb(color)
            return True
        except (tk.TclError, TypeError):
            return False

    def pick_color(self, p, swatch):
        _, hex_color = colorchooser.askcolor(
            color=p["color"], parent=self,
            title=f"Color for {p['name'].get().strip() or 'pathway'}")
        if hex_color:
            p["color"] = hex_color
            swatch.configure(bg=hex_color)
            self.schedule_redraw()

    def _append_pathway(self, name, steps=None, color=None):
        if not (color and self._valid_color(color)):
            color = self._default_color()
        p = {"name": tk.StringVar(value=name), "color": color, "steps": []}
        p["name"].trace_add("write", lambda *_: self.schedule_redraw())
        for i in range(self.n_steps):
            if steps and i < len(steps):
                s = steps[i]
                p["steps"].append(self._new_step(s.get("name", ""), s.get("val", ""),
                                                 bool(s.get("act", False))))
            else:
                p["steps"].append(self._new_step())
        self.pathways.append(p)

    def add_pathway(self):
        if len(self.pathways) >= MAX_PATHWAYS:
            return
        self._append_pathway(f"Pathway {len(self.pathways) + 1}")
        self.rebuild_editor()
        self.schedule_redraw()

    def add_step(self):
        self.n_steps += 1
        for p in self.pathways:
            p["steps"].append(self._new_step())
        self.rebuild_editor()
        self.schedule_redraw()

    def get_data(self):
        return {
            "title": self.chart_title.get(),
            "ylabel": self.y_title.get(),
            "pathways": [
                {"name": p["name"].get(),
                 "color": p["color"],
                 "steps": [{"name": s["name"].get(), "val": s["val"].get(),
                            "act": s["act"].get()} for s in p["steps"]]}
                for p in self.pathways],
        }

    # ---- editor grid ------------------------------------------------------
    def rebuild_editor(self):
        gf = self.grid_frame
        for w in gf.winfo_children():
            w.destroy()

        for i in range(self.n_steps):
            ttk.Label(gf, text=f"Step {i + 1}",
                      font=("TkDefaultFont", 11, "bold")).grid(
                row=0, column=i + 1, padx=10, pady=(2, 4))

        for r, p in enumerate(self.pathways):
            row = r + 1
            cell = ttk.Frame(gf)
            cell.grid(row=row, column=0, padx=(2, 12), pady=6, sticky="w")
            swatch = tk.Label(cell, bg=p["color"], width=2, relief="solid", bd=1,
                              cursor="hand2")
            swatch.pack(side="left", padx=(0, 4))
            swatch.bind("<Button-1>", lambda e, p=p, sw=swatch: self.pick_color(p, sw))
            ttk.Entry(cell, textvariable=p["name"], width=16).pack(side="left")

            for i, s in enumerate(p["steps"]):
                f = ttk.Frame(gf, padding=(8, 0))
                f.grid(row=row, column=i + 1, pady=6)
                ttk.Label(f, text="name", foreground="gray").grid(row=0, column=0, sticky="e")
                ttk.Entry(f, textvariable=s["name"], width=12).grid(row=0, column=1, padx=3)
                ttk.Label(f, text="val", foreground="gray").grid(row=1, column=0, sticky="e")
                ttk.Entry(f, textvariable=s["val"], width=12).grid(row=1, column=1, padx=3)
                ttk.Checkbutton(f, text="activation", variable=s["act"]).grid(
                    row=2, column=0, columnspan=2, sticky="w")

            if r == 0:   # "+" to add a step, right of the last step
                ttk.Button(gf, text="+", width=3, command=self.add_step).grid(
                    row=row, column=self.n_steps + 1, padx=10)

        add_p = ttk.Button(gf, text="+", width=3, command=self.add_pathway)
        add_p.grid(row=len(self.pathways) + 1, column=0, padx=2, pady=6, sticky="w")
        if len(self.pathways) >= MAX_PATHWAYS:
            add_p.state(["disabled"])

        # keep whichever box gets keyboard focus (e.g. via Tab) in view
        def bind_focus(widget):
            for child in widget.winfo_children():
                if child.winfo_class() in ("TEntry", "TCheckbutton", "TButton"):
                    child.bind("<FocusIn>",
                               lambda e: self._ensure_visible(e.widget), add="+")
                bind_focus(child)
        bind_focus(gf)

        self.after_idle(self._fit_editor)

    # ---- drawing ----------------------------------------------------------
    def schedule_redraw(self):
        if self._pending is None:
            self._pending = self.after(60, self.redraw)

    def redraw(self):
        self._pending = None
        draw_figure(self.fig, self.get_data())
        self.preview.draw_idle()

    # ---- file actions -----------------------------------------------------
    def _base_name(self):
        name = self.file_name.get().strip() or "figure"
        return "".join(c for c in name if c not in '<>:"/\\|?*')

    def save_png(self):
        size = self._read_size()
        if size is None:
            messagebox.showerror("Invalid figure size",
                                 f"Width and height must be numbers between "
                                 f"{MIN_IN:g} and {MAX_IN:g} inches.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".png", initialfile=self._base_name() + ".png",
            filetypes=[("PNG image", "*.png")])
        if not path:
            return
        fig = Figure(figsize=size, dpi=300, layout="constrained")
        draw_figure(fig, self.get_data())
        fig.savefig(path, dpi=300, facecolor="white")
        messagebox.showinfo("Saved", f"Figure saved to\n{path}")

    def save_project(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".json", initialfile=self._base_name() + ".json",
            filetypes=[("Pathway project", "*.json")])
        if not path:
            return
        data = self.get_data()
        data["file_name"] = self.file_name.get()
        data["fig_width"] = self.fig_w.get()
        data["fig_height"] = self.fig_h.get()
        data["fig_unit"] = self.fig_unit.get()
        data["version"] = 1
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        messagebox.showinfo("Saved", f"Project saved to\n{path}")

    def load_project(self):
        path = filedialog.askopenfilename(filetypes=[("Pathway project", "*.json")])
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            pathways = data["pathways"][:MAX_PATHWAYS]
            if not pathways:
                raise ValueError("no pathways in file")
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Could not load", f"{path}\n\n{exc}")
            return

        self.file_name.set(data.get("file_name", os.path.splitext(os.path.basename(path))[0]))
        self.chart_title.set(data.get("title", ""))
        self.y_title.set(data.get("ylabel", ""))
        self._set_size_fields(data.get("fig_width"), data.get("fig_height"),
                              data.get("fig_unit"))
        self.n_steps = max(1, max(len(p.get("steps", [])) for p in pathways))
        self.pathways = []
        for i, p in enumerate(pathways):
            self._append_pathway(p.get("name", f"Pathway {i + 1}"), p.get("steps", []),
                                 p.get("color"))
        self.rebuild_editor()
        self.schedule_redraw()


if __name__ == "__main__":
    App().mainloop()