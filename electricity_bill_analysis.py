
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.patches import Patch
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

COLUMNS = ["month", "units", "bill"]
NORMAL_COLOR, UNUSUAL_COLOR = "#4a90d9", "#d9534f"


def process_data(df):
    """Clean and validate raw data; add cost per unit."""
    df = df.copy()
    df.columns = df.columns.str.strip().str.lower()
    missing = set(COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"Missing column(s): {', '.join(sorted(missing))}")
    df["month"] = pd.to_datetime(df["month"], errors="coerce")
    df["units"] = pd.to_numeric(df["units"], errors="coerce")
    df["bill"] = pd.to_numeric(df["bill"], errors="coerce")
    df = df.dropna(subset=COLUMNS)
    df = df[(df["units"] > 0) & (df["bill"] >= 0)]
    df["month"] = df["month"].dt.to_period("M").dt.to_timestamp()
    df = df.drop_duplicates("month", keep="last").sort_values("month").reset_index(drop=True)
    df["cost_per_unit"] = (df["bill"] / df["units"]).round(2)
    return df[COLUMNS + ["cost_per_unit"]]

def analyze(df):
    df = df.copy()
    df["prev_units"] = df["units"].shift(1)
    df["units_change_%"] = (df["units"].pct_change() * 100).round(1)
    df["bill_change_%"] = (df["bill"].pct_change() * 100).replace([np.inf, -np.inf], np.nan).round(1)

    total_units, total_bill = df["units"].sum(), df["bill"].sum()
    stats = {
        "months": len(df),
        "total_units": total_units,
        "total_bill": total_bill,
        "avg_units": df["units"].mean(),
        "avg_bill": df["bill"].mean(),
        "avg_rate": total_bill / total_units,
        "peak": df.loc[df["bill"].idxmax()],
        "lowest": df.loc[df["bill"].idxmin()],
        "trend": None, "fit_units": None, "next_units": None, "next_bill": None, "corr": None,
    }
    if len(df) >= 3:  
        x = np.arange(len(df))
        su, iu = np.polyfit(x, df["units"], 1)
        sb, ib = np.polyfit(x, df["bill"], 1)
        stats.update(
            trend="increasing" if su > 0 else "decreasing",
            fit_units=(su, iu),
            next_units=max(0.0, su * len(df) + iu),
            next_bill=max(0.0, sb * len(df) + ib),
        )
        if df["units"].std() > 0 and df["bill"].std() > 0:
            stats["corr"] = float(np.corrcoef(df["units"], df["bill"])[0, 1])
    return df, stats


def detect_unusual(df, threshold_pct):
    """Flag months where units rose by at least threshold_pct vs the previous month."""
    df = df.copy()
    df["unusual"] = df["units_change_%"] >= threshold_pct
    return df


def sample_rows():
    months = pd.date_range("2025-01-01", periods=12, freq="MS")
    units = [210, 198, 225, 260, 340, 420, 445, 430, 300, 240, 215, 230]
    rates = np.linspace(6.0, 6.8, 12)
    bills = np.round(np.array(units) * rates + 60)
    return [{"month": m, "units": float(u), "bill": float(b)} for m, u, b in zip(months, units, bills)]

