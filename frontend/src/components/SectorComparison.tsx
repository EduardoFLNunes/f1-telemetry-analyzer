import React, { useMemo } from 'react';
import { useTelemetryStore } from '../store/useTelemetryStore';
import { useRenderCounter } from '../hooks/useRenderCounter';
import {
  bestSplits,
  formatSplit,
  sectorSplits,
  sectorTones,
  SECTOR_COUNT,
  SectorTone,
} from '../utils/sectorTimes';

/**
 * How the lap is going, one third at a time.
 *
 * The times are measured here rather than received: nothing in the telemetry
 * carries a sector duration, only which sector the car is in. `sectorTimes.ts`
 * derives them from the lap clock at each crossing, which is why a sector that
 * is still being driven shows dashes instead of a running total.
 */

const TONE_COLOURS: Record<Exclude<SectorTone, null>, string> = {
  purple: '#c084fc',
  green: '#4ade80',
  yellow: '#facc15',
};

const LEGEND: Array<[string, string]> = [
  ['#facc15', 'mais lento'],
  ['#4ade80', 'melhor seu'],
  ['#c084fc', 'melhor sessao'],
];

export const SectorComparison: React.FC = () => {
  useRenderCounter('SectorComparison');
  const currentLapSamples = useTelemetryStore((state) => state.currentLapSamples);
  const previousLapSamples = useTelemetryStore((state) => state.previousLapSamples);
  const completedLaps = useTelemetryStore((state) => state.completedLapsHistory);
  const offlineReplay = useTelemetryStore((state) => state.offlineReplay);

  const { splits, tones } = useMemo(() => {
    // In replay the lap being watched is the one to cut up; live, it is the lap
    // under the car right now.
    const lapSamples = offlineReplay.active && offlineReplay.samples.length
      ? offlineReplay.samples.slice(0, (offlineReplay.currentIndex || 0) + 1)
      : currentLapSamples;
    const reference = offlineReplay.active ? offlineReplay.referenceSamples : previousLapSamples;

    const current = sectorSplits(lapSamples || []);
    const referenceSplits = sectorSplits(reference || []);
    const session = bestSplits([
      ...(completedLaps || []).filter((lap: any) => lap?.valid !== false).map((lap: any) => lap.samples || []),
      reference || [],
    ]);
    return { splits: current, tones: sectorTones(current, referenceSplits, session) };
  }, [currentLapSamples, previousLapSamples, completedLaps, offlineReplay]);

  return (
    <div className="panel sector-panel">
      <span className="label">Comparacao por setor</span>

      <div className="sector-grid">
        {Array.from({ length: SECTOR_COUNT }, (_, index) => {
          const tone = tones[index];
          const colour = tone ? TONE_COLOURS[tone] : 'rgba(148,163,184,0.35)';
          return (
            <div key={index} className="sector-cell" style={{ borderColor: `${colour}44` }}>
              <span className="label sector-name">SET {index + 1}</span>
              <span className="num sector-time" style={{ color: tone ? colour : 'var(--text-2)' }}>
                {formatSplit(splits[index])}
              </span>
              <span className="sector-tick" style={{ background: colour }} />
            </div>
          );
        })}
      </div>

      <div className="sector-legend">
        {LEGEND.map(([colour, text]) => (
          <span key={text} className="sector-legend-item">
            <i style={{ background: colour }} />
            {text}
          </span>
        ))}
      </div>
    </div>
  );
};

export default SectorComparison;
