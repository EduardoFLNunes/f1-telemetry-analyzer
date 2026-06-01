import { OpponentCarState, TelemetryFrame } from '../store/useTelemetryStore';

export type LossReason = 'BRAKING' | 'ACCELERATION' | 'SPEED' | 'TRAJECTORY' | 'UNKNOWN' | null;

type AnalysisSample = {
  progress: number | null;
  speedKmh: number | null;
  position: [number, number, number] | null;
  throttle: number | null;
  brake: number | null;
};

type SpeedStats = {
  avgSpeedKmh: number | null;
  minSpeedKmh: number | null;
  maxSpeedKmh: number | null;
};

export type ComparisonOpponent = {
  carId: number;
  avgSpeedKmh: number | null;
  minSpeedKmh: number | null;
  maxSpeedKmh: number | null;
  deltaToPlayerSeconds: number | null;
  deltaToReferenceSeconds: number | null;
  trajectoryDeviationMeters: number | null;
  brakingEarlierThanPlayer: boolean | null;
  acceleratingEarlierThanPlayer: boolean | null;
  classification: string;
};

export type ComparisonSegment = {
  segmentIndex: number;
  splineStart: number;
  splineEnd: number;
  sector: 1 | 2 | 3;
  player: SpeedStats;
  reference: SpeedStats;
  opponents: ComparisonOpponent[];
  playerVsReference: {
    deltaSeconds: number | null;
    speedDeltaKmh: number | null;
    trajectoryDeviationMeters: number | null;
    mainLossReason: LossReason;
  };
};

export type ComparisonPayload = {
  track: string | null;
  generatedAt: string;
  microSectorCount: number;
  sectors: Array<{
    sector: 1 | 2 | 3;
    playerVsReferenceDeltaSeconds: number | null;
    mainLossReason: string | null;
    bestOpponentCarId: number | null;
    worstSegmentIndex: number | null;
  }>;
  biggestLosses: Array<Record<string, any>>;
  biggestGains: Array<Record<string, any>>;
  opponentRanking: Array<{ carId: number; estimatedAdvantageSeconds: number | null; validSegments: number }>;
  segments: ComparisonSegment[];
  debug: {
    playerSamples: number;
    referenceSamples: number;
    opponentsAnalyzed: number;
    validMicroSectors: number;
    rejectedSegments: number;
    rejectionReasons: Record<string, number>;
    notes: string[];
  };
};

const finite = (value: unknown): number | null => {
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
};

const clamp01 = (value: number) => Math.max(0, Math.min(1, value));

const roundOrNull = (value: number | null, digits = 4): number | null => (
  value === null || !Number.isFinite(value) ? null : Number(value.toFixed(digits))
);

const frameProgress = (frame: TelemetryFrame): number | null => {
  const candidates = [
    frame.lapProgress,
    frame.p,
    frame.normalizedSplinePosition,
    frame.splinePosition,
    frame.spline_t,
  ];
  for (const candidate of candidates) {
    const value = finite(candidate);
    if (value !== null && value >= 0 && value <= 1) return clamp01(value);
  }
  return null;
};

const frameSpeedKmh = (frame: TelemetryFrame): number | null => {
  const direct = finite(frame.speedKmh);
  if (direct !== null) return direct;
  const speed = finite(frame.speed);
  return speed !== null ? speed * 3.6 : null;
};

const framePosition = (frame: TelemetryFrame): [number, number, number] | null => {
  if (Array.isArray(frame.projectedWorldPosition) && frame.projectedWorldPosition.length >= 3) {
    const x = finite(frame.projectedWorldPosition[0]);
    const y = finite(frame.projectedWorldPosition[1]);
    const z = finite(frame.projectedWorldPosition[2]);
    if (x !== null && y !== null && z !== null) return [x, y, z];
  }

  const x = finite(frame.world_x ?? frame.x);
  const y = finite(frame.world_y ?? 0);
  const z = finite(frame.world_z ?? frame.z ?? frame.y);
  return x !== null && y !== null && z !== null ? [x, y, z] : null;
};

