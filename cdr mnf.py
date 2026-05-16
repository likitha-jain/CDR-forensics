import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import pandas as pd
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import re
import os
import json
import urllib.request
import urllib.parse
import webbrowser

# ══════════════════════════════════════════════════════════════════════════════
#  CONFIG & STYLING
# ══════════════════════════════════════════════════════════════════════════════
C = {
    "bg":        "#F1F5F9",
    "card":      "#FFFFFF",
    "accent":    "#4F46E5",
    "accent2":   "#7C3AED",
    "green":     "#10B981",
    "amber":     "#F59E0B",
    "red":       "#EF4444",
    "secondary": "#64748B",
    "border":    "#E2E8F0",
    "row_even":  "#F8FAFC",
    "row_odd":   "#FFFFFF",
    "incoming":  "#D1FAE5",
    "outgoing":  "#EDE9FE",
    "missed":    "#FEE2E2",
    "rejected":  "#FEF3C7",
}

F = {
    "title":  ("Segoe UI", 12, "bold"),
    "stat":   ("Segoe UI", 20, "bold"),
    "label":  ("Segoe UI",  9),
    "mono":   ("Consolas", 10),
    "small":  ("Segoe UI",  8),
    "header": ("Segoe UI",  9, "bold"),
}


def _dk(h, f=0.85):
    h = h.lstrip("#")
    r, g, b = (int(h[i:i+2], 16) for i in (0, 2, 4))
    return "#{:02x}{:02x}{:02x}".format(*(int(c * f) for c in (r, g, b)))


def styled_btn(parent, text, cmd, color=None, fg="#FFFFFF", padx=14, pady=6):
    color = color or C["accent"]
    b = tk.Button(parent, text=text, command=cmd, bg=color, fg=fg,
                  font=F["label"], relief="flat", bd=0, cursor="hand2",
                  activebackground=_dk(color), activeforeground=fg,
                  padx=padx, pady=pady)
    b.bind("<Enter>", lambda e: b.config(bg=_dk(color)))
    b.bind("<Leave>", lambda e: b.config(bg=color))
    return b


def labeled_entry(parent, label, width=22, show=None):
    """Returns (frame, entry_widget)."""
    f = tk.Frame(parent, bg=C["card"])
    tk.Label(f, text=label, bg=C["card"], fg=C["secondary"],
             font=F["small"]).pack(anchor="w")
    kw = dict(font=F["mono"], width=width, relief="solid",
              bd=1, bg=C["bg"], fg="#1E293B",
              highlightbackground=C["border"], highlightthickness=0)
    if show:
        kw["show"] = show
    e = tk.Entry(f, **kw)
    e.pack(fill=tk.X)
    return f, e


# ══════════════════════════════════════════════════════════════════════════════
#  DURATION PARSER & FORMATTER
# ══════════════════════════════════════════════════════════════════════════════
def parse_duration(v):
    """Convert any duration string/number to total seconds."""
    try:
        if pd.isna(v):
            return 0
        s = str(v).strip()
        # HH:MM:SS
        if re.match(r'^\d+:\d+:\d+$', s):
            h, m, sec = s.split(":")
            return int(h) * 3600 + int(m) * 60 + int(sec)
        # MM:SS
        if re.match(r'^\d+:\d+$', s):
            m, sec = s.split(":")
            return int(m) * 60 + int(sec)
        # 00h 00m 30s
        sl = s.lower()
        h   = int(re.search(r'(\d+)\s*h', sl).group(1)) if re.search(r'\d+\s*h', sl) else 0
        m   = int(re.search(r'(\d+)\s*m', sl).group(1)) if re.search(r'\d+\s*m', sl) else 0
        sec = int(re.search(r'(\d+)\s*s', sl).group(1)) if re.search(r'\d+\s*s', sl) else 0
        if h or m or sec:
            return h * 3600 + m * 60 + sec
        return int(float(s))
    except Exception:
        return 0


def fmt_dur(seconds):
    try:
        seconds = int(seconds)
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        return f"{h:02d}h {m:02d}m {s:02d}s"
    except Exception:
        return "00h 00m 00s"


