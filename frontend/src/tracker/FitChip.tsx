import { fitLevel } from "./status";

/** The fit score as a colored chip: high (75+), mid (55+), low. */
export function FitChip({ score, large = false }: { score: number; large?: boolean }) {
  return (
    <span className={`fit-chip fit-${fitLevel(score)}${large ? " large" : ""}`} title={`Fit ${score} out of 100`}>
      {score}
    </span>
  );
}