==
class App(tk.Tk):
    TABLE_COLS = ["month", "units", "bill", "cost_per_unit", "units_change_%", "bill_change_%", "status"]

    def __init__(self):
        super().__init__()
        self.title("Electricity Consumption and Bill Analysis")
        self.geometry("980x700")
        self.rows = []          # raw entered data: list of {"month", "units", "bill"}
        self.df = pd.DataFrame()
        self.threshold = tk.StringVar(value="20")

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=6, pady=6)
        self.tab_data, self.tab_analysis, self.tab_graphs = ttk.Frame(nb), ttk.Frame(nb), ttk.Frame(nb)
        nb.add(self.tab_data, text="1. Data Entry")
        nb.add(self.tab_analysis, text="2. Analysis & Alerts")
        nb.add(self.tab_graphs, text="3. Graphs")
        self._build_data_tab()
        self._build_analysis_tab()
        self._build_graph_tab()
        self.refresh()

    def _build_data_tab(self):
        form = ttk.LabelFrame(self.tab_data, text="Enter Electricity Data", padding=8)
        form.pack(fill="x", padx=8, pady=8)
        self.e_month, self.e_units, self.e_bill = (ttk.Entry(form, width=14) for _ in range(3))
        for i, (label, entry) in enumerate([("Month (YYYY-MM)", self.e_month),
                                            ("Units (kWh)", self.e_units),
                                            ("Bill amount", self.e_bill)]):
            ttk.Label(form, text=label).grid(row=0, column=i, padx=6, sticky="w")
            entry.grid(row=1, column=i, padx=6, pady=2)
        ttk.Button(form, text="Add / Update", command=self._add_row).grid(row=1, column=3, padx=8)
        ttk.Button(form, text="Delete Selected", command=self._delete_selected).grid(row=1, column=4)

        tools = ttk.Frame(self.tab_data)
        tools.pack(fill="x", padx=8)
        for text, cmd in [("Load CSV", self._load_csv), ("Save CSV", self._save_csv),
                          ("Load Sample Data", self._load_sample), ("Clear All", self._clear_all)]:
            ttk.Button(tools, text=text, command=cmd).pack(side="left", padx=3, pady=4)
        ttk.Label(tools, text="Unusual increase if units rise by (%) ≥").pack(side="left", padx=(20, 4))
        spin = ttk.Spinbox(tools, from_=1, to=500, width=5, textvariable=self.threshold, command=self.refresh)
        spin.pack(side="left")
        spin.bind("<Return>", lambda e: self.refresh())
        spin.bind("<FocusOut>", lambda e: self.refresh())

        frame = ttk.Frame(self.tab_data)
        frame.pack(fill="both", expand=True, padx=8, pady=6)
        self.tree = ttk.Treeview(frame, columns=self.TABLE_COLS, show="headings")
        for c in self.TABLE_COLS:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=120 if c != "status" else 150, anchor="center")
        self.tree.tag_configure("unusual", background="#ffd9d9")
        sb = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

    def _build_analysis_tab(self):
        self.text = tk.Text(self.tab_analysis, font=("Consolas", 11), wrap="word", state="disabled", padx=10, pady=10)
        self.text.pack(fill="both", expand=True, padx=8, pady=8)
        self.text.tag_configure("h", font=("Consolas", 12, "bold"))
        self.text.tag_configure("warn", foreground=UNUSUAL_COLOR)

    def _build_graph_tab(self):
        self.fig = Figure(figsize=(9, 6), dpi=100)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.tab_graphs)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

    def _add_row(self):
        try:
            month = pd.to_datetime(self.e_month.get().strip()).to_period("M").to_timestamp()
            units, bill = float(self.e_units.get()), float(self.e_bill.get())
            if units <= 0 or bill < 0:
                raise ValueError
        except (ValueError, TypeError):
            messagebox.showerror("Invalid input", "Enter a valid month (e.g. 2025-03), units > 0 and bill ≥ 0.")
            return
        self.rows = [r for r in self.rows if r["month"] != month]
        self.rows.append({"month": month, "units": units, "bill": bill})
        for e in (self.e_month, self.e_units, self.e_bill):
            e.delete(0, "end")
        self.e_month.focus()
        self.refresh()

    def _delete_selected(self):
        sel = self.tree.selection()
        if not sel:
            return
        months = {self.df.loc[int(i), "month"] for i in sel}
        self.rows = [r for r in self.rows if r["month"] not in months]
        self.refresh()

    def _load_csv(self):
        path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])
        if not path:
            return
        try:
            clean = process_data(pd.read_csv(path))
        except Exception as e:
            messagebox.showerror("Could not load file", str(e))
            return
        if clean.empty:
            messagebox.showwarning("No valid rows", "The file had no valid rows.")
            return
        self.rows = clean[COLUMNS].to_dict("records")
        self.refresh()

    def _save_csv(self):
        if self.df.empty:
            messagebox.showinfo("Save", "No data to save.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
        if path:
            out = self.df.drop(columns=["prev_units", "unusual"])
            out["month"] = out["month"].dt.strftime("%Y-%m")
            out.to_csv(path, index=False)

    def _load_sample(self):
        self.rows = sample_rows()
        self.refresh()

    def _clear_all(self):
        self.rows = []
        self.refresh()

    def _get_threshold(self):
        try:
            return float(self.threshold.get())
        except (ValueError, tk.TclError):
            return 20.0

    def refresh(self):
        if not self.rows:
            self.df = pd.DataFrame()
            self._update_table()
            self._set_text([("No data yet. Add rows or load a CSV / sample data.\n", None)])
            self.fig.clear()
            self.canvas.draw()
            return
        clean = process_data(pd.DataFrame(self.rows, columns=COLUMNS))   # step 2
        df, self.stats = analyze(clean)                                   # step 3
        self.df = detect_unusual(df, self._get_threshold())               # step 4
        self._update_table()                                              # step 6
        self._update_summary()
        self._update_graphs()                                             # step 5

    @staticmethod
    def _fmt(v):
        return "-" if pd.isna(v) else v

    def _update_table(self):
        self.tree.delete(*self.tree.get_children())
        for i, r in self.df.iterrows():
            status = "UNUSUAL INCREASE" if r["unusual"] else ("-" if pd.isna(r["units_change_%"]) else "Normal")
            values = [r["month"].strftime("%b %Y"), r["units"], r["bill"], r["cost_per_unit"],
                      self._fmt(r["units_change_%"]), self._fmt(r["bill_change_%"]), status]
            self.tree.insert("", "end", iid=str(i), values=values, tags=("unusual",) if r["unusual"] else ())

    def _set_text(self, parts):
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        for content, tag in parts:
            self.text.insert("end", content, tag)
        self.text.configure(state="disabled")

    def _update_summary(self):
        s, df = self.stats, self.df
        peak, low = s["peak"], s["lowest"]
        parts = [
            ("SUMMARY\n", "h"),
            (f"Months recorded      : {s['months']}\n"
             f"Total units          : {s['total_units']:.1f} kWh\n"
             f"Total bill           : {s['total_bill']:.2f}\n"
             f"Average units/month  : {s['avg_units']:.1f} kWh\n"
             f"Average bill/month   : {s['avg_bill']:.2f}\n"
             f"Average cost per unit: {s['avg_rate']:.2f}\n"
             f"Highest bill         : {peak['month']:%b %Y} ({peak['bill']:.2f})\n"
             f"Lowest bill          : {low['month']:%b %Y} ({low['bill']:.2f})\n\n", None),
            ("UNUSUAL CONSUMPTION ALERTS\n", "h"),
        ]
        flagged = df[df["unusual"]]
        if flagged.empty:
            parts.append((f"No month increased by {self._get_threshold():g}% or more.\n\n", None))
        else:
            for _, r in flagged.iterrows():
                parts.append((f"! {r['month']:%b %Y}: units up {r['units_change_%']:.1f}% "
                              f"({r['prev_units']:.0f} -> {r['units']:.0f} kWh)\n", "warn"))
            parts.append(("\n", None))
        parts.append(("TREND & ESTIMATE\n", "h"))
        if s["trend"] is None:
            parts.append(("Add at least 3 months of data to see trend and next-month estimate.\n", None))
        else:
            nxt = (df["month"].iloc[-1] + pd.DateOffset(months=1)).strftime("%b %Y")
            txt = (f"Overall consumption trend: {s['trend']}\n"
                   f"Estimated {nxt}: {s['next_units']:.0f} kWh, bill about {s['next_bill']:.0f}\n")
            if s["corr"] is not None:
                txt += f"Correlation (units vs bill): {s['corr']:.2f}\n"
            parts.append((txt, None))
        self._set_text(parts)

    def _update_graphs(self):
        df = self.df
        self.fig.clear()
        x = np.arange(len(df))
        labels = df["month"].dt.strftime("%b %y")
        colors = np.where(df["unusual"], UNUSUAL_COLOR, NORMAL_COLOR)

        ax1 = self.fig.add_subplot(211)
        ax1.bar(x, df["units"], color=colors)
        if self.stats["fit_units"] is not None:
            su, iu = self.stats["fit_units"]
            ax1.plot(x, su * x + iu, "k--", linewidth=1, label="Trend")
        ax1.set_title("Monthly Consumption")
        ax1.set_ylabel("Units (kWh)")
        ax1.legend(handles=[Patch(color=NORMAL_COLOR, label="Normal"),
                            Patch(color=UNUSUAL_COLOR, label="Unusual increase")], fontsize=8)

        ax2 = self.fig.add_subplot(212, sharex=ax1)
        ax2.plot(x, df["bill"], marker="o", color="#2e8b57")
        bad = df["unusual"].to_numpy()
        ax2.scatter(x[bad], df["bill"][bad], color=UNUSUAL_COLOR, s=70, zorder=3)
        ax2.set_title("Monthly Bill")
        ax2.set_ylabel("Bill amount")
        ax2.grid(alpha=0.3)

        ax2.set_xticks(x)
        ax2.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
        plt_hide = ax1.get_xticklabels()
        for t in plt_hide:
            t.set_visible(False)
        self.fig.tight_layout()
        self.canvas.draw()


if __name__ == "__main__":
    App().mainloop()
