"""
Dashboard tab: how JobLens is performing, for every user (Phases 9e + 11).

Data comes from job_agent/monitoring.py; this file only DRAWS.

Phase 11 switched the run charts from Langfuse (needs a Docker server) to
JobLens' OWN run log in the local database (job_agent/runlog.py), so the
Dashboard works on any PC. Three groups:
    Jobs          fit score per job, where your applications are (tracker)
    Runs          seconds per step, LLM time vs output tokens (run log)
    Quality       safety nets that fired per run + your feedback (11b, 11c)

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
    QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from desktop.threads import run_in_background  # noqa: E402
from job_agent import monitoring as m  # noqa: E402

BLUE = "#2a78d6"  # categorical slot 1 (validated in Phase 8e)


DAYS = 30


def load_run_log() -> dict:
    """Runs on a background thread: everything from JobLens' own run log."""
    quality, pass_rate = m.local_quality(DAYS)
    return {
        "runs": m.local_runs(DAYS),
        "calls": m.local_llm_calls(DAYS),
        "nodes": m.local_node_latency(DAYS),
        "decisions": m.local_decisions(DAYS),
        "quality": quality,
        "pass_rate": pass_rate,
        "feedback": m.local_feedback(),
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

    def hbar(self, labels, values, title, unit="", xmax=None, whole=False, fmt="{:.0f}"):
        ax, c = self._axes(title)
        ys = range(len(labels))
        ax.barh(ys, values, height=0.55, color=BLUE)
        ax.set_yticks(list(ys), labels, color=c["ink"], fontsize=8)
        # Reserve at least 4 rows so one or two bars don't fill the whole
        # chart; then put the first item on top.
        ax.set_ylim(max(len(labels), 4) - 0.5, -0.5)
        top = xmax or (max(values) * 1.15 if len(values) and max(values) else 1)
        ax.set_xlim(0, top)
        if whole:
            ax.xaxis.get_major_locator().set_params(integer=True)
        for y, v in zip(ys, values):
            ax.text(v + top * 0.01, y, fmt.format(v) + unit, va="center", fontsize=8, color=c["ink"])
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

        # Three rows of charts don't fit a laptop screen: put them in a
        # scroll area (the KPI tiles above stay visible).
        charts = QWidget()
        grid = QGridLayout(charts)
        self.fit_chart, self.status_chart = Chart(), Chart()
        self.steps_chart, self.latency_chart = Chart(), Chart()
        self.quality_chart, self.feedback_chart = Chart(), Chart()
        for row, pair in enumerate([(self.fit_chart, self.status_chart),
                                    (self.steps_chart, self.latency_chart),
                                    (self.quality_chart, self.feedback_chart)]):
            for col, chart in enumerate(pair):
                chart.setMinimumHeight(260)
                grid.addWidget(chart, row, col)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(charts)
        layout.addWidget(scroll, 1)
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
        self.source.setText("Loading the run log...")
        run_in_background(load_run_log, on_done=self.draw_runs,
                          on_error=lambda msg: self.draw_runs(None, error=msg))

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

    # ---- run log (local database, background thread) --------------------------

    def draw_runs(self, data, error: str | None = None):
        self.refresh_button.setEnabled(True)
        if not data:
            self.source.setText(f"Couldn't read the run log: {error}")
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
        self.source.setText(f"From JobLens' run log on this PC, last {DAYS} days. "
                            "Nothing is sent anywhere.")

        empty = "Analyze a job to see this."
        if nodes.empty:
            self.steps_chart.message("Seconds per pipeline step", empty)
        else:
            self.steps_chart.hbar(list(nodes["node"]), list(nodes["avg_seconds"]),
                                  "Seconds per pipeline step (average)", unit=" s")
        calls = calls[calls["output_tokens"] > 0] if not calls.empty else calls
        if calls.empty:
            self.latency_chart.message("LLM call time vs output tokens", empty)
        else:
            title = "LLM call time vs output tokens"
            if len(calls) >= 3:
                r = calls["output_tokens"].corr(calls["latency"])
                title += f" (correlation {r:.2f})"
            self.latency_chart.scatter(calls["output_tokens"], calls["latency"], title,
                                       "output tokens", "seconds")
        self.draw_quality(data["quality"], data["pass_rate"])
        self.draw_feedback(data["feedback"])

    # ---- 11b + 11c --------------------------------------------------------------

    def draw_quality(self, quality, pass_rate):
        title = "Safety-net catches per run"
        if pass_rate is not None:  # second line: a long title gets cut off in half a window
            title += f"\nevidence verified {pass_rate:.0%} of claims"
        if quality.empty:
            self.quality_chart.message(title, "Analyze a job to see which checks fire.")
        else:
            self.quality_chart.hbar(list(quality["check"]), list(quality["per_run"]), title,
                                    fmt="{:.1f}")

    def draw_feedback(self, feedback):
        title = "Your ratings"
        if feedback.empty or feedback["count"].sum() == 0:
            self.feedback_chart.message(title, "Rate a run after analyzing a job\n"
                                               "(the Analyze tab asks when a run ends).")
        else:
            self.feedback_chart.hbar(list(feedback["label"]), list(feedback["count"]), title,
                                     whole=True)
