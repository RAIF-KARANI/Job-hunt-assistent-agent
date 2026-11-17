import { useState, type ReactNode } from "react";
import { Icon } from "./Icon";

// An accordion (feature F5). The closed row always shows a one-line summary,
// so the main fact is visible without a click. Built on <details>: it opens
// with Enter or Space and is announced as expanded or collapsed.

interface Props {
  title: string;
  /** The one line shown next to the title, open or closed. */
  digest?: ReactNode;
  defaultOpen?: boolean;
  /** No frame of its own: for a list of folds inside a panel or a sheet. */
  flat?: boolean;
  /** Heading level of the title: 2 on a page, 3 inside a panel. */
  level?: 2 | 3;
  children: ReactNode;
}

export function Fold({ title, digest, defaultOpen = false, flat = false, level = 3, children }: Props) {
  const [open, setOpen] = useState(defaultOpen);
  const Heading = level === 2 ? "h2" : "h3";
  return (
    <details className={flat ? "acc flat" : "acc"} open={open} onToggle={(e) => setOpen(e.currentTarget.open)}>
      <summary>
        <Heading>{title}</Heading>
        {digest && <span className="acc-digest">{digest}</span>}
        <Icon name="chevron" size={16} />
      </summary>
      <div className="acc-body">{children}</div>
    </details>
  );
}
