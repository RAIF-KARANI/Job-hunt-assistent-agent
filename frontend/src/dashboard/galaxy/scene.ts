// The 3D job galaxy, in plain three.js (D19). Kept imperative and outside
// React so the frame loop is fully ours:
//   - animated: slow spin, at most 30 frames a second (D12)
//   - still: a frame is drawn only when something changes (drag, resize...)
//   - paused while the agent runs or the window is hidden: same as still
// The job labels are HTML buttons over the canvas; after every frame the
// scene tells the page where each job landed on screen (`place`).

import {
  AdditiveBlending,
  BufferGeometry,
  CanvasTexture,
  Color,
  Float32BufferAttribute,
  Group,
  LineBasicMaterial,
  LineDashedMaterial,
  LineLoop,
  Mesh,
  MeshBasicMaterial,
  NormalBlending,
  PerspectiveCamera,
  Points,
  PointsMaterial,
  Scene,
  SphereGeometry,
  Sprite,
  SpriteMaterial,
  Vector3,
  WebGLRenderer,
  type Blending,
  type Material,
  type Texture,
} from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { RINGS, type Placed } from "./layout";

/** Screen position of a job's dot; `near` is 1 for the closest job, 0 for the farthest. */
export type PlaceFn = (id: number, x: number, y: number, near: number) => void;

const SCALE = 3.6; // world units for the unit disc of layout.ts
const FRAME_MS = 1000 / 30; // D12: never more than 30 FPS
const TURN_SECONDS = 90; // one full turn
const CORE_ID = -1;

interface Palette {
  high: Color;
  mid: Color;
  low: Color;
  core: Color;
  star: Color;
  blending: Blending;
  glow: number;
}

function readPalette(): Palette {
  const css = getComputedStyle(document.documentElement);
  const color = (name: string) => new Color(css.getPropertyValue(name).trim() || "#888888");
  const dark = document.documentElement.dataset.theme !== "light";
  return {
    high: color("--fit-high"),
    mid: color("--fit-mid"),
    low: color("--fit-low"),
    core: color("--accent"),
    star: color("--galaxy-star"),
    // Light glows add up to white on a dark sky; on a light one they'd vanish.
    blending: dark ? AdditiveBlending : NormalBlending,
    glow: dark ? 0.55 : 0.28,
  };
}

/** A soft round spot, tinted by each sprite's color. */
function glowTexture(): Texture {
  const size = 128;
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = size;
  const ctx = canvas.getContext("2d")!;
  const g = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
  g.addColorStop(0, "rgba(255,255,255,1)");
  g.addColorStop(0.25, "rgba(255,255,255,0.45)");
  g.addColorStop(1, "rgba(255,255,255,0)");
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, size, size);
  return new CanvasTexture(canvas);
}

function ringTexture(): Texture {
  const size = 128;
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = size;
  const ctx = canvas.getContext("2d")!;
  ctx.strokeStyle = "#ffffff";
  ctx.lineWidth = 7;
  ctx.beginPath();
  ctx.arc(size / 2, size / 2, size / 2 - 8, 0, Math.PI * 2);
  ctx.stroke();
  return new CanvasTexture(canvas);
}

