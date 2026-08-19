/**
 * Sector splits, derived from the lap clock.
 *
 * Nothing sends them. The backend reports which sector the car is in and never
 * how long the last one took, and `setSectors` in the store has no caller. So
 * the splits here are measured: walk the lap's samples, note the clock each
 * time the car crosses a third of the lap, and difference those crossings.
 *
 * Two things about the clock decide whether this reads a lap or invents one.
 *
 * The frames carry `lap_time: null` explicitly, and `Number(null)` is `0`, not
 * `NaN` -- a "finite number" check written the obvious way turns every gap into
 * a lap that started at zero. `clockAt` refuses null before it looks at the
 * number.
 *
 * And the fallback clock, `sessionTime`, counts from the start of the session
 * and does not reset at the line. Only differences from the lap's own first
 * sample mean anything; an absolute value would report the third sector of lap
 * nine as twelve minutes long.
 */

export const SECTOR_COUNT = 3;

export type SectorTone = 'purple' | 'green' | 'yellow' | null;

function strictNumber(value: unknown): number | null {
  if (value === null || value === undefined || value === '') return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

/** The lap clock at one sample, or null when the sample has no clock at all. */
export function clockAt(sample: any): number | null {
  const lapTime = strictNumber(sample?.lap_time ?? sample?.lapTime);
  if (lapTime !== null && lapTime >= 0) return lapTime;
  return strictNumber(sample?.lapSampleTime ?? sample?.sessionTime ?? sample?.session_time ?? sample?.timestamp);
}

/** How far round the lap a sample is, 0 to 1, or null. */
export function progressAt(sample: any): number | null {
  for (const candidate of [sample?.lapProgress, sample?.p, sample?.normalizedSplinePosition, sample?.splinePosition]) {
    const number = strictNumber(candidate);
    if (number !== null && number >= 0 && number <= 1) return number;
  }
  return null;
}

/**
 * Only the samples since the last time the lap wrapped.
 *
 * A live buffer usually opens with the tail of the previous lap. Those samples
 * sit at 0.99 of the way round, which crosses both sector lines at once and
 * hands sector one the whole lap. Progress falling off a cliff is the flag; the
 * lap is whatever came after the last one.
 */
function lastLapSegment(samples: any[]): any[] {
  let startIndex = 0;
  let previous: number | null = null;
  for (let index = 0; index < samples.length; index += 1) {
    const progress = progressAt(samples[index]);
    if (progress === null) continue;
    if (previous !== null && progress < previous - 0.5) startIndex = index;
    previous = progress;
  }
  return startIndex === 0 ? samples : samples.slice(startIndex);
}

/**
 * Time spent in each third of the lap.
 *
 * A sector the car has not finished is null rather than a partial figure: half
 * of sector two is not a sector-two time, and showing it as one would make
 * every comparison against it wrong.
 */
export function sectorSplits(samples: any[]): Array<number | null> {
  const splits: Array<number | null> = Array(SECTOR_COUNT).fill(null);
  if (!Array.isArray(samples) || samples.length < 2) return splits;
  const lap = lastLapSegment(samples);
  if (lap.length < 2) return splits;

  // The lap starts at the smallest clock in the window, not at the first
  // sample. A buffer often opens with the tail of the previous lap, whose
  // lap_time is high; taking that as the start makes every elapsed negative and
  // the whole lap disappears.
  let start: number | null = null;
  for (const sample of lap) {
    const clock = clockAt(sample);
    if (clock !== null && (start === null || clock < start)) start = clock;
  }
  if (start === null) return splits;

  // Elapsed at each boundary crossing: a third of the lap, then two thirds,
  // then the flag. The crossing falls between two samples, so it is
  // interpolated -- taking the first sample past the line instead would report
  // a sector short or long by however far apart the samples happen to be.
  const boundaries: Array<number | null> = Array(SECTOR_COUNT).fill(null);
  let reached = 0;
  let lastElapsed: number | null = null;
  let previousProgress: number | null = null;
  let previousElapsed: number | null = null;

  for (const sample of lap) {
    const clock = clockAt(sample);
    const progress = progressAt(sample);
    if (clock === null) continue;
    const elapsed = clock - start;
    if (elapsed < 0) continue;
    lastElapsed = elapsed;
    if (progress === null) continue;

    while (reached < SECTOR_COUNT - 1 && progress >= (reached + 1) / SECTOR_COUNT) {
      const line = (reached + 1) / SECTOR_COUNT;
      let at = elapsed;
      if (previousProgress !== null && previousElapsed !== null && progress > previousProgress) {
        const t = (line - previousProgress) / (progress - previousProgress);
        if (t >= 0 && t <= 1) at = previousElapsed + (elapsed - previousElapsed) * t;
      }
      boundaries[reached] = at;
      reached += 1;
    }
    previousProgress = progress;
    previousElapsed = elapsed;
  }

  // The last sector closes on the flag, which is the end of the samples -- there
  // is no fourth boundary to cross.
  if (reached >= SECTOR_COUNT - 1 && lastElapsed !== null) {
    const finalProgress = progressAt(lap[lap.length - 1]);
    if (finalProgress !== null && finalProgress >= 0.985) {
      boundaries[SECTOR_COUNT - 1] = lastElapsed;
    }
  }

  let previous = 0;
  for (let index = 0; index < SECTOR_COUNT; index += 1) {
    const at = boundaries[index];
    if (at === null) break;
    const split = at - previous;
    splits[index] = split > 0 ? split : null;
    previous = at;
  }
  return splits;
}

/** The quickest each sector has been across a set of laps. */
export function bestSplits(laps: Array<any[]>): Array<number | null> {
  const best: Array<number | null> = Array(SECTOR_COUNT).fill(null);
  for (const samples of laps) {
    const splits = sectorSplits(samples);
    for (let index = 0; index < SECTOR_COUNT; index += 1) {
      const split = splits[index];
      if (split === null) continue;
      if (best[index] === null || split < (best[index] as number)) best[index] = split;
    }
  }
  return best;
}

/**
 * The broadcast colours, given what this lap did and what the session has seen.
 *
 * Purple is the quickest that sector has been all session, green is quicker
 * than the lap being compared against, yellow is slower. A sector with nothing
 * to compare against gets no colour rather than a flattering one.
 */
export function sectorTones(
  current: Array<number | null>,
  reference: Array<number | null>,
  sessionBest: Array<number | null>,
): SectorTone[] {
  return current.map((split, index) => {
    if (split === null) return null;
    const best = sessionBest[index];
    if (best !== null && split <= best + 1e-6) return 'purple';
    const previous = reference[index];
    if (previous === null) return null;
    return split < previous ? 'green' : 'yellow';
  });
}

/** m:ss.mmm for a split, or a placeholder when the sector is not done. */
export function formatSplit(split: number | null): string {
  if (split === null || !Number.isFinite(split)) return '--.---';
  if (split < 60) return split.toFixed(3);
  const minutes = Math.floor(split / 60);
  return `${minutes}:${(split - minutes * 60).toFixed(3).padStart(6, '0')}`;
}
