export type CoachingIssueType =
  | 'BRAKING_TOO_EARLY'
  | 'BRAKING_TOO_LATE'
  | 'ACCELERATING_TOO_LATE'
  | 'LOW_CORNER_SPEED'
  | 'LOW_EXIT_SPEED'
  | 'TRAJECTORY_DEVIATION'
  | 'GOOD_GAIN'
  | 'SECTOR_LOSS'
  | 'INSUFFICIENT_DATA'
  | 'UNKNOWN';

export type CoachingSeverity = 'INFO' | 'LOW' | 'MEDIUM' | 'HIGH';
export type CoachingConfidence = 'HIGH' | 'MEDIUM' | 'LOW' | 'INSUFFICIENT_DATA';

export interface CoachingInsight {
  id: string;
  type: CoachingIssueType;
  severity: CoachingSeverity;
  confidence: CoachingConfidence;
  sector: 1 | 2 | 3 | null;
  segmentIndex: number | null;
  splineStart: number | null;
  splineEnd: number | null;
  estimatedDeltaSeconds: number | null;
  speedDeltaKmh: number | null;
  trajectoryDeviationMeters: number | null;
  title: string;
  message: string;
  evidence: string[];
  recommendation: string;
  source: 'RACING_LINE_REFERENCE' | 'CURRENT_LAP' | 'UNKNOWN';
}

export interface CoachingReport {
  status: 'READY' | 'INSUFFICIENT_DATA';
  track: string | null;
  generatedAt: string;
  referenceLapNumber: number | null;
  currentLapNumber: number | null;
  microSectorCount: number;
  summary: {
    mainIssue: CoachingIssueType | null;
    worstSector: 1 | 2 | 3 | null;
    estimatedTotalLossSeconds: number | null;
    totalInsights: number;
    highSeverityCount: number;
  };
  topInsights: CoachingInsight[];
  sectorInsights: Array<{
    sector: 1 | 2 | 3;
    estimatedDeltaSeconds: number | null;
    mainIssue: CoachingIssueType | null;
    message: string;
  }>;
  debug: {
    racingLineStatus: string;
    comparisonSegments: number;
    validSegments: number;
    rejectedSegments: number;
    insufficientDataSegments: number;
    generatedInsights: number;
    performanceMode?: string;
    reason?: string | null;
  };
}
