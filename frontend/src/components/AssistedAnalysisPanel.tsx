import React, { useEffect, useMemo, useState } from 'react';
import { Activity, AlertTriangle, RefreshCw, Target, Zap } from 'lucide-react';
import { api } from '../api/client';
import { AssistedTraceContext, useTelemetryStore } from '../store/useTelemetryStore';

type LapItem = {
  lapId: string;
  source: string;
  driverId: string;
  lapNumber: number;
  track?: string | null;
  lapTime?: number | null;
  sampleCount: number;
  sessionId?: string | null;
};

const INACTIVE_ASSISTED_CONTEXT: AssistedTraceContext = {
  analyzedLapId: null,
  analyzedLapNumber: null,
  referenceLapId: null,
  referenceLapNumber: null,
  track: null,
  headline: null,
};

const phaseLabel: Record<string, string> = {
  entry: 'Entry',
  braking_zone: 'Braking',
  apex: 'Apex',
  exit: 'Exit',
  straight_after: 'Straight',
};

const fmtSec = (value: unknown, digits = 3) => {
  const n = Number(value);
  return Number.isFinite(n) ? `${n.toFixed(digits)}s` : '--';
};

const fmtLap = (lap: LapItem) => {
  const source = lap.source === 'buffer' ? 'LIVE' : lap.source === 'telemetry_db' ? 'DB' : 'REC';
  const time = Number.isFinite(Number(lap.lapTime)) && Number(lap.lapTime) > 0
    ? ` ${Number(lap.lapTime).toFixed(1)}s`
    : '';
  return `${source} L${lap.lapNumber}${time} (${lap.sampleCount})`;
};

const compactValue = (value: unknown) => {
  if (value === null || value === undefined || value === '') return '--';
  const text = String(value).replace(/^rec__/, '');
  return text.length > 28 ? `...${text.slice(-25)}` : text;
};

const fmtEvidence = (evidence: any) => {
  if (!evidence || typeof evidence !== 'object') return '';
  return Object.entries(evidence)
    .slice(0, 4)
    .map(([key, value]) => {
      const n = Number(value);
      const formatted = Number.isFinite(n) ? n.toFixed(Math.abs(n) >= 10 ? 1 : 3) : String(value);
      return `${key}: ${formatted}`;
    })
    .join(' | ');
};

const fmtRefLabel = (metadata: any) => {
  if (!metadata) return '--';
  return [metadata.source, metadata.year, metadata.event, metadata.session, metadata.driver]
    .filter(Boolean)
    .join(' / ');
};

const severityColor = (severity: number) => {
  if (severity > 0.72) return '#fb7185';
  if (severity > 0.38) return '#fbbf24';
  return '#22d3ee';
};

const TinyButton = ({ children, onClick, disabled, title }: any) => (
  <button
    title={title}
    onClick={onClick}
    disabled={disabled}
    className="num"
    style={{
      height: 26,
      display: 'inline-flex',
      alignItems: 'center',
      justifyContent: 'center',
      gap: 6,
      padding: '0 8px',
      borderRadius: 3,
      border: '1px solid rgba(34,211,238,0.22)',
      background: disabled ? 'rgba(255,255,255,0.025)' : 'rgba(34,211,238,0.07)',
      color: disabled ? '#475569' : '#67e8f9',
      cursor: disabled ? 'default' : 'pointer',
      fontSize: 8,
      fontWeight: 800,
      textTransform: 'uppercase',
      minWidth: 0,
    }}
  >
    {children}
  </button>
);

