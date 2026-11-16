import { Icon } from "./Icon";

interface Props {
  /** The theme on screen now (never "system"). */
  theme: "dark" | "light";
  onToggleTheme(): void;
  onSearch(): void;
  /** Hidden on the Analyze page, which is where it leads. */
  showNew: boolean;
}

// 17c: the same three things on every screen, top right: search and quick
// actions (Ctrl K), the light/dark switch, and the main action.
export function TopBar({ theme, onToggleTheme, onSearch, showNew }: Props) {
  const toLight = theme === "dark";
  return (
    <div className="topbar">
      <button type="button" className="kbtn" onClick={onSearch} aria-label="Search and quick actions" aria-keyshortcuts="Control+K">
        <Icon name="search" size={16} />
        Search
        <kbd className="kbd">Ctrl K</kbd>
      </button>
      <button
        type="button"
        className="btn btn-secondary icon-only"
        onClick={onToggleTheme}
        aria-label={toLight ? "Switch to light mode" : "Switch to dark mode"}
        title={toLight ? "Light mode" : "Dark mode"}
      >
        <Icon name={toLight ? "sun" : "moon"} />
      </button>
      {showNew && (
        // The label changes on hover or focus; "New analysis" stays its name
        // for screen readers.
        <a className="btn btn-primary cta" href="#/analyze" aria-label="New analysis">
          <span className="cta-ico" aria-hidden="true">
            <Icon name="plus" size={16} />
            <Icon name="lens" size={16} />
          </span>
          <span className="cta-lbl" aria-hidden="true">
            <span>New analysis</span>
            <span>Land the next one</span>
          </span>
        </a>
      )}
    </div>
  );
}
