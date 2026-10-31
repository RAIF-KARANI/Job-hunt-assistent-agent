// Which resumes this run compares (14b, D28). The default set comes from
// Settings → Resumes; "Ask me for each job" opens the chips every time,
// otherwise one quiet line with a "change" link.

import { useEffect, useState } from "react";
import { getApi } from "../bridge/bridge";

const label = (file: string) => file.replace(/\.pdf$/i, "");

/** The default set, resolved against the resumes that exist ("" = all). */
export function defaultsFor(files: string[], saved: string | undefined): string[] {
  const wanted = (saved ?? "").split("|").filter(Boolean);
  const existing = files.filter((f) => wanted.includes(f));
  return existing.length ? existing : files;
}

interface Props {
  value: string[] | null; // null until the resumes are loaded
  onChange(files: string[]): void;
  disabled: boolean;
}

export function ResumeChoice({ value, onChange, disabled }: Props) {
  const [files, setFiles] = useState<string[]>([]);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    Promise.all([getApi().then((api) => api.list_resumes()), getApi().then((api) => api.get_settings())])
      .then(([resumes, settings]) => {
        const names = resumes.map((r) => r.name);
        setFiles(names);
        onChange(defaultsFor(names, settings.RESUMES_DEFAULT as string | undefined));
        setOpen(settings.RESUMES_ASK === "true");
      })
      .catch(() => undefined);
    // Once per Analyze screen: the defaults are a starting point you can change.
  }, []);

  if (files.length < 2 || value === null) return null; // nothing to choose

  const toggle = (file: string) => {
    if (value.includes(file)) {
      if (value.length > 1) onChange(value.filter((f) => f !== file)); // keep at least one
    } else {
      onChange(files.filter((f) => f === file || value.includes(f)));
    }
  };

  if (!open) {
    return (
      <p className="resume-choice-line hint">
        Comparing with {value.length === files.length ? `all ${files.length} resumes` : `${value.length} of ${files.length} resumes`}
        {" · "}
        <button type="button" className="link-button" onClick={() => setOpen(true)} disabled={disabled}>
          change
        </button>
      </p>
    );
  }
  return (
    <fieldset className="resume-choice" disabled={disabled}>
      <legend>Resumes to compare with this job</legend>
      <div className="resume-chips">
        {files.map((file) => (
          <button
            key={file}
            type="button"
            className="chip-toggle"
            aria-pressed={value.includes(file)}
            onClick={() => toggle(file)}
            title={value.includes(file) && value.length === 1 ? "At least one resume is needed" : undefined}
          >
            {label(file)}
          </button>
        ))}
      </div>
      <span className="hint">
        Fewer resumes = a faster step 2 (about one AI call each). Your default set is in Settings → Resumes.
      </span>
    </fieldset>
  );
}
