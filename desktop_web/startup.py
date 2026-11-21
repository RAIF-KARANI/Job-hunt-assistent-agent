"""The work JobLens does when it starts and when it quits, whichever window
shows it (18d1). Today's pywebview window (app.py) and the Rust window's
engine (engine.py) both call these, so the two always do the same things.

Nothing here imports a window library.
"""

import os
import sys
import threading
import time

from job_agent import paths


def prepare() -> None:
    """Before the page shows anything: mark runs that were cut off when the
    app last closed (12j), and re-score saved jobs computed with an older
    formula (v1.1.0: in code, no AI, well under a second)."""
    from job_agent import runlog

    try:
        runlog.mark_interrupted()
    except Exception as e:  # the run log must never stop the app from opening
        print(f"! run log: {e}")
    try:
        from job_agent.tracker import rescore_all

        changed = rescore_all()
        if changed:
            print(f"  re-scored {len(changed)} saved job(s) with the new formula")
    except Exception as e:  # never stop the app from opening
        print(f"! re-scoring saved jobs: {e}")


def after_update(api) -> None:
    """1.1.1: read the installer's log (did the last update work?), then
    remove the last update's installer, which is no longer needed."""
    from desktop_web import updates
    from job_agent import __version__

    api._install_problem = updates.review_last_install(paths.APP_HOME / "updates", __version__, paths.APP_HOME)
    updates.clean_downloads(paths.APP_HOME / "updates")


def background_chores() -> None:
    """Slow, once-a-start jobs that never hold up the window."""
    threading.Thread(target=keep_old_descriptions, name="joblens-descriptions", daemon=True).start()
    threading.Thread(target=weekly_backup, name="joblens-backup", daemon=True).start()
    if paths.IS_INSTALLED:  # a run from source never touches the installed app's leftovers
        threading.Thread(target=clean_temp, name="joblens-clean-temp", daemon=True).start()


def check_for_updates_soon(api, delay: float = 5) -> None:
    """13b: once per start, a few seconds after the page loaded, on a
    background thread (startup never waits for GitHub)."""

    def later():
        time.sleep(delay)
        try:
            api._startup_update_check()
        except Exception as e:  # an update check must never break the app
            print(f"! update check: {e}")

    threading.Thread(target=later, name="joblens-updates", daemon=True).start()


def weekly_backup(delay: float = 60) -> None:
    """19a: once a week, a backup of your data into APP_HOME/backups (the
    last 4 are kept). A minute after start, so it never slows the window."""
    time.sleep(delay)
    try:
        from job_agent import backup

        made = backup.auto_backup_if_due()
        if made:
            print(f"  backup: {made.name}")
    except Exception as e:  # a failed backup must never break the app
        print(f"! weekly backup: {e}")


def keep_old_descriptions() -> None:
    """16e: a single try to fetch the job description of every job saved
    before JobLens kept them. Slow on purpose (a pause between pages), in
    the background, and never again after it ran once."""
    from job_agent import posting_archive

    time.sleep(30)  # startup, the page and the update check go first
    try:
        counts = posting_archive.backfill()
        if counts:
            print("  job descriptions of older jobs: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))
    except Exception as e:  # never worth a crash
        print(f"! keeping old job descriptions: {e}")


def clean_temp() -> None:
    from desktop_web import housekeeping

    try:
        removed, freed = housekeeping.clean_webview_temp()
        if removed:
            print(f"  removed {removed} old browser profile(s) from %TEMP% ({freed / 1e6:.0f} MB)")
    except Exception as e:  # housekeeping must never stop the app
        print(f"! cleaning %TEMP%: {e}")


def free_the_gpu(api, grace: float = 5.0, tidy: bool = False) -> None:
    """15g, on Quit: end a running step (closing its connection makes Ollama
    stop at once), then free the model's graphics memory. On 1 Nov a quit
    JobLens lived on without a window for ~8 minutes, waiting for an AI call,
    with the GPU at 90 %. If the step still hasn't ended after `grace`
    seconds, the process exits anyway.
    tidy (15h): also drop the saved state of runs that can't be continued."""
    from job_agent.llm import unload_model

    runner = getattr(api, "_runner", None)
    done = runner.shut_down(grace) if runner else True
    if tidy:
        try:
            from desktop_web import housekeeping

            keep = {runner.run_id} if runner and getattr(runner, "run_id", None) else set()
            result = housekeeping.prune_checkpoints(keep=keep)
            if result["runs_removed"]:
                print(f"  checkpoints: removed {result['runs_removed']} old run(s), "
                      f"{result['bytes_before'] / 1e6:.1f} -> {result['bytes_after'] / 1e6:.1f} MB")
        except Exception as e:  # never block quitting
            print(f"! tidying checkpoints: {e}")
    unload_model()
    if not done:
        print("! the agent didn't stop in time: exiting anyway")
        sys.stdout.flush()
        os._exit(0)  # a thread blocked in a call must not keep JobLens alive
