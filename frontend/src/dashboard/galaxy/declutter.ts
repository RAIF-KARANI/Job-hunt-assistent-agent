// 16a: labels of jobs that sit close together used to cover each other, so
// none could be read. After the jobs are placed, the labels are measured and
// a label that would touch one already kept is hidden. Order = who keeps
// theirs: the selected job first, then best fit first (the order of the
// buttons). A hidden label still shows on hover, focus and selection (CSS).
//
// The mark is a data attribute, not a class: React owns `className` and
// would wipe a class on the next render.

const GAP = 3; // px kept free around a label

function touches(a: DOMRect, b: DOMRect): boolean {
  return a.left < b.right + GAP && b.left < a.right + GAP && a.top < b.bottom + GAP && b.top < a.bottom + GAP;
}

export function declutterLabels(root: HTMLElement): void {
  const kept: DOMRect[] = [];
  const core = root.querySelector<HTMLElement>(".galaxy-core");
  if (core) kept.push(core.getBoundingClientRect());

  const labeled = [...root.querySelectorAll<HTMLElement>(".galaxy-node.labeled")];
  labeled.sort((a, b) => Number(b.classList.contains("selected")) - Number(a.classList.contains("selected"))); // stable

  // Measure everything first, then write: no layout work between the two.
  const crowded = new Set<HTMLElement>();
  for (const node of labeled) {
    const label = node.querySelector<HTMLElement>(".galaxy-label");
    if (!label) continue;
    const box = label.getBoundingClientRect();
    if (box.width === 0) continue; // not laid out yet
    if (kept.some((other) => touches(other, box))) crowded.add(node);
    else kept.push(box);
  }
  for (const node of root.querySelectorAll<HTMLElement>(".galaxy-node")) {
    if (crowded.has(node)) node.dataset.crowded = "";
    else delete node.dataset.crowded;
  }
}