const playerSamples = (samples: TelemetryFrame[]): AnalysisSample[] => (
  samples.map((sample) => ({
    progress: frameProgress(sample),
    speedKmh: frameSpeedKmh(sample),
    position: framePosition(sample),
    throttle: finite(sample.throttle),
    brake: finite(sample.brake),
  }))
);

const opponentSamples = (samples: OpponentCarState[]): AnalysisSample[] => (
  samples
    .filter((sample) => sample.carId !== 0 && sample.isPlayer !== true)
    .map((sample) => {
      const x = finite(sample.worldPosition?.x);
      const y = finite(sample.worldPosition?.y ?? 0);
      const z = finite(sample.worldPosition?.z);
      return {
        progress: finite(sample.splinePosition),
        speedKmh: finite(sample.speedKmh),
        position: x !== null && y !== null && z !== null ? [x, y, z] as [number, number, number] : null,
        throttle: null,
        brake: null,
      };
    })
);

const buildMicroSectors = (count: number) => {
  const safeCount = Math.max(1, Math.min(200, Math.floor(count || 50)));
  return Array.from({ length: safeCount }, (_, index) => {
    const splineStart = index / safeCount;
    const splineEnd = (index + 1) / safeCount;
    const midpoint = (splineStart + splineEnd) / 2;
    const sector = (midpoint < 1 / 3 ? 1 : midpoint < 2 / 3 ? 2 : 3) as 1 | 2 | 3;
    return { segmentIndex: index, splineStart, splineEnd, sector };
  });
};

const inSegment = (sample: AnalysisSample, start: number, end: number, index: number, count: number) => (
  sample.progress !== null && (index === count - 1
    ? sample.progress >= start && sample.progress <= end
    : sample.progress >= start && sample.progress < end)
);

const speedStats = (samples: AnalysisSample[]): SpeedStats => {
  const speeds = samples.map((sample) => sample.speedKmh).filter((value): value is number => value !== null);
  if (!speeds.length) return { avgSpeedKmh: null, minSpeedKmh: null, maxSpeedKmh: null };
  return {
    avgSpeedKmh: speeds.reduce((sum, value) => sum + value, 0) / speeds.length,
    minSpeedKmh: Math.min(...speeds),
    maxSpeedKmh: Math.max(...speeds),
  };
};

const pointDistance = (a: [number, number, number], b: [number, number, number]) => (
  Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2])
);

const pathDistance = (samples: AnalysisSample[]): number | null => {
  const points = samples
    .filter((sample): sample is AnalysisSample & { progress: number; position: [number, number, number] } => (
      sample.progress !== null && sample.position !== null
    ))
    .sort((a, b) => a.progress - b.progress);
  if (points.length < 2) return null;
  const distance = points.slice(1).reduce((sum, point, index) => (
    sum + pointDistance(points[index].position, point.position)
  ), 0);
  return distance > 0 ? distance : null;
};

const estimateDistance = (groups: AnalysisSample[][], start: number, end: number): number | null => {
  for (const group of groups) {
    const distance = pathDistance(group);
    if (distance !== null && distance >= 1) return distance;
  }
  return null;
};

const estimateTime = (avgSpeedKmh: number | null, distanceMeters: number | null): number | null => {
  if (avgSpeedKmh === null || avgSpeedKmh <= 1 || distanceMeters === null || distanceMeters <= 0) return null;
  return distanceMeters / (avgSpeedKmh / 3.6);
};

const smooth = (values: number[]) => values.map((_, index) => {
  const start = Math.max(0, index - 1);
  const end = Math.min(values.length, index + 2);
  const chunk = values.slice(start, end);
  return chunk.reduce((sum, value) => sum + value, 0) / chunk.length;
});