/** The same "random" stars every time (no flicker between visits). */
function seeded(seed: number) {
  return () => {
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function circle(radius: number): BufferGeometry {
  const points: number[] = [];
  for (let i = 0; i < 128; i++) {
    const a = (i / 128) * Math.PI * 2;
    points.push(Math.cos(a) * radius, 0, Math.sin(a) * radius);
  }
  return new BufferGeometry().setAttribute("position", new Float32BufferAttribute(points, 3));
}

export class GalaxyScene {
  private renderer: WebGLRenderer;
  private scene = new Scene();
  private camera = new PerspectiveCamera(40, 1, 0.1, 100);
  private controls: OrbitControls;
  private spin = new Group(); // rings + jobs; turns when animated
  private jobsGroup = new Group();
  private decor = new Group(); // rings, core, stars: rebuilt on theme change
  private sphere = new SphereGeometry(1, 24, 16);
  private glow = glowTexture();
  private ring = ringTexture();
  private selection: Sprite;
  private nodes = new Map<number, Mesh>();
  private palette = readPalette();
  private animate = false;
  private raf = 0;
  private last = 0;
  private width = 1;
  private height = 1;
  private v = new Vector3();
  private resizeObserver: ResizeObserver;

  constructor(
    private host: HTMLElement,
    private place: PlaceFn,
    private onLost: () => void,
  ) {
    // Throws when WebGL isn't available; the caller falls back to the flat map.
    // "low-power": on laptops with two GPUs, keep the big one for the local LLM.
    this.renderer = new WebGLRenderer({ antialias: true, alpha: true, powerPreference: "low-power" });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.domElement.className = "galaxy-canvas";
    this.renderer.domElement.addEventListener("webglcontextlost", this.lost);
    host.prepend(this.renderer.domElement);

    this.camera.position.set(0, 4.5, 6.85); // ~33° above the disc
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enablePan = false;
    this.controls.enableZoom = false; // the wheel scrolls the page; zoom has buttons
    this.controls.minPolarAngle = Math.PI * 0.12;
    this.controls.maxPolarAngle = Math.PI * 0.6;
    this.controls.rotateSpeed = 0.6;
    this.controls.dampingFactor = 0.08;
    this.controls.addEventListener("change", this.requestFrame);

    this.selection = new Sprite(new SpriteMaterial({ map: this.ring, transparent: true, depthWrite: false }));
    this.selection.visible = false;
    this.spin.add(this.decor, this.jobsGroup, this.selection);
    this.scene.add(this.spin);
    this.buildDecor();

    this.resizeObserver = new ResizeObserver(this.resize);
    this.resizeObserver.observe(host);
    document.addEventListener("visibilitychange", this.onVisibility);
    this.resize();
  }

  // ---- what the page changes ------------------------------------------------

  setJobs(nodes: Placed[], selectedId: number | null): void {
    for (const mesh of this.nodes.values()) {
      this.jobsGroup.remove(mesh);
      (mesh.material as Material).dispose();
      (mesh.children[0] as Sprite).material.dispose();
    }
    this.nodes.clear();
    for (const node of nodes) {
      const color = this.palette[node.level];
      const mesh = new Mesh(this.sphere, new MeshBasicMaterial({ color }));
      const size = 0.07 + (node.job.fit_score / 100) * 0.09;
      mesh.scale.setScalar(size);
      mesh.position.set(node.x * SCALE, node.y * SCALE, node.z * SCALE);
      const halo = new Sprite(
        new SpriteMaterial({ map: this.glow, color, transparent: true, opacity: this.palette.glow, blending: this.palette.blending, depthWrite: false }),
      );
      halo.scale.setScalar(7); // relative to the sphere's own scale
      mesh.add(halo);
      this.jobsGroup.add(mesh);
      this.nodes.set(node.job.id, mesh);
    }
    this.setSelected(selectedId);
  }

  setSelected(id: number | null): void {
    const mesh = id === null ? undefined : this.nodes.get(id);
    this.selection.visible = Boolean(mesh);
    if (mesh) {
      this.selection.position.copy(mesh.position);
      this.selection.scale.setScalar(mesh.scale.x * 4.2);
      this.selection.material.color.copy(this.palette.core);
    }
    this.requestFrame();
  }

  setAnimate(animate: boolean): void {
    this.animate = animate;
    this.controls.enableDamping = animate; // damping needs a running loop
    this.last = performance.now();
    this.requestFrame();
  }

  /** Theme changed: re-read the colors. */
  recolor(nodes: Placed[], selectedId: number | null): void {
    this.palette = readPalette();
    this.buildDecor();
    this.setJobs(nodes, selectedId);
  }

  zoom(factor: number): void {
    const distance = Math.min(16, Math.max(4.5, this.camera.position.length() * factor));
    this.camera.position.setLength(distance);
    this.controls.update();
    this.requestFrame();
  }

  resetView(): void {
    this.camera.position.set(0, 4.5, 6.85); // ~33° above the disc
    this.fitToWidth();
    this.spin.rotation.y = 0;
    this.controls.update();
    this.requestFrame();
  }

  dispose(): void {
    cancelAnimationFrame(this.raf);
    this.resizeObserver.disconnect();
    document.removeEventListener("visibilitychange", this.onVisibility);
    this.controls.dispose();
    this.setJobs([], null);
    this.clearDecor();
    this.sphere.dispose();
    this.glow.dispose();
    this.ring.dispose();
    this.selection.material.dispose();
    // Free the GPU context now: page switches would otherwise pile them up
    // until the browser starts dropping old ones.
    this.renderer.domElement.removeEventListener("webglcontextlost", this.lost);
    this.renderer.dispose();
    this.renderer.forceContextLoss();
    this.renderer.domElement.remove();
  }

  // ---- inside -------------------------------------------------------------

  private buildDecor(): void {
    this.clearDecor();
    const p = this.palette;
    const ringColors = [p.high, p.mid, p.low];
    RINGS.forEach((r, i) => {
      const material =
        i === 0
          ? new LineBasicMaterial({ color: ringColors[i], transparent: true, opacity: 0.45 })
          : new LineDashedMaterial({ color: ringColors[i], transparent: true, opacity: 0.45, dashSize: 0.12, gapSize: 0.1 });
      const line = new LineLoop(circle(r * SCALE), material);
      line.computeLineDistances();
      this.decor.add(line);
    });

    const core = new Mesh(this.sphere, new MeshBasicMaterial({ color: p.core }));
    core.scale.setScalar(0.34);
    const halo = new Sprite(
      new SpriteMaterial({ map: this.glow, color: p.core, transparent: true, opacity: p.glow + 0.15, blending: p.blending, depthWrite: false }),
    );
    halo.scale.setScalar(7);
    core.add(halo);
    this.decor.add(core);

    const random = seeded(7);
    const stars: number[] = [];
    for (let i = 0; i < 700; i++) {
      const r = 14 + random() * 16;
      const theta = random() * Math.PI * 2;
      const phi = Math.acos(2 * random() - 1);
      stars.push(r * Math.sin(phi) * Math.cos(theta), r * Math.cos(phi), r * Math.sin(phi) * Math.sin(theta));
    }
    const starGeometry = new BufferGeometry().setAttribute("position", new Float32BufferAttribute(stars, 3));
    this.decor.add(new Points(starGeometry, new PointsMaterial({ color: p.star, size: 0.07, transparent: true, opacity: 0.7, depthWrite: false })));
  }

  private clearDecor(): void {
    this.decor.traverse((o) => {
      if (o === this.decor) return;
      const thing = o as Mesh;
      // Sprites share one geometry inside three.js, and the sphere is ours to keep.
      if (thing.geometry && thing.geometry !== this.sphere && !(o instanceof Sprite)) thing.geometry.dispose();
      (thing.material as Material | undefined)?.dispose();
    });
    this.decor.clear();
  }

  private requestFrame = () => {
    if (!this.raf && document.visibilityState === "visible") this.raf = requestAnimationFrame(this.frame);
  };

  private frame = (now: number) => {
    this.raf = 0;
    if (this.animate) {
      this.raf = requestAnimationFrame(this.frame);
      const elapsed = now - this.last;
      if (elapsed < FRAME_MS - 2) return; // the 30 FPS cap
      // A fixed 33.3 ms schedule: holds 30 FPS without ever going over it.
      // (`last = now` slipped every frame to the next display refresh: ~21 FPS.)
      this.last = elapsed > FRAME_MS * 2 ? now : this.last + FRAME_MS;
      this.spin.rotation.y += (Math.min(elapsed, 100) / 1000) * ((Math.PI * 2) / TURN_SECONDS);
      this.controls.update();
    }
    this.draw();
  };

  private draw(): void {
    this.renderer.render(this.scene, this.camera);
    const distances: [number, number, number, number][] = [];
    for (const [id, mesh] of this.nodes) distances.push(this.project(id, mesh.getWorldPosition(this.v)));
    distances.push(this.project(CORE_ID, this.v.set(0, 0, 0)));
    const near = Math.min(...distances.map((d) => d[3]));
    const far = Math.max(...distances.map((d) => d[3]));
    for (const [id, x, y, d] of distances) this.place(id, x, y, far > near ? (far - d) / (far - near) : 1);
  }

  private project(id: number, world: Vector3): [number, number, number, number] {
    const distance = world.distanceTo(this.camera.position);
    world.project(this.camera);
    return [id, ((world.x + 1) / 2) * this.width, ((1 - world.y) / 2) * this.height, distance];
  }

  private resize = () => {
    this.width = Math.max(1, this.host.clientWidth);
    this.height = Math.max(1, this.host.clientHeight);
    this.renderer.setSize(this.width, this.height);
    this.camera.aspect = this.width / this.height;
    this.fitToWidth();
    this.camera.updateProjectionMatrix();
    this.controls.update();
    this.draw(); // now, not next frame: the canvas was just cleared
  };

  /** A narrow card moves the camera back so the outer ring still fits. */
  private fitToWidth(): void {
    const wide = Math.min(1, this.camera.aspect / 1.35);
    const base = 8.2 / wide;
    if (Math.abs(this.camera.position.length() - base) > 0.01) this.camera.position.setLength(Math.min(16, base));
  }

  private onVisibility = () => {
    if (document.visibilityState === "visible") {
      this.last = performance.now();
      this.requestFrame();
    } else {
      cancelAnimationFrame(this.raf);
      this.raf = 0;
    }
  };

  private lost = (event: Event) => {
    event.preventDefault();
    cancelAnimationFrame(this.raf);
    this.onLost();
  };
}

export { CORE_ID };