# ══════════════════════════════════════════════════════════════════════════════
#  TILE WIDGET
# ══════════════════════════════════════════════════════════════════════════════
class Tile(tk.Frame):
    def __init__(self, parent, label, color):
        super().__init__(parent, bg=C["card"], padx=20, pady=14,
                         highlightbackground=C["border"],
                         highlightthickness=1)
        self._var = tk.Label(self, text="0", fg=color,
                             bg=C["card"], font=F["stat"])
        self._var.pack()
        tk.Label(self, text=label.upper(), fg=C["secondary"],
                 bg=C["card"], font=("Segoe UI", 7, "bold")).pack()

    def set(self, v):
        self._var.config(text=str(v))


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN APP
# ══════════════════════════════════════════════════════════════════════════════
class SmartCDR:
    def __init__(self, root):
        self.root = root
        self.root.title("Forensic CDR Analyzer Pro")
        self.root.geometry("1350x920")
        self.root.configure(bg=C["bg"])
        self.root.minsize(1000, 700)

        self.df        = pd.DataFrame()
        self._csv_path = None
        self._owner    = None          # detected device number

        self._apply_ttk()
        self._build_ui()

    # ── TTK theme ─────────────────────────────────────────────────────────────
    def _apply_ttk(self):
        s = ttk.Style(self.root)
        s.theme_use("clam")
        s.configure("TNotebook",
                    background=C["bg"], borderwidth=0, tabmargins=[0, 0, 0, 0])
        s.configure("TNotebook.Tab",
                    background=C["card"], foreground=C["secondary"],
                    font=F["label"], padding=[18, 8], borderwidth=0)
        s.map("TNotebook.Tab",
              background=[("selected", C["accent"])],
              foreground=[("selected", "#FFFFFF")])
        s.configure("Treeview",
                    background=C["card"], fieldbackground=C["card"],
                    foreground="#1E293B", font=("Consolas", 9),
                    rowheight=24, borderwidth=0)
        s.configure("Treeview.Heading",
                    background=C["accent"], foreground="#FFFFFF",
                    font=("Segoe UI", 9, "bold"), relief="flat")
        s.map("Treeview",
              background=[("selected", C["accent"])],
              foreground=[("selected", "#FFFFFF")])
        s.configure("Vertical.TScrollbar",
                    background=C["border"], troughcolor=C["bg"],
                    arrowcolor=C["accent"], borderwidth=0)
        s.configure("Horizontal.TScrollbar",
                    background=C["border"], troughcolor=C["bg"],
                    arrowcolor=C["accent"], borderwidth=0)

    # ── UI skeleton ───────────────────────────────────────────────────────────
    def _build_ui(self):
        # Header
        hdr = tk.Frame(self.root, bg=C["card"], height=58,
                       highlightbackground=C["border"], highlightthickness=1)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)
        tk.Label(hdr, text="◈  CDR FORENSICS", bg=C["card"], fg=C["accent"],
                 font=("Segoe UI", 13, "bold")).pack(side=tk.LEFT, padx=22)
        self._owner_lbl = tk.Label(hdr, text="", bg=C["card"],
                                   fg=C["secondary"], font=F["small"])
        self._owner_lbl.pack(side=tk.RIGHT, padx=22)

        # Notebook
        self.nb = ttk.Notebook(self.root)
        self.nb.pack(fill=tk.BOTH, expand=True, padx=16, pady=12)

        self._tab_load   = tk.Frame(self.nb, bg=C["bg"])
        self._tab_search = tk.Frame(self.nb, bg=C["bg"])
        self._tab_geo    = tk.Frame(self.nb, bg=C["bg"])

        self.nb.add(self._tab_load,   text="  📂  Data Input  ")
        self.nb.add(self._tab_search, text="  📊  Search & Analysis  ")
        self.nb.add(self._tab_geo,    text="  🌍  Live Geo Lookup  ")

        self._setup_load_tab()
        self._setup_search_tab()
        self._setup_geo_tab()

    # ══════════════════════════════════════════════════════════════════════════
    #  TAB 1 — DATA INPUT
    # ══════════════════════════════════════════════════════════════════════════
    def _setup_load_tab(self):
        outer = tk.Frame(self._tab_load, bg=C["bg"])
        outer.place(relx=0.5, rely=0.42, anchor="center")

        card = tk.Frame(outer, bg=C["card"],
                        highlightbackground=C["border"],
                        highlightthickness=1, padx=50, pady=40)
        card.pack()

        tk.Frame(card, bg=C["accent"], height=5).pack(fill=tk.X, pady=(0, 20))

        tk.Label(card, text="◈  LOAD CDR FILE", bg=C["card"], fg=C["accent"],
                 font=("Segoe UI", 14, "bold")).pack()
        tk.Label(card, text="Supports CSV exports  ·  columns auto-detected",
                 bg=C["card"], fg=C["secondary"], font=F["small"]).pack(pady=(4, 18))

        styled_btn(card, "  📂  Browse CSV  ", self.load_file).pack(pady=4)

        self._file_lbl = tk.Label(card, text="No file loaded.",
                                  bg=C["card"], fg=C["secondary"],
                                  font=F["small"], wraplength=360)
        self._file_lbl.pack(pady=(10, 0))

        # stat tiles below card
        row = tk.Frame(outer, bg=C["bg"])
        row.pack(pady=(22, 0))

        self._t_total   = Tile(row, "Total Records",  C["accent"])
        self._t_contact = Tile(row, "Unique Contacts", C["green"])
        self._t_dur     = Tile(row, "Total Duration",  C["amber"])
        self._t_missed  = Tile(row, "Missed / Rejected", C["red"])

        for t in (self._t_total, self._t_contact, self._t_dur, self._t_missed):
            t.pack(side=tk.LEFT, padx=7)

    # ══════════════════════════════════════════════════════════════════════════
    #  TAB 2 — SEARCH & ANALYSIS
    # ══════════════════════════════════════════════════════════════════════════
    def _setup_search_tab(self):
        # ── search bar ──────────────────────────────────────────────────────
        sbar = tk.Frame(self._tab_search, bg=C["card"],
                        highlightbackground=C["border"],
                        highlightthickness=1, padx=16, pady=12)
        sbar.pack(fill=tk.X, padx=8, pady=(8, 4))

        tk.Label(sbar, text="🔍  Target Number / Name:",
                 bg=C["card"], fg=C["secondary"],
                 font=F["label"]).pack(side=tk.LEFT, padx=(0, 8))

        self._search_var = tk.StringVar()
        se = tk.Entry(sbar, textvariable=self._search_var, font=F["mono"],
                      width=28, relief="solid", bd=1, bg=C["bg"])
        se.pack(side=tk.LEFT, padx=(0, 10))
        se.bind("<Return>", lambda e: self._run_analysis())

        styled_btn(sbar, "Analyze Contact", self._run_analysis).pack(side=tk.LEFT, padx=4)
        styled_btn(sbar, "Show All", self._reset_analysis,
                   color=C["secondary"]).pack(side=tk.LEFT, padx=4)

        # call-type filter
        tk.Label(sbar, text="  Type:", bg=C["card"],
                 fg=C["secondary"], font=F["label"]).pack(side=tk.LEFT, padx=(12, 4))
        self._type_var = tk.StringVar(value="All")
        om = ttk.Combobox(sbar, textvariable=self._type_var, width=12,
                          values=["All", "Incoming", "Outgoing", "Missed", "Rejected"],
                          state="readonly", font=F["label"])
        om.pack(side=tk.LEFT)
        om.bind("<<ComboboxSelected>>", lambda e: self._run_analysis())

        self._row_lbl = tk.Label(sbar, text="", bg=C["card"],
                                 fg=C["secondary"], font=F["small"])
        self._row_lbl.pack(side=tk.RIGHT, padx=8)

        # ── tiles ───────────────────────────────────────────────────────────
        trow = tk.Frame(self._tab_search, bg=C["bg"])
        trow.pack(fill=tk.X, padx=8, pady=4)

        self._s_total = Tile(trow, "Total Calls",    C["accent"])
        self._s_mins  = Tile(trow, "Total Minutes",  C["green"])
        self._s_freq  = Tile(trow, "Calls / Day",    C["amber"])
        self._s_miss  = Tile(trow, "Missed/Rejected", C["red"])

        for t in (self._s_total, self._s_mins, self._s_freq, self._s_miss):
            t.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)

        # ── paned: table | charts ────────────────────────────────────────────
        pane = tk.PanedWindow(self._tab_search, orient=tk.HORIZONTAL,
                              bg=C["border"], sashwidth=4, sashrelief="flat")
        pane.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        # table side
        tbl_f = tk.Frame(pane, bg=C["bg"])
        pane.add(tbl_f, width=560)

        cols = ("dt", "name", "ph", "dur", "typ")
        self._tree = ttk.Treeview(tbl_f, columns=cols, show="headings",
                                  selectmode="browse")
        hdrs = ["Date / Time", "Name", "Phone", "Duration", "Type"]
        widths = [148, 130, 130, 110, 90]
        for col, h, w in zip(cols, hdrs, widths):
            self._tree.heading(col, text=h)
            self._tree.column(col, width=w, minwidth=60, anchor="center")

        vsb = ttk.Scrollbar(tbl_f, orient="vertical",   command=self._tree.yview)
        hsb = ttk.Scrollbar(tbl_f, orient="horizontal", command=self._tree.xview)
        self._tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side=tk.RIGHT,  fill=tk.Y)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)
        self._tree.pack(fill=tk.BOTH, expand=True)

        self._tree.tag_configure("Incoming", background=C["incoming"])
        self._tree.tag_configure("Outgoing", background=C["outgoing"])
        self._tree.tag_configure("Missed",   background=C["missed"])
        self._tree.tag_configure("Rejected", background=C["rejected"])

        # chart side
        self._vis_f = tk.Frame(pane, bg=C["card"])
        pane.add(self._vis_f, width=660)

    # ══════════════════════════════════════════════════════════════════════════
    #  TAB 3 — LIVE GEO LOOKUP
    # ══════════════════════════════════════════════════════════════════════════
    def _setup_geo_tab(self):
        # ── top: input panel ────────────────────────────────────────────────
        inp = tk.Frame(self._tab_geo, bg=C["card"],
                       highlightbackground=C["border"],
                       highlightthickness=1, padx=22, pady=18)
        inp.pack(fill=tk.X, padx=10, pady=(10, 0))

        tk.Label(inp, text="🌍  CELL TOWER GEO LOOKUP  —  Unwired Labs API",
                 bg=C["card"], fg=C["accent"],
                 font=("Segoe UI", 11, "bold")).grid(row=0, column=0,
                 columnspan=6, sticky="w", pady=(0, 14))

        # API Key
        fk, self._geo_apikey = labeled_entry(inp, "API Key", width=36)
        fk.grid(row=1, column=0, columnspan=2, padx=(0, 16), sticky="ew")

        # MCC
        fm, self._geo_mcc = labeled_entry(inp, "MCC", width=8)
        fm.grid(row=1, column=2, padx=(0, 10), sticky="ew")

        # MNC
        fn, self._geo_mnc = labeled_entry(inp, "MNC", width=8)
        fn.grid(row=1, column=3, padx=(0, 10), sticky="ew")

        # TAC / LAC
        ft, self._geo_lac = labeled_entry(inp, "TAC / LAC", width=12)
        ft.grid(row=1, column=4, padx=(0, 10), sticky="ew")

        # Cell ID
        fc, self._geo_cellid = labeled_entry(inp, "Cell ID", width=14)
        fc.grid(row=1, column=5, padx=(0, 10), sticky="ew")

        # Radio type
        fr = tk.Frame(inp, bg=C["card"])
        fr.grid(row=1, column=6, padx=(0, 16), sticky="ew")
        tk.Label(fr, text="Radio Type", bg=C["card"], fg=C["secondary"],
                 font=F["small"]).pack(anchor="w")
        self._geo_radio = tk.StringVar(value="LTE")
        radio_cb = ttk.Combobox(fr, textvariable=self._geo_radio,
                                values=["GSM", "UMTS", "LTE", "NR"],
                                width=8, state="readonly", font=F["label"])
        radio_cb.pack()

        # Lookup button
        fb = tk.Frame(inp, bg=C["card"])
        fb.grid(row=1, column=7, padx=(10, 0), sticky="s")
        styled_btn(fb, "  🔍  Lookup Location  ",
                   self._geo_lookup, color=C["accent"]).pack()
        styled_btn(fb, "  🗺  Open in Maps  ",
                   self._open_maps, color=C["green"],
                   padx=10, pady=4).pack(pady=(6, 0))

        # ── middle: result info strip ────────────────────────────────────────
        self._geo_result_f = tk.Frame(self._tab_geo, bg=C["card"],
                                      highlightbackground=C["border"],
                                      highlightthickness=1, padx=22, pady=12)
        self._geo_result_f.pack(fill=tk.X, padx=10, pady=(6, 0))

        tk.Label(self._geo_result_f, text="Result",
                 bg=C["card"], fg=C["secondary"],
                 font=F["header"]).pack(anchor="w")

        self._geo_info = tk.Label(self._geo_result_f,
                                  text="Enter cell tower details and click Lookup.",
                                  bg=C["card"], fg=C["secondary"],
                                  font=F["label"], anchor="w", justify="left")
        self._geo_info.pack(anchor="w", pady=(4, 0))

        # coordinate tiles
        coord_row = tk.Frame(self._geo_result_f, bg=C["card"])
        coord_row.pack(fill=tk.X, pady=(10, 0))

        self._g_lat  = self._geo_tile(coord_row, "Latitude",  C["accent"])
        self._g_lon  = self._geo_tile(coord_row, "Longitude", C["accent2"])
        self._g_acc  = self._geo_tile(coord_row, "Accuracy (m)", C["amber"])
        self._g_addr = self._geo_tile(coord_row, "Address / Area", C["green"], wide=True)

        # ── bottom: embedded map (HTML via WebView fallback = tkinter canvas) ─
        map_hdr = tk.Frame(self._tab_geo, bg=C["accent"], padx=10, pady=5)
        map_hdr.pack(fill=tk.X, padx=10, pady=(6, 0))
        tk.Label(map_hdr, text="▸ MAP PREVIEW  (pin drops on lookup)",
                 bg=C["accent"], fg="#FFFFFF", font=F["header"]).pack(side=tk.LEFT)
        self._map_status = tk.Label(map_hdr, text="",
                                    bg=C["accent"], fg="#C7D2FE", font=F["small"])
        self._map_status.pack(side=tk.RIGHT, padx=8)

        self._map_frame = tk.Frame(self._tab_geo, bg=C["bg"],
                                   highlightbackground=C["border"],
                                   highlightthickness=1)
        self._map_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 8))

        self._lat = None
        self._lon = None

        # Draw placeholder canvas map
        self._draw_map_placeholder()

    def _geo_tile(self, parent, label, color, wide=False):
        f = tk.Frame(parent, bg=C["card"],
                     highlightbackground=C["border"],
                     highlightthickness=1,
                     padx=16, pady=10)
        f.pack(side=tk.LEFT, padx=(0, 8), fill=tk.X,
               expand=True if wide else False)
        tk.Label(f, text=label.upper(), bg=C["card"],
                 fg=C["secondary"], font=("Segoe UI", 7, "bold")).pack(anchor="w")
        v = tk.Label(f, text="—", bg=C["card"], fg=color,
                     font=("Segoe UI", 11, "bold"))
        v.pack(anchor="w")
        return v

    def _draw_map_placeholder(self, lat=None, lon=None, label=""):
        for w in self._map_frame.winfo_children():
            w.destroy()

        fig = plt.Figure(figsize=(10, 4), dpi=88)
        fig.patch.set_facecolor(C["bg"])
        ax = fig.add_subplot(111)
        ax.set_facecolor("#E8EFFE")
        ax.set_xlim(-180, 180)
        ax.set_ylim(-90, 90)
        ax.set_xlabel("Longitude", fontsize=8, color=C["secondary"])
        ax.set_ylabel("Latitude",  fontsize=8, color=C["secondary"])
        ax.set_title("World Map  —  Cell Tower Pin",
                     fontsize=9, color=C["accent"])
        ax.tick_params(colors=C["secondary"], labelsize=7)
        ax.spines[:].set_edgecolor(C["border"])
        ax.grid(True, linestyle="--", alpha=0.4, color=C["border"])

        # Draw simple world outline using basic shapes
        ax.axhline(0, color=C["border"], lw=0.8, alpha=0.5)
        ax.axvline(0, color=C["border"], lw=0.8, alpha=0.5)

        if lat is not None and lon is not None:
            ax.plot(lon, lat, marker="*", color=C["red"],
                    markersize=18, zorder=5)
            ax.annotate(
                f"  📍 {label}\n  ({lat:.4f}, {lon:.4f})",
                xy=(lon, lat),
                fontsize=8, color=C["accent"],
                bbox=dict(boxstyle="round,pad=0.3",
                          fc="white", ec=C["accent"], lw=1)
            )
            ax.set_xlim(max(-180, lon - 12), min(180, lon + 12))
            ax.set_ylim(max(-90,  lat - 8),  min(90,  lat + 8))

        fig.tight_layout()
        canvas = FigureCanvasTkAgg(fig, master=self._map_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        plt.close(fig)

    # ══════════════════════════════════════════════════════════════════════════
    #  GEO LOOKUP  (Unwired Labs API)
    # ══════════════════════════════════════════════════════════════════════════
    def _geo_lookup(self):
        api_key = self._geo_apikey.get().strip()
        mcc     = self._geo_mcc.get().strip()
        mnc     = self._geo_mnc.get().strip()
        lac     = self._geo_lac.get().strip()
        cellid  = self._geo_cellid.get().strip()
        radio   = self._geo_radio.get().strip().lower()

        if not api_key:
            messagebox.showwarning("API Key Missing",
                                   "Please enter your Unwired Labs API key.")
            return
        if not all([mcc, mnc, lac, cellid]):
            messagebox.showwarning("Missing Fields",
                                   "Please fill in MCC, MNC, TAC/LAC, and Cell ID.")
            return

        try:
            mcc_i    = int(mcc)
            mnc_i    = int(mnc)
            lac_i    = int(lac)
            cellid_i = int(cellid)
        except ValueError:
            messagebox.showerror("Invalid Input",
                                 "MCC, MNC, TAC/LAC, and Cell ID must be integers.")
            return

        payload = json.dumps({
            "token":  api_key,
            "radio":  radio,
            "mcc":    mcc_i,
            "mnc":    mnc_i,
            "cells":  [{"lac": lac_i, "cid": cellid_i}],
            "address": 1
        }).encode("utf-8")

        try:
            req = urllib.request.Request(
                "https://us1.unwiredlabs.com/v2/process.php",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as ex:
            messagebox.showerror("Network Error", str(ex))
            return

        if data.get("status") != "ok":
            msg = data.get("message", "Unknown error from Unwired Labs.")
            messagebox.showerror("Lookup Failed", msg)
            self._geo_info.config(
                text=f"❌  Lookup failed: {msg}", fg=C["red"])
            return

        self._lat = data.get("lat")
        self._lon = data.get("lon")
        acc  = data.get("accuracy", "?")
        addr = data.get("address", {})

        if isinstance(addr, dict):
            area = ", ".join(filter(None, [
                addr.get("road") or addr.get("suburb"),
                addr.get("city") or addr.get("town") or addr.get("village"),
                addr.get("state"),
                addr.get("country"),
            ])) or "—"
        else:
            area = str(addr) if addr else "—"

        self._g_lat.config(text=f"{self._lat:.6f}")
        self._g_lon.config(text=f"{self._lon:.6f}")
        self._g_acc.config(text=str(acc))
        self._g_addr.config(text=area)

        self._geo_info.config(
            text=f"✔  Cell resolved  ·  MCC {mcc}  MNC {mnc}  LAC {lac}  CID {cellid}  ·  Accuracy ±{acc} m",
            fg=C["green"]
        )
        self._map_status.config(text=f"Pin @ {self._lat:.5f}, {self._lon:.5f}")
        self._draw_map_placeholder(self._lat, self._lon,
                                   label=f"{area[:30]}…" if len(area) > 30 else area)

    def _open_maps(self):
        if self._lat is None or self._lon is None:
            messagebox.showinfo("No Location",
                                "Run a successful lookup first.")
            return
        url = f"https://www.google.com/maps?q={self._lat},{self._lon}"
        webbrowser.open(url)

    # ══════════════════════════════════════════════════════════════════════════
    #  FILE LOAD & PROCESSING
    # ══════════════════════════════════════════════════════════════════════════
    def load_file(self):
        path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])
        if not path:
            return
        try:
            self._csv_path = path
            self._process_data()
            self._file_lbl.config(text=f"✔  {os.path.basename(path)}")
            self._reset_analysis()
            self.nb.select(self._tab_search)
        except Exception as ex:
            messagebox.showerror("Load Error", str(ex))

    def _process_data(self):
        raw = pd.read_csv(self._csv_path)
        raw.columns = [str(c).strip() for c in raw.columns]

        # ── Detect columns ────────────────────────────────────────────────
        def find_col(*keywords):
            for k in keywords:
                for col in raw.columns:
                    if k.lower() in col.lower():
                        return col
            return None

        c_date   = find_col("date time", "datetime", "timestamp", "date")
        c_type   = find_col("type", "call type", "status")
        c_dur    = find_col("duration", "secs", "time")
        c_from   = find_col("from number", "from", "calling")
        c_to     = find_col("to number", "to", "dialled", "contact", "number", "phone")
        c_name   = find_col("name", "contact name")

        if not all([c_date, c_type, c_dur, c_from, c_to]):
            raise ValueError(
                "Could not detect required columns.\n"
                f"Found: {list(raw.columns)}"
            )

        self.df = pd.DataFrame()
        self.df["DateTime"]  = pd.to_datetime(raw[c_date],  errors="coerce")
        self.df["FromNum"]   = raw[c_from].astype(str)
        self.df["ToNum"]     = raw[c_to].astype(str)
        self.df["CallType"]  = raw[c_type].fillna("Unknown").astype(str).str.strip()
        self.df["Name"]      = raw[c_name].astype(str) if c_name else "—"
        self.df["DurSecs"]   = raw[c_dur].apply(parse_duration)
        self.df["DurStr"]    = self.df["DurSecs"].apply(fmt_dur)
        self.df["Hour"]      = self.df["DateTime"].dt.hour
        self.df = self.df.dropna(subset=["DateTime"])

        # Detect owner (most frequent From Number)
        self._owner = self.df["FromNum"].value_counts().idxmax()
        self._owner_lbl.config(
            text=f"Device Number: {self._mask(self._owner)}")

        # Build "Contact" = the other party
        def contact(row):
            return (row["ToNum"]
                    if row["FromNum"] == self._owner
                    else row["FromNum"])

        self.df["Contact"] = self.df.apply(contact, axis=1)

        # Display name: prefer Name column if not blank/Unknown
        def display_name(row):
            n = str(row["Name"]).strip()
            if n and n.lower() not in ("nan", "unknown", "—", ""):
                return n
            return row["Contact"]

        self.df["DisplayName"] = self.df.apply(display_name, axis=1)

        # Update load tab tiles
        missed = self.df["CallType"].isin(["Missed", "Rejected"]).sum()
        self._t_total.set(len(self.df))
        self._t_contact.set(self.df["Contact"].nunique())
        self._t_dur.set(fmt_dur(self.df["DurSecs"].sum()))
        self._t_missed.set(int(missed))

    # ══════════════════════════════════════════════════════════════════════════
    #  MASK
    # ══════════════════════════════════════════════════════════════════════════
    @staticmethod
    def _mask(val):
        s = str(val)
        if len(s) > 6:
            return f"{s[:3]}****{s[-3:]}"
        return s

    # ══════════════════════════════════════════════════════════════════════════
    #  ANALYSIS CORE
    # ══════════════════════════════════════════════════════════════════════════
    def _run_analysis(self):
        if self.df.empty:
            messagebox.showinfo("No Data", "Load a CSV file first.")
            return
        query     = self._search_var.get().strip()
        type_filt = self._type_var.get()

        data = self.df.copy()

        if query:
            mask = (
                data["Contact"].str.contains(query, case=False, na=False) |
                data["DisplayName"].str.contains(query, case=False, na=False) |
                data["ToNum"].str.contains(query, case=False, na=False) |
                data["FromNum"].str.contains(query, case=False, na=False)
            )
            data = data[mask]
            if data.empty:
                messagebox.showinfo("No Results",
                                    f"No records match: {query}")
                return

        if type_filt != "All":
            data = data[data["CallType"] == type_filt]

        self._update_ui(data)

    def _reset_analysis(self):
        if self.df.empty:
            return
        self._search_var.set("")
        self._type_var.set("All")
        self._update_ui(self.df)

    # ══════════════════════════════════════════════════════════════════════════
    #  UPDATE UI
    # ══════════════════════════════════════════════════════════════════════════
    def _update_ui(self, data):
        # ── Tiles ──────────────────────────────────────────────────────────
        self._s_total.set(len(data))
        self._s_mins.set(round(data["DurSecs"].sum() / 60, 1))
        span = max((data["DateTime"].max() - data["DateTime"].min()).days, 1)
        self._s_freq.set(round(len(data) / span, 1))
        self._s_miss.set(int(data["CallType"].isin(["Missed", "Rejected"]).sum()))

        # ── Table ───────────────────────────────────────────────────────────
        for item in self._tree.get_children():
            self._tree.delete(item)

        for _, r in data.iterrows():
            dt  = r["DateTime"].strftime("%Y-%m-%d  %H:%M")
            nm  = str(r["DisplayName"])[:22]
            ph  = self._mask(r["Contact"])
            dur = r["DurStr"]
            ct  = r["CallType"]
            tag = ct if ct in ("Incoming", "Outgoing", "Missed", "Rejected") else ""
            self._tree.insert("", "end", values=(dt, nm, ph, dur, ct), tags=(tag,))

        n = len(data)
        self._row_lbl.config(
            text=f"{n} record{'s' if n != 1 else ''}")

        # ── Charts ──────────────────────────────────────────────────────────
        for w in self._vis_f.winfo_children():
            w.destroy()

        plt.rcParams.update({
            "figure.facecolor": C["card"],
            "axes.facecolor":   C["bg"],
            "axes.edgecolor":   C["border"],
            "axes.labelcolor":  C["secondary"],
            "xtick.color":      C["secondary"],
            "ytick.color":      C["secondary"],
            "text.color":       "#1E293B",
            "grid.color":       C["border"],
            "grid.linestyle":   "--",
            "grid.alpha":       0.5,
            "font.family":      "sans-serif",
        })

        fig = plt.Figure(figsize=(6.8, 5.4), dpi=92)

        # ── Pie: call distribution ──
        ax1 = fig.add_subplot(221)
        counts = data["CallType"].value_counts()
        pie_colors = {
            "Incoming": "#10B981", "Outgoing": "#4F46E5",
            "Missed":   "#EF4444", "Rejected": "#F59E0B",
        }
        clrs = [pie_colors.get(k, "#94A3B8") for k in counts.index]
        if not counts.empty:
            wedges, texts, autotexts = ax1.pie(
                counts, labels=None, autopct="%1.0f%%",
                startangle=140, colors=clrs,
                wedgeprops={"linewidth": 1.2, "edgecolor": "white"}
            )
            for at in autotexts:
                at.set_fontsize(7)
            ax1.legend(counts.index, fontsize=7,
                       loc="lower center", ncol=2,
                       bbox_to_anchor=(0.5, -0.18))
        ax1.set_title("Call Distribution", fontsize=9, pad=6)

        # ── Bar: peak hours ──
        ax2 = fig.add_subplot(222)
        hourly = data["Hour"].value_counts().sort_index()
        if not hourly.empty:
            bars = ax2.bar(hourly.index, hourly.values,
                           color=C["accent"], alpha=0.85, width=0.7)
            ax2.set_xlabel("Hour of Day", fontsize=7)
            ax2.set_ylabel("Calls", fontsize=7)
            ax2.set_xticks(range(0, 24, 2))
            ax2.tick_params(labelsize=7)
            ax2.grid(True, axis="y")
        ax2.set_title("Peak Hours", fontsize=9, pad=6)

        # ── Line: daily call trend ──
        ax3 = fig.add_subplot(212)
        if not data.empty:
            daily = data.groupby(data["DateTime"].dt.date).size()
            if len(daily) > 1:
                ax3.fill_between(range(len(daily)), daily.values,
                                 color=C["accent"], alpha=0.15)
                ax3.plot(range(len(daily)), daily.values,
                         color=C["accent"], lw=2,
                         marker="o", ms=3.5)
                # label every Nth date to avoid clutter
                step = max(1, len(daily) // 8)
                ax3.set_xticks(range(0, len(daily), step))
                ax3.set_xticklabels(
                    [str(d) for d in list(daily.index)[::step]],
                    rotation=28, ha="right", fontsize=7
                )
                ax3.set_ylabel("Calls / Day", fontsize=7)
                ax3.grid(True, axis="y")
            else:
                ax3.text(0.5, 0.5, "Not enough dates for trend",
                         ha="center", va="center", fontsize=8,
                         color=C["secondary"])
                ax3.axis("off")
        ax3.set_title("Daily Call Trend", fontsize=9, pad=6)

        fig.tight_layout(pad=1.5)

        canvas = FigureCanvasTkAgg(fig, master=self._vis_f)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        plt.close(fig)


# ══════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    root = tk.Tk()
    app  = SmartCDR(root)
    root.mainloop()