const trend = (samples: AnalysisSample[]) => {
  const points = samples
    .filter((sample): sample is AnalysisSample & { progress: number; speedKmh: number } => (
      sample.progress !== null && sample.speedKmh !== null
    ))
    .sort((a, b) => a.progress - b.progress);
  if (points.length < 3) return { phase: 'UNKNOWN', startSpline: null as number | null };

  const speeds = smooth(points.map((sample) => sample.speedKmh));
  const deltas = speeds.slice(1).map((value, index) => value - speeds[index]);
  const totalDelta = speeds[speeds.length - 1] - speeds[0];
  const drops = deltas.map((delta, index) => ({ delta, index })).filter((item) => item.delta <= -0.8);
  const gains = deltas.map((delta, index) => ({ delta, index })).filter((item) => item.delta >= 0.8);
  const denominator = Math.max(1, deltas.length);
  if (totalDelta <= -2 && drops.length / denominator >= 0.45) {
    return { phase: 'BRAKING', startSpline: points[drops[0]?.index ?? 0].progress };
  }
  if (totalDelta >= 2 && gains.length / denominator >= 0.45) {
    return { phase: 'ACCELERATION', startSpline: points[gains[0]?.index ?? 0].progress };
  }
  return { phase: 'NEUTRAL', startSpline: points[0].progress };
};

const brakingZone = (samples: AnalysisSample[]) => {
  const direct = samples
    .filter((sample): sample is AnalysisSample & { progress: number; brake: number } => (
      sample.progress !== null && sample.brake !== null && sample.brake > 0.05
    ))
    .sort((a, b) => a.progress - b.progress);
  if (direct.length >= 2) return { detected: true, startSpline: direct[0].progress };
  const result = trend(samples);
  return { detected: result.phase === 'BRAKING', startSpline: result.phase === 'BRAKING' ? result.startSpline : null };
};

const accelerationZone = (samples: AnalysisSample[]) => {
  const result = trend(samples);
  if (result.phase === 'ACCELERATION') return { detected: true, startSpline: result.startSpline };
  return { detected: false, startSpline: null as number | null };
};

const trajectoryDeviation = (samples: AnalysisSample[], reference: AnalysisSample[]): number | null => {
  const points = samples.filter((sample): sample is AnalysisSample & { progress: number; position: [number, number, number] } => (
    sample.progress !== null && sample.position !== null
  ));
  const refs = reference.filter((sample): sample is AnalysisSample & { progress: number; position: [number, number, number] } => (
    sample.progress !== null && sample.position !== null
  ));
  if (!points.length || !refs.length) return null;
  const distances = points.map((sample) => {
    const nearest = refs.reduce((best, ref) => (
      Math.abs(ref.progress - sample.progress) < Math.abs(best.progress - sample.progress) ? ref : best
    ), refs[0]);
    return pointDistance(sample.position, nearest.position);
  });
  return distances.reduce((sum, value) => sum + value, 0) / distances.length;
};

const delta = (left: number | null, right: number | null) => (
  left === null || right === null ? null : left - right
);

const classifyLoss = (
  deltaSeconds: number | null,
  speedDeltaKmh: number | null,
  trajectoryMeters: number | null,
  playerBrake: ReturnType<typeof brakingZone>,
  referenceBrake: ReturnType<typeof brakingZone>,
  playerAccel: ReturnType<typeof accelerationZone>,
  referenceAccel: ReturnType<typeof accelerationZone>,
): LossReason => {
  if (deltaSeconds === null) return null;
  if (deltaSeconds <= 0.03) return 'UNKNOWN';
  if (
    playerBrake.startSpline !== null &&
    referenceBrake.startSpline !== null &&
    playerBrake.startSpline + 0.004 < referenceBrake.startSpline
  ) return 'BRAKING';
  if (
    playerAccel.startSpline !== null &&
    referenceAccel.startSpline !== null &&
    playerAccel.startSpline > referenceAccel.startSpline + 0.004
  ) return 'ACCELERATION';
  if (speedDeltaKmh !== null && speedDeltaKmh < -3) return 'SPEED';
  if (trajectoryMeters !== null && trajectoryMeters >= 5) return 'TRAJECTORY';
  return 'UNKNOWN';
};

