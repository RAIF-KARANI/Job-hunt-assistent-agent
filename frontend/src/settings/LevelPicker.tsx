// The 3D level (D14) as three choices, with the one that suits this PC
// marked. The page also checks that WebGL works at all: Python can't know.

import type { Ui3D } from "../bridge/types";

export const LEVELS: { id: Ui3D; title: string; text: string }[] = [
  { id: "animated", title: "Animated", text: "3D galaxy that turns slowly. Pauses while the agent works." },
  { id: "still", title: "Still", text: "3D galaxy that moves only when you drag it. Almost no GPU use." },
  { id: "off", title: "Off", text: "Flat map with the same information. No 3D at all." },
];

let webgl: boolean | null = null;

/** Can this browser make a WebGL context? Checked once, then remembered. */
export function webglWorks(): boolean {
  if (webgl === null) {
    try {
      const canvas = document.createElement("canvas");
      const gl = canvas.getContext("webgl2") ?? canvas.getContext("webgl");
      webgl = Boolean(gl);
      (gl as WebGLRenderingContext | null)?.getExtension("WEBGL_lose_context")?.loseContext(); // give it back now
    } catch {
      webgl = false;
    }
  }
  return webgl;
}

/** The PC check's advice, overruled when WebGL doesn't work. */
export function advise(recommended: { level: Ui3D; reason: string } | null): { level: Ui3D; reason: string } | null {
  if (!webglWorks()) return { level: "off", reason: "3D (WebGL) doesn't work in this window on this PC." };
  return recommended;
}

interface Props {
  value: Ui3D;
  onChange(level: Ui3D): void;
  recommended: { level: Ui3D; reason: string } | null;
  name?: string;
}

export function LevelPicker({ value, onChange, recommended, name = "ui3d" }: Props) {
  const advice = advise(recommended);
  return (
    <div className="level-picker">
      <div className="level-options" role="radiogroup" aria-label="3D effects">
        {LEVELS.map((l) => (
          <label key={l.id} className={value === l.id ? "level selected" : "level"}>
            <input type="radio" name={name} value={l.id} checked={value === l.id} onChange={() => onChange(l.id)} />
            <span className="level-title">
              {l.title}
              {advice?.level === l.id && <span className="badge">Recommended</span>}
            </span>
            <span className="level-text">{l.text}</span>
          </label>
        ))}
      </div>
      {advice && (
        <p className="hint" role="status">
          Why {LEVELS.find((l) => l.id === advice.level)?.title.toLowerCase()}: {advice.reason}
        </p>
      )}
    </div>
  );
}
