// Settings → Your data (19a, E7): back up everything to one file, restore
// from one, and the automatic backups (weekly, and before an update).
// A restore asks first, says what's in the file, and backs up what's there now.

import { useEffect, useState } from "react";
import { errorMessage, getApi } from "../bridge/bridge";
import type { BackupInfo, BackupStatus } from "../bridge/types";

function when(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

const plural = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;

function contents(info: Pick<BackupInfo, "jobs" | "resumes" | "cover_notes">): string {
  return [plural(info.jobs, "job"), plural(info.resumes.length, "resume"), plural(info.cover_notes, "cover note")].join(", ");
}

export function BackupCard({ onStatus }: { onStatus?(status: BackupStatus): void }) {
  const [status, setStatus] = useState<BackupStatus | null>(null);
  const [busy, setBusy] = useState<"backup" | "choose" | "restore" | null>(null);
  const [picked, setPicked] = useState<BackupInfo | null>(null);
  const [message, setMessage] = useState<{ path?: string; text: string } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = () =>
    getApi()
      .then((api) => api.backup_status())
      .then((s) => {
        setStatus(s);
        onStatus?.(s);
      })
      .catch(() => undefined);
  useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const run = async <T,>(what: "backup" | "choose" | "restore", call: () => Promise<T>): Promise<T | undefined> => {
    setBusy(what);
    setError(null);
    setMessage(null);
    try {
      return await call();
    } catch (e) {
      setError(errorMessage(e));
      return undefined;
    } finally {
      setBusy(null);
    }
  };

  const backUp = async () => {
    const made = await run("backup", async () => (await getApi()).create_backup());
    if (made) setMessage({ path: made.path, text: `Backed up ${contents(made)}.` });
  };

  const choose = async () => {
    setPicked(null);
    const info = await run("choose", async () => (await getApi()).choose_backup());
    if (info) setPicked(info);
  };

  const restore = async () => {
    const done = await run("restore", async () => (await getApi()).restore_backup());
    setPicked(null);
    if (!done) return;
    setMessage({ text: `Restored ${contents(done)}. JobLens reloads to show them…` });
    // Every screen, the theme and the settings come from the restored data: start the page afresh.
    window.setTimeout(() => window.location.reload(), 2500);
  };

  return (
    <div className="backup">
      <p className="hint">
        One file with your tracker, resumes, cover notes and settings. API keys are left out, so the file is safe to keep on a USB stick
        or a cloud drive; after a restore on a new PC you paste your key once.
      </p>
      <div className="row-actions">
        <button type="button" className="btn btn-primary" onClick={() => void backUp()} disabled={busy !== null}>
          {busy === "backup" ? "Backing up…" : "Back up now…"}
        </button>
        <button type="button" className="btn btn-secondary" onClick={() => void choose()} disabled={busy !== null}>
          {busy === "choose" ? "Choosing…" : "Restore from a backup…"}
        </button>
      </div>

      {picked && (
        <div className="backup-confirm" role="group" aria-labelledby="restore-title">
          <p id="restore-title">
            <strong>Replace your data with {picked.file}?</strong>
          </p>
          <p className="hint">
            It holds {contents(picked)}
            {picked.created && `, made ${when(picked.created)}`}
            {picked.version && ` by JobLens ${picked.version}`}. Your tracker, resumes and cover notes are replaced by these; your API keys
            stay. What you have now is backed up first, so you can go back.
          </p>
          <div className="row-actions">
            <button type="button" className="btn btn-danger" onClick={() => void restore()} disabled={busy !== null}>
              {busy === "restore" ? "Restoring…" : "Replace and restore"}
            </button>
            <button type="button" className="btn btn-ghost" onClick={() => setPicked(null)} disabled={busy !== null}>
              Cancel
            </button>
          </div>
        </div>
      )}

      {message && (
        <p className="check-status ok" role="status">
          <span aria-hidden="true">✓</span> {message.text}{" "}
          {message.path && (
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => void getApi().then((api) => api.show_in_folder(message.path!))}>
              Show in folder
            </button>
          )}
        </p>
      )}
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}

      <h3 className="backup-auto-title">Automatic backups</h3>
      <p className="hint">
        Once a week, and before an update installs. The last {status?.keep ?? 4} are kept
        {status?.last ? `; the newest is from ${when(status.last)} (${status.last_reason}).` : "; none yet."}
      </p>
      <div className="row-actions">
        <button type="button" className="btn btn-ghost" onClick={() => void getApi().then((api) => api.open_backup_folder()).then(refresh)}>
          Open the backups folder
        </button>
      </div>
    </div>
  );
}
