import React from 'react';

function formatText(value) {
  return value === undefined || value === null || value === '' ? '--' : String(value);
}

function formatMeters(value) {
  return Number.isFinite(Number(value)) ? `${Number(value).toFixed(1)} m` : '--';
}

function formatSource(value) {
  if (!value) return '--';
  const text = String(value);
  if (text.includes('PitAreaSurface component physical triangles')) return 'PitArea physical surface';
  return text.length > 28 ? `${text.slice(0, 27)}...` : text;
}

function areaClass(area) {
  if (area === 'pit_entry_access') return 'text-emerald-300 border-emerald-400/35 bg-emerald-500/10';
  if (area === 'pit_corridor') return 'text-yellow-200 border-yellow-400/35 bg-yellow-500/10';
  if (area === 'pit_exit_access') return 'text-orange-300 border-orange-400/35 bg-orange-500/10';
  if (area === 'main_track') return 'text-slate-200 border-slate-400/25 bg-slate-500/10';
  return 'text-slate-400 border-slate-500/20 bg-slate-500/5';
}

function ToggleButton({ active, label, onClick }) {
  return (
    <button
      onClick={onClick}
      className={`px-2 py-0.5 num text-[7px] uppercase rounded-sm transition-all ${
        active ? 'bg-yellow-500/15 text-yellow-200 border border-yellow-500/30' : 'text-slate-500 hover:text-slate-300 border border-transparent'
      }`}
    >
      {label}
    </button>
  );
}

