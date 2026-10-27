"""
Dashboard tab: the monitoring dashboard (Phase 8e) as a native tab.

Data comes from job_agent/monitoring.py - the same tested data layer the
Streamlit dashboard uses. This file only DRAWS, which is exactly why that
layer was kept free of UI code.

Two speeds of data:
    tracker (local SQLite)  -> instant, drawn immediately
    Langfuse (network)      -> loaded in a background thread; if Langfuse
                               isn't running, those panels say so and the
                               rest of the tab still works.

Charts are matplotlib figures embedded in Qt (FigureCanvasQTAgg), styled
like the web dashboard: one color per series, values at bar ends, light
gridlines, and colors that follow the app's light/dark palette.
"""

import matplotlib

matplotlib.use("QtAgg")  # draw into Qt widgets, not a separate window

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402
from PySide6.QtGui import QPalette  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

from desktop.threads import run_in_background  # noqa: E402
from job_agent import monitoring as m  # noqa: E402

BLUE = "#2a78d6"  # categorical slot 1 (validated in Phase 8e)


def load_traces() -> dict | None:
    """Runs on a background thread: everything that needs Langfuse."""
    if not m.langfuse_available():
        return None
    obs = m.fetch_observations(30)
    return {
        "runs": m.build_runs(obs),
        "calls": m.build_llm_calls(obs),
        "nodes": m.build_node_latency(obs),
        "decisions": m.build_decisions(m.fetch_scores()),
    }


class KpiTile(QFrame):
    def __init__(self, label: str):
        super().__init__()
        self.setObjectName("tile")
        v = QVBoxLayout(self)
        caption = QLabel(label)
        caption.setObjectName("hint")
        self.value = QLabel("–")
        self.value.setObjectName("kpi")
        v.addWidget(caption)
        v.addWidget(self.value)


class Chart(FigureCanvasQTAgg):
    """One matplotlib figure inside a Qt widget."""

    def __init__(self):
        self.figure = Figure(figsize=(5, 2.6), layout="constrained")
        super().__init__(self.figure)

    def _colors(self):
        # Follow the Qt palette, so charts match the app in light AND dark mode.
        pal = self.palette()
        return {"bg": pal.color(QPalette.ColorRole.Base).name(),
                "ink": pal.color(QPalette.ColorRole.Text).name(),
                "muted": pal.color(QPalette.ColorRole.PlaceholderText).name()}

    def _axes(self, title: str):
        c = self._colors()
        self.figure.clear()
        self.figure.set_facecolor(c["bg"])
        ax = self.figure.add_subplot()
        ax.set_facecolor(c["bg"])
        ax.set_title(title, loc="left", fontsize=10, fontweight="bold", color=c["ink"])
        for side in ("top", "right", "left"):
            ax.spines[side].set_visible(False)
        ax.spines["bottom"].set_color(c["muted"])
        ax.tick_params(colors=c["muted"], labelsize=8, length=0)
        ax.grid(axis="x", color=c["muted"], alpha=0.25, linewidth=0.6)
        ax.set_axisbelow(True)
        return ax, c

    def hbar(self, labels, values, title, unit="", xmax=None, whole=False):
        ax, c = self._axes(title)
        ys = range(len(labels))
        ax.barh(ys, values, height=0.55, color=BLUE)
        ax.set_yticks(list(ys), labels, color=c["ink"], fontsize=8)
        ax.invert_yaxis()  # first item on top
        top = xmax or (max(values) * 1.15 if len(values) and max(values) else 1)
        ax.set_xlim(0, top)
        if whole:
            ax.xaxis.get_major_locator().set_params(integer=True)
        for y, v in zip(ys, values):
            ax.text(v + top * 0.01, y, f"{v:.0f}{unit}", va="center", fontsize=8, color=c["ink"])
        self.draw()

    def scatter(self, x, y, title, xlabel, ylabel):
        ax, c = self._axes(title)
        ax.scatter(x, y, s=28, color=BLUE, alpha=0.85, linewidths=0)
        ax.grid(axis="y", color=c["muted"], alpha=0.25, linewidth=0.6)
        ax.set_xlabel(xlabel, color=c["muted"], fontsize=8)
        ax.set_ylabel(ylabel, color=c["muted"], fontsize=8)
        ax.set_ylim(bottom=0)
        self.draw()

    def message(self, title: str, text: str):
        ax, c = self._axes(title)
        ax.axis("off")
        ax.text(0.5, 0.45, text, ha="center", va="center", fontsize=9, color=c["muted"],
                wrap=True, transform=ax.transAxes)
        self.draw()


class DashboardTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        top = QHBoxLayout()
        self.tiles = {key: KpiTile(label) for key, label in [
            ("runs", "Runs (30 days)"), ("llm_calls", "LLM calls"), ("tokens", "Tokens"),
            ("median", "Median full run"), ("approval", "Approval rate")]}
        for tile in self.tiles.values():
            top.addWidget(tile, 1)
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh)
        top.addWidget(self.refresh_button)
        layout.addLayout(top)

        self.source = QLabel()
        self.source.setObjectName("hint")
        self.source.setWordWrap(True)
        layout.addWidget(self.source)

        grid = QGridLayout()
        self.fit_chart, self.status_chart = Chart(), Chart()
        self.steps_chart, self.latency_chart = Chart(), Chart()
        grid.addWidget(self.fit_chart, 0, 0)
        grid.addWidget(self.status_chart, 0, 1)
        grid.addWidget(self.steps_chart, 1, 0)
        grid.addWidget(self.latency_chart, 1, 1)
        layout.addLayout(grid, 1)
        self._loaded = False

    def showEvent(self, event):
        # Load lazily: only when the tab is first opened, not at app start.
        super().showEvent(event)
        if not self._loaded:
            self._loaded = True
            self.refresh()

    def refresh(self):
        self.draw_tracker()
        self.refresh_button.setEnabled(False)
        self.source.setText("Loading traces from Langfuse...")
        run_in_background(load_traces, on_done=self.draw_traces,
                          on_error=lambda msg: self.draw_traces(None, error=msg))

    # ---- tracker (local, instant) ---------------------------------------------

    def draw_tracker(self):
        jobs = m.fetch_jobs()
        if jobs.empty:
            self.fit_chart.message("Fit score per job", "No tracked jobs yet.")
        else:
            top = jobs.sort_values("fit_score", ascending=False).head(10)  # chart only
            labels = [f"#{r.id} {r.company[:16]}" for r in top.itertuples()]
            title = "Fit score per job" + (" (top 10)" if len(jobs) > 10 else "")
            self.fit_chart.hbar(labels, list(top["fit_score"]), title, xmax=105)
        funnel = m.build_status_funnel(jobs)  # ALL jobs, not just the top 10
        self.status_chart.hbar(list(funnel["status"]), list(funnel["jobs"]),
                               "Where your applications are", whole=True)

    # ---- traces (network, background) -----------------------------------------

    def draw_traces(self, data, error: str | None = None):
        self.refresh_button.setEnabled(True)
        if not data:
            reason = error or "Langfuse isn't running"
            self.source.setText(f"Trace charts need Langfuse ({reason}). Start it with "
                                "`docker compose up -d` in infra\\langfuse and set "
                                "Tracing = langfuse in Settings. Tracker charts work without it.")
            for key in self.tiles:
                self.tiles[key].value.setText("–")
            for chart, title in [(self.steps_chart, "Seconds per pipeline step"),
                                 (self.latency_chart, "LLM call time vs output tokens")]:
                chart.message(title, "Needs Langfuse")
            return

        runs, calls, nodes = data["runs"], data["calls"], data["nodes"]
        kpi = m.build_kpis(runs, calls, data["decisions"])
        self.tiles["runs"].value.setText(str(kpi["runs"]))
        self.tiles["llm_calls"].value.setText(str(kpi["llm_calls"]))
        self.tiles["tokens"].value.setText(f"{kpi['tokens_in'] + kpi['tokens_out']:,}")
        self.tiles["median"].value.setText(
            f"{kpi['median_full_run']:.0f} s" if kpi["median_full_run"] is not None else "–")
        self.tiles["approval"].value.setText(
            f"{kpi['approval_rate']:.0%}" if kpi["approval_rate"] is not None else "–")
        self.source.setText(f"Traces from Langfuse ({m.langfuse_url()}), last 30 days.")

        if nodes.empty:
            self.steps_chart.message("Seconds per pipeline step", "No runs traced yet.")
        else:
            self.steps_chart.hbar(list(nodes["node"]), list(nodes["avg_seconds"]),
                                  "Seconds per pipeline step (average)", unit=" s")
        if calls.empty:
            self.latency_chart.message("LLM call time vs output tokens", "No LLM calls traced yet.")
        else:
            title = "LLM call time vs output tokens"
            if len(calls) >= 3:
                r = calls["output_tokens"].corr(calls["latency"])
                title += f" (correlation {r:.2f})"
            self.latency_chart.scatter(calls["output_tokens"], calls["latency"], title,
                                       "output tokens", "seconds")
