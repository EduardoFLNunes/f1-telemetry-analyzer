import { describe, expect, it } from 'vitest';
import {
  bestSplits,
  clockAt,
  formatSplit,
  sectorSplits,
  sectorTones,
} from './sectorTimes';

/** A lap of samples: `seconds` long, evenly spaced, progress 0 to 1. */
function lap(seconds: number, options: { count?: number; clock?: 'lap_time' | 'sessionTime'; offset?: number } = {}) {
  const count = options.count ?? 120;
  const offset = options.offset ?? 0;
  return Array.from({ length: count }, (_, index) => {
    const progress = index / (count - 1);
    const elapsed = progress * seconds;
    return options.clock === 'sessionTime'
      ? { sessionTime: offset + elapsed, lap_time: null, lapProgress: progress }
      : { lap_time: elapsed, lapProgress: progress };
  });
}

describe('clockAt', () => {
  it('refuses an explicit null instead of reading it as zero', () => {
    // The frames carry `lap_time: null`, and Number(null) is 0. A finite check
    // written the obvious way turns every gap into a lap that began at zero.
    expect(clockAt({ lap_time: null })).toBeNull();
    expect(clockAt({ lap_time: null, sessionTime: null })).toBeNull();
    expect(clockAt({})).toBeNull();
    expect(clockAt({ lap_time: 0 })).toBe(0);
  });

  it('falls back to the session clock when the lap clock is missing', () => {
    expect(clockAt({ lap_time: null, sessionTime: 942.5 })).toBe(942.5);
    expect(clockAt({ lap_time: 12.5, sessionTime: 942.5 })).toBe(12.5);
  });
});

describe('sectorSplits', () => {
  it('cuts a lap into three sectors that add up to the lap', () => {
    const splits = sectorSplits(lap(90));
    expect(splits.every((split) => split !== null)).toBe(true);
    const total = splits.reduce<number>((sum, split) => sum + (split ?? 0), 0);
    expect(total).toBeCloseTo(90, 1);
    for (const split of splits) expect(split).toBeCloseTo(30, 0);
  });

  it('measures from the first sample of the lap, not from an absolute clock', () => {
    // sessionTime counts from the start of the session and does not reset at
    // the line; read absolutely, the third sector of lap nine lasts minutes.
    const late = lap(90, { clock: 'sessionTime', offset: 4200 });
    const splits = sectorSplits(late);
    for (const split of splits) expect(split).toBeCloseTo(30, 0);
  });

  it('leaves a sector the car has not finished empty', () => {
    const half = lap(90).filter((sample) => sample.lapProgress <= 0.5);
    const splits = sectorSplits(half);
    expect(splits[0]).toBeCloseTo(30, 0);
    // Half of sector two is not a sector-two time.
    expect(splits[1]).toBeNull();
    expect(splits[2]).toBeNull();
  });

  it('has nothing to say about a lap with no clock at all', () => {
    const clockless = Array.from({ length: 60 }, (_, index) => ({ lap_time: null, lapProgress: index / 59 }));
    expect(sectorSplits(clockless)).toEqual([null, null, null]);
    expect(sectorSplits([])).toEqual([null, null, null]);
    expect(sectorSplits(null as any)).toEqual([null, null, null]);
  });

  it('ignores samples whose clock runs backwards into the lap before', () => {
    const samples = [
      { lap_time: 84.2, lapProgress: 0.99 },   // tail of the previous lap
      ...lap(90),
    ];
    const splits = sectorSplits(samples);
    for (const split of splits) expect(split).not.toBeNull();
  });

  it('does not report uneven sectors when the samples are sparse', () => {
    const splits = sectorSplits(lap(90, { count: 12 }));
    const total = splits.reduce<number>((sum, split) => sum + (split ?? 0), 0);
    expect(total).toBeGreaterThan(80);
    expect(total).toBeLessThanOrEqual(90.001);
  });
});

describe('bestSplits and sectorTones', () => {
  it('takes the quickest each sector has been across the session', () => {
    const best = bestSplits([lap(90), lap(87), lap(93)]);
    for (const split of best) expect(split).toBeCloseTo(29, 0);
  });

  it('paints the session best purple, an improvement green and the rest yellow', () => {
    const tones = sectorTones([28, 31, 26], [29, 30, 27], [28, 29, 25]);
    expect(tones).toEqual(['purple', 'yellow', 'green']);
  });

  it('leaves a sector uncoloured rather than flattering it', () => {
    // Nothing to compare against is not the same as being quick.
    expect(sectorTones([28, null, 26], [null, null, null], [null, null, null]))
      .toEqual([null, null, null]);
    expect(sectorTones([null, null, null], [29, 30, 27], [28, 29, 25]))
      .toEqual([null, null, null]);
  });

  it('calls a tie with the session best purple', () => {
    expect(sectorTones([28], [27], [28])[0]).toBe('purple');
  });
});

describe('formatSplit', () => {
  it('shows seconds for a sector and minutes only when it needs them', () => {
    expect(formatSplit(28.114)).toBe('28.114');
    expect(formatSplit(72.5)).toBe('1:12.500');
    expect(formatSplit(null)).toBe('--.---');
    expect(formatSplit(NaN)).toBe('--.---');
  });
});