export function PitLaneDebugPanel({
  state,
  options,
  onToggle,
  classification,
  recording = false,
  recordedCount = 0,
  exportStatus = '',
  onToggleRecording,
  onExportRecording,
}) {
  const data = state?.data;
  const pitArea = data?.pitAreaGeometry || {};
  const corridor = data?.pitLaneCorridorV2 || data?.pitlaneV2 || {};
  const entryAccessGeometry = data?.pitEntryAccessGeometryV2 || pitArea.entryAccessGeometryV2 || data?.pitEntryAccess || {};
  const exitAccessGeometry = data?.pitExitAccessGeometryV2 || pitArea.exitAccessGeometryV2 || data?.pitExitAccess || {};
  const finalReport = pitArea.finalReport || {};
  const activeVersion = data?.activePitlaneDebugVersion || 'PitAreaGeometry';
  const corridorDetected = pitArea.corridorDetected ?? finalReport.pitAreaIncludesCorridor ?? Boolean(corridor.geometry?.pointCount);
  const entryAccessDetected = pitArea.entryAccessDetected ?? finalReport.pitAreaIncludesEntryAccess ?? Boolean(entryAccessGeometry.pointCount || entryAccessGeometry.triangleCount);
  const exitAccessDetected = pitArea.exitAccessDetected ?? finalReport.pitAreaIncludesExitAccess ?? Boolean(exitAccessGeometry.pointCount || exitAccessGeometry.triangleCount);
  const entryAccessGeometryBuilt = Boolean(entryAccessGeometry.geometryBuilt ?? entryAccessGeometry.triangleCount);
  const exitAccessGeometryBuilt = Boolean(exitAccessGeometry.geometryBuilt ?? exitAccessGeometry.triangleCount);
  const entryAccessHasSurface = Boolean(entryAccessGeometry.hasSurface ?? entryAccessGeometry.surfaceFootprint?.triangleCount);
  const exitAccessHasSurface = Boolean(exitAccessGeometry.hasSurface ?? exitAccessGeometry.surfaceFootprint?.triangleCount);
  const pitLaneAiUsedAsReferenceOnly = Boolean(
    (entryAccessGeometry.pitLaneAiUsedAsReferenceOnly ?? true)
      && (exitAccessGeometry.pitLaneAiUsedAsReferenceOnly ?? true),
  );
  const entryConfidence = pitArea.components?.components?.find((component) => component.name === 'PitEntryAccessArea')?.confidence
    || entryAccessGeometry.confidence
    || '--';
  const exitConfidence = pitArea.components?.components?.find((component) => component.name === 'PitExitAccessArea')?.confidence
    || exitAccessGeometry.confidence
    || '--';
  const runtimeChanged = pitArea.runtimeChanged ?? data?.runtimeChanged ?? finalReport.runtimeChanged ?? false;
  const readyForRuntimeIntegration = pitArea.readyForRuntimeIntegration ?? finalReport.readyForRuntimeIntegration ?? false;
  const exitValidation = pitArea.exitAccessValidationReport || {};
  const liveExitValidation = pitArea.exitAccessLiveValidation || {};
  const samplesInsideExitAccess = exitValidation.samplesInsideExitAccess ?? liveExitValidation.samplesInsideExitAccess ?? 0;
  const exitAccessValidated = exitValidation.exitAccessValidated ?? liveExitValidation.exitAccessValidated ?? false;
  const currentArea = classification?.area || 'unknown';
  const currentAreaLabel = classification?.label || 'UNKNOWN';

  return (
    <div className="absolute bottom-3 left-3 panel w-[340px] px-3 py-2 text-[10px] text-slate-300">
      <div className="flex items-center justify-between gap-2 mb-2">
        <div>
          <div className="text-cyan-300 font-semibold uppercase tracking-[0.18em] text-[9px]">PitLane Debug</div>
          <div className="text-slate-500 text-[9px]">PitAreaGeometry evaluation, runtime unchanged</div>
        </div>
        <button
          onClick={state?.reload}
          className="px-2 py-0.5 num text-[7px] uppercase rounded-sm text-cyan-300 border border-cyan-500/25 bg-cyan-500/10"
        >
          Reload
        </button>
      </div>

      <div className="grid grid-cols-3 gap-1 mb-2">
        <ToggleButton active={options.showMainTrack} label="Main" onClick={() => onToggle('showMainTrack')} />
        <ToggleButton active={options.showPitArea} label="Pit Area" onClick={() => onToggle('showPitArea')} />
        <ToggleButton active={options.showPitCorridorV2} label="Corridor" onClick={() => onToggle('showPitCorridorV2')} />
        <ToggleButton active={options.showEntryAccess} label="Entry" onClick={() => onToggle('showEntryAccess')} />
        <ToggleButton active={options.showExitAccess} label="Exit" onClick={() => onToggle('showExitAccess')} />
        <ToggleButton active={options.showAiReferences} label="AI refs" onClick={() => onToggle('showAiReferences')} />
        <ToggleButton active={options.showCarPath} label="Car Path" onClick={() => onToggle('showCarPath')} />
        <ToggleButton active={options.showLabels} label="Labels" onClick={() => onToggle('showLabels')} />
        <ToggleButton active={options.showAdvancedLegacy} label="Legacy" onClick={() => onToggle('showAdvancedLegacy')} />
      </div>

      <div className="grid grid-cols-2 gap-1 mb-2">
        <button
          onClick={onToggleRecording}
          className={`px-2 py-1 num text-[7px] uppercase rounded-sm border transition-all ${
            recording ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30' : 'text-slate-400 border-slate-500/20 hover:text-slate-200'
          }`}
        >
          {recording ? `Recording ${recordedCount}` : 'Record Pit Path'}
        </button>
        <button
          onClick={onExportRecording}
          disabled={!recordedCount}
          className={`px-2 py-1 num text-[7px] uppercase rounded-sm border transition-all ${
            recordedCount ? 'bg-cyan-500/10 text-cyan-300 border-cyan-500/25' : 'text-slate-600 border-slate-700/40'
          }`}
        >
          Export Pit Path
        </button>
      </div>
      {exportStatus && <div className="mb-2 text-[9px] text-slate-400 num">{exportStatus}</div>}

      {state?.loading && <div className="text-amber-200">Carregando PitAreaGeometry...</div>}
      {state?.error && <div className="text-rose-300">Erro: {state.error}</div>}

      {data && (
        <>
          <div className={`mb-2 inline-flex items-center px-2 py-1 rounded-sm border num text-[10px] font-semibold ${areaClass(currentArea)}`}>
            {currentAreaLabel}
          </div>
          <div className="grid grid-cols-[118px_1fr] gap-x-3 gap-y-1 num">
            <span className="text-slate-500">active layer</span>
            <span className="text-yellow-200">{formatText(activeVersion)}</span>
            <span className="text-slate-500">corridor</span>
            <span className={corridorDetected ? 'text-emerald-300' : 'text-rose-300'}>{String(Boolean(corridorDetected))}</span>
            <span className="text-slate-500">entry access</span>
            <span className={entryAccessDetected ? 'text-emerald-300' : 'text-rose-300'}>{String(Boolean(entryAccessDetected))}</span>
            <span className="text-slate-500">exit access</span>
            <span className={exitAccessDetected ? 'text-emerald-300' : 'text-rose-300'}>{String(Boolean(exitAccessDetected))}</span>
            <span className="text-slate-500">entry area built</span>
            <span className={entryAccessGeometryBuilt ? 'text-emerald-300' : 'text-rose-300'}>{String(entryAccessGeometryBuilt)}</span>
            <span className="text-slate-500">exit area built</span>
            <span className={exitAccessGeometryBuilt ? 'text-emerald-300' : 'text-rose-300'}>{String(exitAccessGeometryBuilt)}</span>
            <span className="text-slate-500">entry surface</span>
            <span className={entryAccessHasSurface ? 'text-emerald-300' : 'text-rose-300'}>{String(entryAccessHasSurface)}</span>
            <span className="text-slate-500">exit surface</span>
            <span className={exitAccessHasSurface ? 'text-emerald-300' : 'text-rose-300'}>{String(exitAccessHasSurface)}</span>
            <span className="text-slate-500">entry confidence</span>
            <span>{formatText(entryConfidence)}</span>
            <span className="text-slate-500">exit confidence</span>
            <span>{formatText(exitConfidence)}</span>
            <span className="text-slate-500">entry source</span>
            <span>{formatSource(entryAccessGeometry.source)}</span>
            <span className="text-slate-500">exit source</span>
            <span>{formatSource(exitAccessGeometry.source)}</span>
            <span className="text-slate-500">pit_lane.ai</span>
            <span className={pitLaneAiUsedAsReferenceOnly ? 'text-cyan-300' : 'text-rose-300'}>{pitLaneAiUsedAsReferenceOnly ? 'reference only' : 'geometry source'}</span>
            <span className="text-slate-500">current area</span>
            <span>{formatText(currentArea)}</span>
            <span className="text-slate-500">dist exit</span>
            <span>{formatMeters(classification?.distanceToExitAccess)}</span>
            <span className="text-slate-500">dist pit/main</span>
            <span>{formatMeters(classification?.distanceToPitArea)} / {formatMeters(classification?.distanceToMainTrack)}</span>
            <span className="text-slate-500">exit samples</span>
            <span>{formatText(samplesInsideExitAccess)}</span>
            <span className="text-slate-500">exit validated</span>
            <span className={exitAccessValidated ? 'text-emerald-300' : 'text-slate-400'}>{String(Boolean(exitAccessValidated))}</span>
            <span className="text-slate-500">confidence</span>
            <span>{formatText(classification?.confidence)}</span>
            <span className="text-slate-500">runtime changed</span>
            <span className={runtimeChanged ? 'text-rose-300' : 'text-emerald-300'}>{String(Boolean(runtimeChanged))}</span>
            <span className="text-slate-500">ready runtime</span>
            <span className={readyForRuntimeIntegration ? 'text-rose-300' : 'text-slate-400'}>{String(Boolean(readyForRuntimeIntegration))}</span>
          </div>
        </>
      )}
    </div>
  );
}

export default PitLaneDebugPanel;