const classifyOpponent = (
  deltaToPlayer: number | null,
  speedDelta: number | null,
  trajectoryMeters: number | null,
  opponentBrake: ReturnType<typeof brakingZone>,
  playerBrake: ReturnType<typeof brakingZone>,
  opponentAccel: ReturnType<typeof accelerationZone>,
  playerAccel: ReturnType<typeof accelerationZone>,
) => {
  if (deltaToPlayer === null && speedDelta === null) return 'INSUFFICIENT_DATA';
  if (
    opponentBrake.startSpline !== null &&
    playerBrake.startSpline !== null &&
    opponentBrake.startSpline > playerBrake.startSpline + 0.004
  ) return 'OPPONENT_BRAKES_LATER';
  if (
    opponentAccel.startSpline !== null &&
    playerAccel.startSpline !== null &&
    opponentAccel.startSpline + 0.004 < playerAccel.startSpline
  ) return 'OPPONENT_ACCELERATES_EARLIER';
  if (deltaToPlayer !== null && deltaToPlayer < -0.04) return 'OPPONENT_FASTER';
  if (deltaToPlayer !== null && deltaToPlayer > 0.04) return 'PLAYER_FASTER';
  if (speedDelta !== null && speedDelta > 3) return 'OPPONENT_HIGHER_SPEED';
  if (speedDelta !== null && speedDelta < -3) return 'PLAYER_HIGHER_SPEED';
  if (trajectoryMeters !== null && trajectoryMeters >= 5) return 'TRAJECTORY_DEVIATION';
  return 'SIMILAR';
};

const reasonText = (reason: LossReason) => {
  if (reason === 'BRAKING') return 'frear antes';
  if (reason === 'ACCELERATION') return 'acelerar depois';
  if (reason === 'SPEED') return 'menor velocidade minima';
  if (reason === 'TRAJECTORY') return 'trajetoria diferente';
  return 'dados inconclusivos';
};