export const AssistedAnalysisPanel: React.FC<{ active?: boolean }> = ({ active = true }) => {
  const lastCompletedLapNumber = useTelemetryStore(s => active ? s.lapDebug.lastCompletedLapNumber : null);
  const assistedTraceContext = useTelemetryStore(s => active ? s.assistedTraceContext : INACTIVE_ASSISTED_CONTEXT);
  const setAssistedTraceContext = useTelemetryStore(s => s.setAssistedTraceContext);
  const clearAssistedTraceContext = useTelemetryStore(s => s.clearAssistedTraceContext);
  const [laps, setLaps] = useState<LapItem[]>([]);
  const [lapId, setLapId] = useState('');
  const [referenceLapId, setReferenceLapId] = useState('');
  const [analysis, setAnalysis] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedLap = useMemo(() => laps.find(lap => lap.lapId === lapId) || null, [laps, lapId]);
  const referenceOptions = useMemo(() => laps.filter(lap => lap.lapId !== lapId && lap.sampleCount >= 40), [laps, lapId]);

  const publishAnalysisContext = (nextAnalysis: any) => {
    if (!nextAnalysis?.lapId) {
      clearAssistedTraceContext();
      return;
    }

    const lapNumber = Number(nextAnalysis.lapNumber);
    const referenceLapNumber = Number(nextAnalysis.reference?.lapNumber);
    setAssistedTraceContext({
      analyzedLapId: nextAnalysis.lapId,
      analyzedLapNumber: Number.isFinite(lapNumber) ? lapNumber : null,
      referenceLapId: nextAnalysis.reference?.lapId || null,
      referenceLapNumber: Number.isFinite(referenceLapNumber) ? referenceLapNumber : null,
      track: nextAnalysis.track || null,
      headline: nextAnalysis.summary?.headline || null,
    });
  };

  const loadLaps = async () => {
    try {
      const payload = await api.listAssistedAnalysisLaps();
      const next = Array.isArray(payload.laps) ? payload.laps : [];
      setLaps(next);
      const preferredLapId = assistedTraceContext.analyzedLapId
        && next.some((lap: LapItem) => lap.lapId === assistedTraceContext.analyzedLapId)
        ? assistedTraceContext.analyzedLapId
        : null;
      setLapId(current => preferredLapId || current || next.find((lap: LapItem) => lap.sampleCount >= 40)?.lapId || next[0]?.lapId || '');
    } catch (exc: any) {
      setError(exc?.response?.data?.detail || 'Lap list unavailable');
    }
  };

  const loadCached = async (targetLapId = lapId, refLapId = referenceLapId) => {
    if (!targetLapId) {
      clearAssistedTraceContext();
      return;
    }
    try {
      const payload = await api.getAssistedAnalysis(targetLapId, refLapId || null, {
        includeExternalReference: true,
      });
      setAnalysis(payload.analysis);
      publishAnalysisContext(payload.analysis);
      setError(null);
    } catch {
      if (refLapId) {
        try {
          const payload = await api.getAssistedAnalysis(targetLapId, null, {
            includeExternalReference: true,
          });
          if (payload.analysis?.reference?.lapId === refLapId) {
            setAnalysis(payload.analysis);
            publishAnalysisContext(payload.analysis);
            setError(null);
            return;
          }
        } catch {
          // The requested lap has no cached automatic-reference analysis either.
        }
      }
      setAnalysis(null);
    }
  };

  const runAnalysis = async (force = false) => {
    if (!lapId) return;
    setLoading(true);
    setError(null);
    try {
      const payload = await api.requestAssistedAnalysis(lapId, {
        referenceLapId: referenceLapId || null,
        includeExternalReference: true,
        force,
      });
      setAnalysis(payload.analysis);
      publishAnalysisContext(payload.analysis);
      await loadLaps();
    } catch (exc: any) {
      setError(exc?.response?.data?.detail || 'Analysis failed');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!active) return undefined;
    loadLaps();
    return undefined;
  }, [lastCompletedLapNumber, active, assistedTraceContext.analyzedLapId]);

  useEffect(() => {
    if (!active || !assistedTraceContext.analyzedLapId) return;
    setLapId(assistedTraceContext.analyzedLapId);
    setReferenceLapId(assistedTraceContext.referenceLapId || '');
  }, [active, assistedTraceContext.analyzedLapId, assistedTraceContext.referenceLapId]);

  useEffect(() => {
    if (!active) return;
    setAnalysis(null);
    loadCached();
  }, [lapId, referenceLapId, active]);

  const summary = analysis?.summary;
  const topLosses = Array.isArray(analysis?.topLosses) ? analysis.topLosses : [];
  const corners = Array.isArray(analysis?.corners) ? analysis.corners : [];
  const externalReference = analysis?.externalReference?.available ? analysis.externalReference : null;
  const externalMetadata = externalReference?.metadata;

  return (
    <div className="panel flex flex-col h-full overflow-hidden">
      <div className="flex items-center justify-between px-3 py-2 shrink-0"
        style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
        <div className="flex items-center gap-2">
          <div style={{ width: 3, height: 16, background: '#a78bfa', borderRadius: 2 }} />
          <span className="num text-[8px] font-bold text-slate-300 uppercase tracking-widest">Assisted Analysis</span>
        </div>
        <Activity size={13} color="#a78bfa" />
      </div>

      <div className="px-2 py-2 flex flex-col gap-2 shrink-0" style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
        <select
          className="num"
          value={lapId}
          onChange={event => setLapId(event.target.value)}
          style={{
            height: 26,
            width: '100%',
            borderRadius: 3,
            border: '1px solid rgba(255,255,255,0.08)',
            background: '#080812',
            color: '#cbd5e1',
            padding: '0 8px',
            fontSize: 8,
          }}
        >
          {laps.length === 0 && <option value="">No persisted laps</option>}
          {laps.map(lap => <option key={lap.lapId} value={lap.lapId}>{fmtLap(lap)}</option>)}
        </select>

        <select
          className="num"
          value={referenceLapId}
          onChange={event => setReferenceLapId(event.target.value)}
          style={{
            height: 26,
            width: '100%',
            borderRadius: 3,
            border: '1px solid rgba(255,255,255,0.08)',
            background: '#080812',
            color: '#94a3b8',
            padding: '0 8px',
            fontSize: 8,
          }}
        >
          <option value="">Best reference</option>
          {referenceOptions.map(lap => <option key={lap.lapId} value={lap.lapId}>{fmtLap(lap)}</option>)}
        </select>

        <div className="flex gap-1">
          <TinyButton title="Generate assisted analysis" onClick={() => runAnalysis(false)} disabled={!lapId || loading}>
            <Target size={12} /> Analyze
          </TinyButton>
          <TinyButton title="Recompute assisted analysis" onClick={() => runAnalysis(true)} disabled={!lapId || loading}>
            <RefreshCw size={12} /> Force
          </TinyButton>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-2 py-2 flex flex-col gap-2">
        {error && (
          <div className="flex gap-2 items-start px-2 py-2 rounded-sm"
            style={{ background: 'rgba(251,113,133,0.08)', border: '1px solid rgba(251,113,133,0.18)' }}>
            <AlertTriangle size={13} color="#fb7185" />
            <span className="text-[9px] text-rose-200 leading-relaxed">{error}</span>
          </div>
        )}

        {!analysis && !error && (
          <div className="flex-1 flex flex-col items-center justify-center gap-2 opacity-35">
            <Target size={28} color="#64748b" />
            <span className="num text-[8px] text-slate-600 uppercase tracking-wider text-center leading-relaxed">
              Post-lap diagnosis<br />not generated
            </span>
          </div>
        )}

        {analysis && (
          <>
            <div className="rounded-sm px-2 py-2"
              style={{ background: 'rgba(167,139,250,0.06)', border: '1px solid rgba(167,139,250,0.16)' }}>
              <div className="flex items-center justify-between mb-1">
                <span className="label" style={{ fontSize: 6 }}>Summary</span>
                <span className="num text-[8px] text-violet-300">{fmtSec(summary?.totalEstimatedGainS)}</span>
              </div>
              <p className="text-[9px] text-slate-300 leading-relaxed font-sans">{summary?.headline}</p>
              <div className="mt-2 grid grid-cols-2 gap-1">
                <div>
                  <span className="num text-[6px] text-slate-600 uppercase block">Status</span>
                  <span className="num text-[7px] text-slate-300">{analysis.status || 'ANALYZED'}</span>
                </div>
                <div>
                  <span className="num text-[6px] text-slate-600 uppercase block">Reference</span>
                  <span className="num text-[7px] text-slate-300">{analysis.reference?.lapNumber ? `L${analysis.reference.lapNumber}` : compactValue(analysis.reference?.lapId)}</span>
                </div>
                <div>
                  <span className="num text-[6px] text-slate-600 uppercase block">Lap</span>
                  <span className="num text-[7px] text-slate-300">{analysis.lapNumber ? `L${analysis.lapNumber}` : compactValue(analysis.lapId)}</span>
                </div>
                <div>
                  <span className="num text-[6px] text-slate-600 uppercase block">Corners</span>
                  <span className="num text-[7px] text-slate-300">{summary?.cornerCount ?? corners.length}</span>
                </div>
              </div>
              <div className="mt-2 flex items-center justify-between">
                <span className="num text-[7px] text-slate-600 uppercase">Confidence</span>
                <span className="num text-[8px] text-slate-300">{Math.round((summary?.confidence ?? 0) * 100)}%</span>
              </div>
            </div>

            {externalReference && (
              <details className="rounded-sm px-2 py-2"
                style={{ background: 'rgba(34,211,238,0.035)', border: '1px solid rgba(34,211,238,0.12)' }}>
                <summary className="num text-[7px] text-cyan-300 uppercase cursor-pointer">
                  External Reference
                </summary>
                <div className="mt-1 grid grid-cols-2 gap-1">
                  <div>
                    <span className="num text-[6px] text-slate-600 uppercase block">Source</span>
                    <span className="num text-[7px] text-slate-300">{fmtRefLabel(externalMetadata)}</span>
                  </div>
                  <div>
                    <span className="num text-[6px] text-slate-600 uppercase block">Type</span>
                    <span className="num text-[7px] text-slate-300">{externalMetadata?.referenceType || '--'}</span>
                  </div>
                  <div>
                    <span className="num text-[6px] text-slate-600 uppercase block">Calibration</span>
                    <span className="num text-[7px] text-slate-300">{externalMetadata?.calibrationStatus || '--'}</span>
                  </div>
                  <div>
                    <span className="num text-[6px] text-slate-600 uppercase block">Comparable</span>
                    <span className="num text-[7px] text-slate-300">{externalMetadata?.comparableToAssetto || '--'}</span>
                  </div>
                </div>
                <p className="mt-1 text-[8px] text-slate-500 leading-snug font-sans">{externalReference.comparabilityNotice}</p>
                {Array.isArray(externalReference.macroCornerContext) && externalReference.macroCornerContext.length > 0 && (
                  <div className="mt-1 flex flex-col gap-1">
                    {externalReference.macroCornerContext.slice(0, 3).map((item: any) => (
                      <div key={`external-${item.cornerId}`} className="num text-[7px] text-slate-500 leading-snug">
                        <span className="text-cyan-400">{item.name}</span> {item.summary}
                      </div>
                    ))}
                  </div>
                )}
              </details>
            )}

            {topLosses.length > 0 && (
              <div>
                <span className="label block mb-1" style={{ fontSize: 6 }}>Main Losses</span>
                <div className="flex flex-col gap-1">
                  {topLosses.map((loss: any) => (
                    <div key={`${loss.cornerId}-${loss.phase}`} className="px-2 py-1.5 rounded-sm"
                      style={{ background: 'rgba(255,255,255,0.025)', border: '1px solid rgba(255,255,255,0.05)' }}>
                      <div className="flex items-center justify-between gap-2">
                        <span className="num text-[8px] font-bold text-slate-300">{loss.name}</span>
                        <span className="num text-[8px] text-amber-300">{fmtSec(loss.estimatedGainS ?? loss.lossS)}</span>
                      </div>
                      <div className="num text-[7px] text-slate-600 uppercase mt-1">{phaseLabel[loss.phase] || loss.phase || 'Trace'}</div>
                      {loss.concept && (
                        <div className="num text-[7px] text-violet-300 mt-1">{loss.concept}</div>
                      )}
                      <p className="text-[8px] text-slate-400 leading-snug mt-1 font-sans">{loss.primaryError || 'Time loss'}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div>
              <span className="label block mb-1" style={{ fontSize: 6 }}>Corner Diagnostics</span>
              <div className="flex flex-col gap-1.5">
                {corners.map((corner: any) => {
                  const primary = Array.isArray(corner.errors) ? corner.errors[0] : null;
                  const severity = Number(primary?.severity ?? 0);
                  const evidenceText = fmtEvidence(primary?.evidence || corner.evidenceTelemetry);
                  return (
                    <div key={corner.cornerId} className="rounded-sm px-2 py-2"
                      style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.05)' }}>
                      <div className="flex items-center justify-between gap-2">
                        <div className="flex items-center gap-1.5 min-w-0">
                          <Zap size={11} color={primary ? severityColor(severity) : '#475569'} />
                          <span className="num text-[8px] font-bold text-slate-300 truncate">{corner.name}</span>
                        </div>
                        <span className="num text-[8px] text-cyan-300">{fmtSec(corner.estimatedGainS)}</span>
                      </div>
                      <div className="mt-1 flex items-center gap-1">
                        <div className="h-[3px] flex-1 rounded-full" style={{ background: 'rgba(255,255,255,0.06)' }}>
                          <div className="h-full rounded-full" style={{ width: `${Math.min(1, severity) * 100}%`, background: severityColor(severity) }} />
                        </div>
                        <span className="num text-[7px] text-slate-600">{phaseLabel[primary?.phase] || phaseLabel[corner.primaryPhase] || 'OK'}</span>
                      </div>
                      {corner.technicalConcept && (
                        <div className="mt-1 num text-[7px] text-violet-300">{corner.technicalConcept}</div>
                      )}
                      {corner.physicalBehavior && (
                        <div className="mt-1 text-[8px] text-slate-500 leading-snug font-sans">{corner.physicalBehavior}</div>
                      )}
                      {evidenceText && (
                        <div className="mt-1 px-1.5 py-1 rounded-sm"
                          style={{ background: 'rgba(34,211,238,0.04)', border: '1px solid rgba(34,211,238,0.08)' }}>
                          <span className="num text-[6px] text-cyan-500 uppercase block mb-0.5">Evidence</span>
                          <span className="num text-[7px] text-slate-500 leading-snug">{evidenceText}</span>
                        </div>
                      )}
                      <p className="text-[8.5px] text-slate-400 leading-relaxed mt-1.5 font-sans">{corner.feedback}</p>
                    </div>
                  );
                })}
              </div>
            </div>
          </>
        )}
      </div>

      <div className="px-3 py-1.5 shrink-0 flex items-center justify-between"
        style={{ borderTop: '1px solid rgba(255,255,255,0.04)' }}>
        <span className="num text-[7px] text-slate-700 uppercase tracking-wider">Post-lap only</span>
        <span className="num text-[7px] text-slate-600">{selectedLap?.track || analysis?.track || 'Track pending'}</span>
      </div>
    </div>
  );
};
