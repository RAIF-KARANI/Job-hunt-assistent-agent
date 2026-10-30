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
