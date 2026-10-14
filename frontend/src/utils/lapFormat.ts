/** M:SS,mmm, com vírgula (ADR 0003; pedido 29). */
export function formatLapTime(seconds: number | null | undefined): string {
  if (typeof seconds !== 'number' || !Number.isFinite(seconds) || seconds < 0) {
    return '--:--,---';
  }

  const minutes = Math.floor(seconds / 60);
  const remaining = seconds - minutes * 60;
  return `${minutes}:${remaining.toFixed(3).padStart(6, '0').replace('.', ',')}`;
}

export function formatDelta(seconds: number | null | undefined): string {
  if (typeof seconds !== 'number' || !Number.isFinite(seconds)) {
    return 'N/A';
  }
  // Vírgula e o sinal sempre junto do número (pedido 29).
  return `${seconds > 0 ? '+' : seconds < 0 ? '−' : ''}${Math.abs(seconds).toFixed(3).replace('.', ',')}`;
}

export function deltaTone(seconds: number | null | undefined): string {
  if (typeof seconds !== 'number' || !Number.isFinite(seconds)) {
    return 'text-slate-500';
  }
  return seconds <= 0 ? 'text-emerald-400' : 'text-rose-400';
}
