// Inline stroke icons (currentColor), so they follow the text color in both themes.

const paths = {
  dashboard: (
    <>
      <rect x="2" y="2" width="6" height="6" rx="1.5" />
      <rect x="10" y="2" width="6" height="6" rx="1.5" />
      <rect x="2" y="10" width="6" height="6" rx="1.5" />
      <rect x="10" y="10" width="6" height="6" rx="1.5" />
    </>
  ),
  analyze: <path d="M5 3.5l9 5.5-9 5.5z" strokeLinejoin="round" />,
  tracker: (
    <>
      <rect x="2" y="3" width="4" height="12" rx="1.2" />
      <rect x="7" y="3" width="4" height="8" rx="1.2" />
      <rect x="12" y="3" width="4" height="10" rx="1.2" />
    </>
  ),
  evals: (
    <>
      <path d="M2.5 15.5h13" strokeLinecap="round" />
      <path d="M3.5 12l3.5-4 3 2.5 4.5-6" strokeLinecap="round" strokeLinejoin="round" />
    </>
  ),
  settings: (
    <>
      <circle cx="9" cy="9" r="2.6" />
      <path
        d="M9 1.8v2.2M9 14v2.2M1.8 9h2.2M14 9h2.2M3.9 3.9l1.6 1.6M12.5 12.5l1.6 1.6M3.9 14.1l1.6-1.6M12.5 5.5l1.6-1.6"
        strokeLinecap="round"
      />
    </>
  ),
  sun: (
    <>
      <circle cx="9" cy="9" r="3.2" />
      <path d="M9 1.5v1.8M9 14.7v1.8M1.5 9h1.8M14.7 9h1.8M3.7 3.7l1.3 1.3M13 13l1.3 1.3M3.7 14.3L5 13M13 5l1.3-1.3" strokeLinecap="round" />
    </>
  ),
  moon: <path d="M14.5 11.2A6.2 6.2 0 016.8 3.5a6.2 6.2 0 107.7 7.7z" strokeLinejoin="round" />,
  monitor: (
    <>
      <rect x="2" y="3" width="14" height="9.5" rx="1.5" />
      <path d="M6.5 15.5h5M9 12.5v3" strokeLinecap="round" />
    </>
  ),
  search: (
    <>
      <circle cx="8" cy="8" r="5" />
      <path d="M15.5 15.5l-3.8-3.8" strokeLinecap="round" />
    </>
  ),
  // the main button: a plus that turns into a lens with a glint (17c)
  plus: <path d="M9 3.5v11M3.5 9h11" strokeLinecap="round" />,
  lens: (
    <>
      <circle cx="8" cy="8" r="4.6" />
      <path d="M14.8 14.8l-3.5-3.5" strokeLinecap="round" />
      <path className="glint" d="M6 8a2 2 0 012-2" strokeLinecap="round" />
    </>
  ),
  chevron: <path d="M4.5 6.75L9 11.25l4.5-4.5" strokeLinecap="round" strokeLinejoin="round" />,
  up: <path d="M9 14V4M4.5 8.5L9 4l4.5 4.5" strokeLinecap="round" strokeLinejoin="round" />,
  down: <path d="M9 4v10M4.5 9.5L9 14l4.5-4.5" strokeLinecap="round" strokeLinejoin="round" />,
  arrow: <path d="M3.5 9h11M10 4.5L14.5 9 10 13.5" strokeLinecap="round" strokeLinejoin="round" />,
  bolt: <path d="M10 2L4 10.2h4.4L8 16l6-8.2H9.6z" strokeLinejoin="round" />,
  "chevron-right": <path d="M6.75 4.5L11.25 9l-4.5 4.5" strokeLinecap="round" strokeLinejoin="round" />,
  check: <path d="M3.75 9.5l3.4 3.4 7.1-7.4" strokeLinecap="round" strokeLinejoin="round" />,
  minus: <path d="M4.5 9h9" strokeLinecap="round" />,
  briefcase: (
    <>
      <rect x="2.5" y="5.5" width="13" height="9.5" rx="2" />
      <path d="M6.75 5.5V4.4A1.4 1.4 0 018.15 3h1.7a1.4 1.4 0 011.4 1.4v1.1" />
    </>
  ),
  message: <path d="M3 5a2 2 0 012-2h8a2 2 0 012 2v5.5a2 2 0 01-2 2H7L3 15.5z" strokeLinejoin="round" />,
  question: (
    <>
      <circle cx="9" cy="9" r="6.5" />
      <path d="M7.2 7a1.9 1.9 0 112.6 1.75c-.5.2-.8.6-.8 1.1v.35M9 12.6h.01" strokeLinecap="round" />
    </>
  ),
  clock: (
    <>
      <circle cx="9" cy="9" r="6.5" />
      <path d="M9 5.5V9l2.3 1.5" strokeLinecap="round" />
    </>
  ),
  shield: (
    <>
      <path d="M9 2.5l5.3 2v4.1c0 3.3-2.3 5.7-5.3 6.8-3-1.1-5.3-3.5-5.3-6.8V4.5z" strokeLinejoin="round" />
      <path d="M6.75 9l1.5 1.5 3-3" strokeLinecap="round" strokeLinejoin="round" />
    </>
  ),
  note: (
    <>
      <path d="M10.5 2.5H5.4A1.9 1.9 0 003.5 4.4v9.2a1.9 1.9 0 001.9 1.9h7.2a1.9 1.9 0 001.9-1.9V6.5z" strokeLinejoin="round" />
      <path d="M6.75 10.5l1.5 1.5 3-3" strokeLinecap="round" strokeLinejoin="round" />
    </>
  ),
} as const;

export type IconName = keyof typeof paths;

export function Icon({ name, size = 18 }: { name: IconName; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true">
      {paths[name]}
    </svg>
  );
}

export function Logo() {
  return (
    <svg width="28" height="28" viewBox="0 0 28 28" fill="none" aria-hidden="true">
      <circle cx="12" cy="12" r="8" stroke="var(--accent)" strokeWidth="2.4" />
      <path d="M18 18l6 6" stroke="var(--accent)" strokeWidth="2.4" strokeLinecap="round" />
      <circle cx="12" cy="12" r="2.6" fill="var(--accent)" />
    </svg>
  );
}