export function buildComparisonAnalysisFromStore(options: {
  currentLapSamples: TelemetryFrame[];
  referenceLapSamples: TelemetryFrame[];
  opponentHistoryByCarId: Record<number, OpponentCarState[]>;
  track: string | null;
  microSectorCount: number;
}): ComparisonPayload {
  const microsectors = buildMicroSectors(options.microSectorCount);
  const current = playerSamples(options.currentLapSamples);
  const reference = playerSamples(options.referenceLapSamples);
  const opponents = Object.fromEntries(
    Object.entries(options.opponentHistoryByCarId)
      .filter(([carId]) => Number(carId) !== 0)
      .map(([carId, history]) => [Number(carId), opponentSamples(history)]),
  ) as Record<number, AnalysisSample[]>;
  const rejectionReasons: Record<string, number> = {};
  const opponentTotals = new Map<number, { delta: number; validSegments: number }>();
  let validMicroSectors = 0;

  const segments = microsectors.map((segment): ComparisonSegment => {
    const playerSegment = current.filter((sample) => inSegment(sample, segment.splineStart, segment.splineEnd, segment.segmentIndex, microsectors.length));
    const referenceSegment = reference.filter((sample) => inSegment(sample, segment.splineStart, segment.splineEnd, segment.segmentIndex, microsectors.length));
    const opponentSegments = Object.fromEntries(
      Object.entries(opponents).map(([carId, samples]) => [
        Number(carId),
        samples.filter((sample) => inSegment(sample, segment.splineStart, segment.splineEnd, segment.segmentIndex, microsectors.length)),
      ]),
    ) as Record<number, AnalysisSample[]>;

    if (!playerSegment.length) rejectionReasons.missing_player_samples = (rejectionReasons.missing_player_samples || 0) + 1;
    if (!referenceSegment.length) rejectionReasons.missing_reference_samples = (rejectionReasons.missing_reference_samples || 0) + 1;
    if (Object.keys(opponents).length && !Object.values(opponentSegments).some((samples) => samples.length)) {
      rejectionReasons.missing_opponent_samples = (rejectionReasons.missing_opponent_samples || 0) + 1;
    }

    const player = speedStats(playerSegment);
    const referenceStats = speedStats(referenceSegment);
    const distance = estimateDistance([playerSegment, referenceSegment, ...Object.values(opponentSegments)], segment.splineStart, segment.splineEnd);
    const playerTime = estimateTime(player.avgSpeedKmh, distance);
    const referenceTime = estimateTime(referenceStats.avgSpeedKmh, distance);
    const playerBrake = brakingZone(playerSegment);
    const referenceBrake = brakingZone(referenceSegment);
    const playerAccel = accelerationZone(playerSegment);
    const referenceAccel = accelerationZone(referenceSegment);
    const speedDelta = delta(player.avgSpeedKmh, referenceStats.avgSpeedKmh);
    const deltaSeconds = delta(playerTime, referenceTime);
    const trajectoryMeters = trajectoryDeviation(playerSegment, referenceSegment);
    const mainLossReason = classifyLoss(deltaSeconds, speedDelta, trajectoryMeters, playerBrake, referenceBrake, playerAccel, referenceAccel);

    const opponentPayloads = Object.entries(opponentSegments).map(([carIdText, samples]) => {
      const carId = Number(carIdText);
      const stats = speedStats(samples);
      const opponentTime = estimateTime(stats.avgSpeedKmh, distance);
      const deltaToPlayerSeconds = delta(opponentTime, playerTime);
      const deltaToReferenceSeconds = delta(opponentTime, referenceTime);
      const opponentBrake = brakingZone(samples);
      const opponentAccel = accelerationZone(samples);
      const trajectoryToPlayer = trajectoryDeviation(samples, playerSegment);
      const speedDeltaToPlayer = delta(stats.avgSpeedKmh, player.avgSpeedKmh);
      if (deltaToPlayerSeconds !== null) {
        const previous = opponentTotals.get(carId) || { delta: 0, validSegments: 0 };
        opponentTotals.set(carId, { delta: previous.delta + deltaToPlayerSeconds, validSegments: previous.validSegments + 1 });
      }
      const brakingEarlierThanPlayer = (
        opponentBrake.startSpline !== null && playerBrake.startSpline !== null
          ? opponentBrake.startSpline + 0.004 < playerBrake.startSpline
          : null
      );
      const acceleratingEarlierThanPlayer = (
        opponentAccel.startSpline !== null && playerAccel.startSpline !== null
          ? opponentAccel.startSpline + 0.004 < playerAccel.startSpline
          : null
      );
      return {
        carId,
        avgSpeedKmh: roundOrNull(stats.avgSpeedKmh, 3),
        minSpeedKmh: roundOrNull(stats.minSpeedKmh, 3),
        maxSpeedKmh: roundOrNull(stats.maxSpeedKmh, 3),
        deltaToPlayerSeconds: roundOrNull(deltaToPlayerSeconds),
        deltaToReferenceSeconds: roundOrNull(deltaToReferenceSeconds),
        trajectoryDeviationMeters: roundOrNull(trajectoryToPlayer, 3),
        brakingEarlierThanPlayer,
        acceleratingEarlierThanPlayer,
        classification: classifyOpponent(deltaToPlayerSeconds, speedDeltaToPlayer, trajectoryToPlayer, opponentBrake, playerBrake, opponentAccel, playerAccel),
      };
    }).sort((a, b) => a.carId - b.carId);

    if (player.avgSpeedKmh !== null && (referenceStats.avgSpeedKmh !== null || opponentPayloads.some((opponent) => opponent.avgSpeedKmh !== null))) {
      validMicroSectors += 1;
    }

    return {
      ...segment,
      player: {
        avgSpeedKmh: roundOrNull(player.avgSpeedKmh, 3),
        minSpeedKmh: roundOrNull(player.minSpeedKmh, 3),
        maxSpeedKmh: roundOrNull(player.maxSpeedKmh, 3),
      },
      reference: {
        avgSpeedKmh: roundOrNull(referenceStats.avgSpeedKmh, 3),
        minSpeedKmh: roundOrNull(referenceStats.minSpeedKmh, 3),
        maxSpeedKmh: roundOrNull(referenceStats.maxSpeedKmh, 3),
      },
      opponents: opponentPayloads,
      playerVsReference: {
        deltaSeconds: roundOrNull(deltaSeconds),
        speedDeltaKmh: roundOrNull(speedDelta, 3),
        trajectoryDeviationMeters: roundOrNull(trajectoryMeters, 3),
        mainLossReason,
      },
    };
  });

  const sectors = ([1, 2, 3] as const).map((sector) => {
    const sectorSegments = segments.filter((segment) => segment.sector === sector);
    const deltas = sectorSegments.map((segment) => segment.playerVsReference.deltaSeconds).filter((value): value is number => value !== null);
    const reasonCounts = new Map<string, number>();
    sectorSegments.forEach((segment) => {
      const reason = segment.playerVsReference.mainLossReason;
      if (reason && segment.playerVsReference.deltaSeconds !== null && segment.playerVsReference.deltaSeconds > 0.03) {
        reasonCounts.set(reason, (reasonCounts.get(reason) || 0) + 1);
      }
    });
    const opponentSectorTotals = new Map<number, number>();
    sectorSegments.forEach((segment) => {
      segment.opponents.forEach((opponent) => {
        if (opponent.deltaToPlayerSeconds === null) return;
        opponentSectorTotals.set(opponent.carId, (opponentSectorTotals.get(opponent.carId) || 0) + opponent.deltaToPlayerSeconds);
      });
    });
    const worst = sectorSegments
      .filter((segment) => segment.playerVsReference.deltaSeconds !== null)
      .sort((a, b) => (b.playerVsReference.deltaSeconds || 0) - (a.playerVsReference.deltaSeconds || 0))[0];
    const bestOpponent = Array.from(opponentSectorTotals.entries()).sort((a, b) => a[1] - b[1])[0]?.[0] ?? null;
    const mainLossReason = Array.from(reasonCounts.entries()).sort((a, b) => b[1] - a[1])[0]?.[0] ?? null;
    return {
      sector,
      playerVsReferenceDeltaSeconds: deltas.length ? roundOrNull(deltas.reduce((sum, value) => sum + value, 0)) : null,
      mainLossReason,
      bestOpponentCarId: bestOpponent,
      worstSegmentIndex: worst?.segmentIndex ?? null,
    };
  });

  const biggestLosses = segments
    .filter((segment) => segment.playerVsReference.deltaSeconds !== null && segment.playerVsReference.deltaSeconds > 0.03)
    .sort((a, b) => (b.playerVsReference.deltaSeconds || 0) - (a.playerVsReference.deltaSeconds || 0))
    .slice(0, 5)
    .map((segment) => ({
      segmentIndex: segment.segmentIndex,
      sector: segment.sector,
      splineStart: segment.splineStart,
      splineEnd: segment.splineEnd,
      deltaSeconds: segment.playerVsReference.deltaSeconds,
      reason: segment.playerVsReference.mainLossReason,
      message: `Voce perde aproximadamente ${Math.abs(segment.playerVsReference.deltaSeconds || 0).toFixed(2)}s no setor ${segment.sector} por ${reasonText(segment.playerVsReference.mainLossReason)}.`,
    }));

  const biggestGains = segments
    .filter((segment) => segment.playerVsReference.deltaSeconds !== null && segment.playerVsReference.deltaSeconds < -0.03)
    .sort((a, b) => (a.playerVsReference.deltaSeconds || 0) - (b.playerVsReference.deltaSeconds || 0))
    .slice(0, 5)
    .map((segment) => ({
      segmentIndex: segment.segmentIndex,
      sector: segment.sector,
      splineStart: segment.splineStart,
      splineEnd: segment.splineEnd,
      deltaSeconds: segment.playerVsReference.deltaSeconds,
      reason: segment.playerVsReference.mainLossReason,
      message: `Voce ganha aproximadamente ${Math.abs(segment.playerVsReference.deltaSeconds || 0).toFixed(2)}s no setor ${segment.sector}.`,
    }));

  const opponentRanking = Array.from(opponentTotals.entries())
    .map(([carId, value]) => ({
      carId,
      estimatedAdvantageSeconds: roundOrNull(value.delta),
      validSegments: value.validSegments,
    }))
    .sort((a, b) => (a.estimatedAdvantageSeconds || 0) - (b.estimatedAdvantageSeconds || 0));

  return {
    track: options.track,
    generatedAt: new Date().toISOString(),
    microSectorCount: microsectors.length,
    sectors,
    biggestLosses,
    biggestGains,
    opponentRanking,
    segments,
    debug: {
      playerSamples: current.length,
      referenceSamples: reference.length,
      opponentsAnalyzed: Object.keys(opponents).length,
      validMicroSectors,
      rejectedSegments: Object.values(rejectionReasons).reduce((sum, value) => sum + value, 0),
      rejectionReasons,
      notes: [
        'Opponent braking/acceleration uses speed trend inference when throttle/brake channels are unavailable.',
        'Frontend reference samples come from the existing validated lap store.',
      ],
    },
  };
}
