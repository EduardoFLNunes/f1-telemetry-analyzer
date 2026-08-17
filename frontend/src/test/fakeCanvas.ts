/**
 * A canvas that records instead of drawing.
 *
 * The renderers here are pure functions of the track data and the zoom -- they
 * take a context and issue orders to it. Recording those orders is enough to say
 * whether the paint came out in the right order, at the right width, and whether
 * the fill rule that keeps the infield clean is still being asked for. Every
 * call carries the style that was in force when it was made, because that is
 * what a stroke actually looks like.
 */

export type RecordedCall = {
  op: string;
  args: any[];
  strokeStyle: any;
  fillStyle: any;
  lineWidth: number;
  globalAlpha: number;
};

const OPS = [
  'beginPath', 'closePath', 'moveTo', 'lineTo', 'arc', 'ellipse', 'rect',
  'quadraticCurveTo', 'bezierCurveTo', 'clip', 'stroke', 'fill', 'fillRect',
  'strokeRect', 'clearRect', 'fillText', 'strokeText', 'translate', 'scale',
  'rotate', 'transform', 'setTransform', 'resetTransform', 'setLineDash',
  'drawImage',
];

export type FakeContext = any & { calls: RecordedCall[] };

export function createFakeContext(): FakeContext {
  const calls: RecordedCall[] = [];
  const stack: Array<Record<string, any>> = [];
  const STYLE_KEYS = [
    'strokeStyle', 'fillStyle', 'lineWidth', 'globalAlpha', 'lineCap', 'lineJoin',
    'font', 'globalCompositeOperation', 'lineDashOffset', 'miterLimit',
  ];

  const ctx: any = {
    calls,
    strokeStyle: '#000',
    fillStyle: '#000',
    lineWidth: 1,
    globalAlpha: 1,
    lineCap: 'butt',
    lineJoin: 'miter',
    font: '10px sans-serif',
    globalCompositeOperation: 'source-over',
    lineDashOffset: 0,
    miterLimit: 10,
    canvas: { width: 800, height: 600 },
  };

  const record = (op: string) => (...args: any[]) => {
    calls.push({
      op,
      args,
      strokeStyle: ctx.strokeStyle,
      fillStyle: ctx.fillStyle,
      lineWidth: ctx.lineWidth,
      globalAlpha: ctx.globalAlpha,
    });
  };

  for (const op of OPS) ctx[op] = record(op);

  // save/restore actually restore, so a test can catch a renderer leaking its
  // style onto whatever is drawn next.
  ctx.save = (...args: any[]) => {
    const snapshot: Record<string, any> = {};
    for (const key of STYLE_KEYS) snapshot[key] = ctx[key];
    stack.push(snapshot);
    record('save')(...args);
  };
  ctx.restore = (...args: any[]) => {
    const snapshot = stack.pop();
    if (snapshot) Object.assign(ctx, snapshot);
    record('restore')(...args);
  };

  ctx.measureText = (text: string) => ({ width: String(text).length * 5 });
  ctx.createLinearGradient = () => ({ addColorStop() {} });
  ctx.createRadialGradient = () => ({ addColorStop() {} });
  ctx.getTransform = () => ({ a: 1, b: 0, c: 0, d: 1, e: 0, f: 0 });

  return ctx as FakeContext;
}

/** Every call of one kind, oldest first. */
export function callsOf(ctx: FakeContext, op: string): RecordedCall[] {
  return ctx.calls.filter((call: RecordedCall) => call.op === op);
}

/** The sequence of operations, for order assertions. */
export function opSequence(ctx: FakeContext): string[] {
  return ctx.calls.map((call: RecordedCall) => call.op);
}

/** A Path2D that remembers what was traced into it. */
export class FakePath2D {
  /** How many have been built, so a test can prove a path is cached. */
  static created = 0;

  ops: Array<{ op: string; args: any[] }> = [];

  constructor() {
    FakePath2D.created += 1;
  }

  moveTo(...args: any[]) { this.ops.push({ op: 'moveTo', args }); }
  lineTo(...args: any[]) { this.ops.push({ op: 'lineTo', args }); }
  closePath(...args: any[]) { this.ops.push({ op: 'closePath', args }); }
  arc(...args: any[]) { this.ops.push({ op: 'arc', args }); }
  rect(...args: any[]) { this.ops.push({ op: 'rect', args }); }
  quadraticCurveTo(...args: any[]) { this.ops.push({ op: 'quadraticCurveTo', args }); }
  bezierCurveTo(...args: any[]) { this.ops.push({ op: 'bezierCurveTo', args }); }
}

/** Installs FakePath2D globally; returns the undo. */
export function installFakePath2D(): () => void {
  const previous = (globalThis as any).Path2D;
  (globalThis as any).Path2D = FakePath2D;
  return () => {
    if (previous === undefined) delete (globalThis as any).Path2D;
    else (globalThis as any).Path2D = previous;
  };
}

/** Parses `rgba(r,g,b,a)` into its four numbers. */
export function parseRgba(colour: any): { r: number; g: number; b: number; a: number } | null {
  const match = /rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*(?:,\s*([\d.]+)\s*)?\)/.exec(String(colour));
  if (!match) return null;
  return {
    r: Number(match[1]),
    g: Number(match[2]),
    b: Number(match[3]),
    a: match[4] === undefined ? 1 : Number(match[4]),
  };
}
