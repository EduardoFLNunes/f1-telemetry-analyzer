import React from 'react';

function formatText(value) {
  return value === undefined || value === null || value === '' ? '--' : String(value);
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

export function PitLaneDebugPanel({ state, options, onToggle }) {
  const data = state?.data;
  const pitArea = data?.pitAreaGeometry || {};
  const corridor = data?.pitLaneCorridorV2 || data?.pitlaneV2 || {};
  const finalReport = pitArea.finalReport || {};
  const activeVersion = data?.activePitlaneDebugVersion || 'PitAreaGeometry';
  const sourceMeshCount = pitArea.sourceMeshCount ?? finalReport.sourceMeshCount;
  const triangleCount = pitArea.triangleCount ?? finalReport.triangleCount;
  const corridorDetected = pitArea.corridorDetected ?? finalReport.pitAreaIncludesCorridor ?? Boolean(corridor.geometry?.pointCount);
  const entryAccessDetected = pitArea.entryAccessDetected ?? finalReport.pitAreaIncludesEntryAccess ?? Boolean(data?.pitEntryAccess?.pointCount);
  const exitAccessDetected = pitArea.exitAccessDetected ?? finalReport.pitAreaIncludesExitAccess ?? Boolean(data?.pitExitAccess?.pointCount);
  const runtimeChanged = pitArea.runtimeChanged ?? data?.runtimeChanged ?? finalReport.runtimeChanged ?? false;
  const readyForRuntimeIntegration = pitArea.readyForRuntimeIntegration ?? finalReport.readyForRuntimeIntegration ?? false;

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
        <ToggleButton active={options.showLabels} label="Labels" onClick={() => onToggle('showLabels')} />
        <ToggleButton active={options.showAdvancedLegacy} label="Legacy" onClick={() => onToggle('showAdvancedLegacy')} />
      </div>

      {state?.loading && <div className="text-amber-200">Carregando PitAreaGeometry...</div>}
      {state?.error && <div className="text-rose-300">Erro: {state.error}</div>}

      {data && (
        <div className="grid grid-cols-[108px_1fr] gap-x-3 gap-y-1 num">
          <span className="text-slate-500">active layer</span>
          <span className="text-yellow-200">{formatText(activeVersion)}</span>
          <span className="text-slate-500">source meshes</span>
          <span>{formatText(sourceMeshCount)}</span>
          <span className="text-slate-500">triangles</span>
          <span>{formatText(triangleCount)}</span>
          <span className="text-slate-500">corridor</span>
          <span className={corridorDetected ? 'text-emerald-300' : 'text-rose-300'}>{String(Boolean(corridorDetected))}</span>
          <span className="text-slate-500">entry access</span>
          <span className={entryAccessDetected ? 'text-emerald-300' : 'text-rose-300'}>{String(Boolean(entryAccessDetected))}</span>
          <span className="text-slate-500">exit access</span>
          <span className={exitAccessDetected ? 'text-emerald-300' : 'text-rose-300'}>{String(Boolean(exitAccessDetected))}</span>
          <span className="text-slate-500">runtime changed</span>
          <span className={runtimeChanged ? 'text-rose-300' : 'text-emerald-300'}>{String(Boolean(runtimeChanged))}</span>
          <span className="text-slate-500">ready runtime</span>
          <span className={readyForRuntimeIntegration ? 'text-rose-300' : 'text-slate-400'}>{String(Boolean(readyForRuntimeIntegration))}</span>
        </div>
      )}
    </div>
  );
}

export default PitLaneDebugPanel;
