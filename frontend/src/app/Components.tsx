import { FitChip } from "../tracker/FitChip";

// 17b: every shared piece on one page, to check the glass tokens in both
// themes without hunting through the screens. Open it at #/components; it
// is not in the sidebar.

const SWATCHES = [
  ["Blue", "var(--blue)"],
  ["Purple", "var(--purple)"],
  ["Pink", "var(--pink)"],
  ["Orange", "var(--orange)"],
  ["Yellow", "var(--yellow)"],
] as const;

const STATUSES = [
  ["Researched", "var(--st-researched)"],
  ["Cover note ready", "var(--st-cover)"],
  ["Applied", "var(--st-applied)"],
  ["Interviewing", "var(--st-interviewing)"],
  ["Offer", "var(--st-offer)"],
  ["Rejected", "var(--st-rejected)"],
] as const;

const row = { display: "flex", flexWrap: "wrap", gap: "var(--space-3)", alignItems: "center" } as const;
const dot = { width: 10, height: 10, borderRadius: "50%", flex: "none" } as const;

export function Components() {
  return (
    <div className="page">
      <header className="page-head">
        <h1>Components</h1>
        <p>The shared pieces of the version 3 look. Switch the theme in the sidebar to check both.</p>
      </header>

      <section className="card" aria-labelledby="c-type">
        <h2 id="c-type">Type</h2>
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)", marginTop: "var(--space-3)" }}>
          <span style={{ fontSize: "var(--text-2xl)", fontWeight: 700, letterSpacing: "-0.025em" }}>Page title, 30</span>
          <span style={{ fontSize: "var(--text-xl)", fontWeight: 650 }}>Section heading, 20</span>
          <span style={{ fontSize: "var(--text-lg)", fontWeight: 600 }}>Card title, 16</span>
          <span>Body text, 14. The agent reads the posting and compares your resumes.</span>
          <span style={{ color: "var(--text-muted)" }}>Muted text, for descriptions.</span>
          <span style={{ color: "var(--text-faint)", fontSize: "var(--text-sm)" }}>Faint text, 13, for dates and hints.</span>
          <span style={{ fontFamily: "var(--font-mono)", fontSize: "var(--text-sm)" }}>[2/5] Comparing your resumes with the job...</span>
        </div>
      </section>

      <section className="card" aria-labelledby="c-buttons">
        <h2 id="c-buttons">Buttons</h2>
        <div style={{ ...row, marginTop: "var(--space-3)" }}>
          <button type="button" className="btn btn-primary">New analysis</button>
          <button type="button" className="btn btn-secondary">Open details</button>
          <button type="button" className="btn btn-ghost">Interview prep</button>
          <button type="button" className="btn btn-danger">Remove job</button>
          <button type="button" className="btn btn-danger-text">Reject</button>
          <button type="button" className="btn btn-primary" disabled>Approve and save</button>
          <button type="button" className="btn btn-secondary" disabled>Rewrite</button>
        </div>
      </section>

      <section className="card" aria-labelledby="c-fields">
        <h2 id="c-fields">Fields</h2>
        <div style={{ ...row, alignItems: "flex-end", marginTop: "var(--space-3)" }}>
          <div className="field" style={{ flex: "1 1 280px" }}>
            <label htmlFor="c-link">Job posting link</label>
            <input id="c-link" className="input" type="url" placeholder="https://..." />
            <span className="hint">Paste the link to the posting.</span>
          </div>
          <div className="field" style={{ flex: "1 1 200px" }}>
            <label htmlFor="c-status">Status</label>
            <select id="c-status" className="input" defaultValue="Applied">
              <option>Cover note ready</option>
              <option>Applied</option>
              <option>Interviewing</option>
            </select>
          </div>
          <label className="check">
            <input type="checkbox" defaultChecked /> Ask me which resumes to compare
          </label>
        </div>
        <div className="field" style={{ marginTop: "var(--space-4)" }}>
          <label htmlFor="c-notes">Notes</label>
          <textarea id="c-notes" className="input" rows={3} defaultValue="Spoke to the recruiter on Monday." />
        </div>
        <div style={{ ...row, marginTop: "var(--space-4)" }}>
          <div className="segmented" role="radiogroup" aria-label="View">
            <label className="segment">
              <input type="radio" name="c-view" defaultChecked />
              <span>Board</span>
            </label>
            <label className="segment">
              <input type="radio" name="c-view" />
              <span>List</span>
            </label>
          </div>
          <span className="badge">5 jobs</span>
          <FitChip score={89} />
          <FitChip score={63} />
          <FitChip score={40} />
          <FitChip score={100} large />
        </div>
      </section>

      <section className="card" aria-labelledby="c-notices">
        <h2 id="c-notices">Notices</h2>
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)", marginTop: "var(--space-3)" }}>
          <div className="notice notice-warn">1 application has had no news for a while. A short follow-up email can help.</div>
          <div className="notice notice-danger">The model isn't installed. Choose an installed model in Settings.</div>
          <span className="ok-ink">Saved.</span>
          <span className="danger-ink">Couldn't reach the model.</span>
        </div>
      </section>

      <section aria-label="Tiles" className="tiles">
        <div className="tile">
          <span className="tile-label">Jobs tracked</span>
          <span className="tile-value">33</span>
        </div>
        <div className="tile">
          <span className="tile-label">Median full run</span>
          <span className="tile-value">4m 26s</span>
        </div>
        <div className="tile">
          <span className="tile-label">Evidence verified</span>
          <span className="tile-value">63%</span>
        </div>
      </section>

      <section className="card" aria-labelledby="c-colors">
        <h2 id="c-colors">Colours</h2>
        <div style={{ ...row, marginTop: "var(--space-3)" }}>
          {SWATCHES.map(([name, color]) => (
            <span key={name} style={row}>
              <span style={{ width: 28, height: 28, borderRadius: 9, background: color }} />
              {name}
            </span>
          ))}
          <span style={{ width: 120, height: 28, borderRadius: 9, background: "var(--accent-grad)" }} title="Main action gradient" />
        </div>
        <div style={{ ...row, marginTop: "var(--space-4)", color: "var(--text-muted)", fontSize: "var(--text-sm)" }}>
          {STATUSES.map(([name, color]) => (
            <span key={name} style={{ ...row, gap: "var(--space-2)" }}>
              <span style={{ ...dot, background: color }} />
              {name}
            </span>
          ))}
        </div>
      </section>

      <section className="card placeholder" aria-labelledby="c-empty">
        <h2 id="c-empty">Empty state</h2>
        <p>No jobs here yet. Analyze a posting and it shows up.</p>
      </section>
    </div>
  );
}
