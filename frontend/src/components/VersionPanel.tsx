/**
 * Which version is installed, which racing line the coach is driving against,
 * and how far behind the repository each of them is.
 *
 * They are shown apart because they move apart: rebuilding the app does not
 * regenerate the racing line, and regenerating the line does not rebuild the
 * app. One combined number would be wrong about one of them.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { RefreshCw } from 'lucide-react';

type RacingLine = {
  track: string;
  lapSeconds: number | null;
  microsectors: number | null;
  source: string | null;
  builtAt: string | null;
  digest: string | null;
  repoDigest: string | null;
  current: boolean | null;
};

type VersionStatus = {
  app?: {
    version: string | null;
    commit: string | null;
    shortCommit: string | null;
    branch: string | null;
    committedAt: string | null;
    builtAt: string | null;
    subject?: string | null;
    dirty?: boolean | null;
    stamped?: boolean;
  };
  racingLines?: RacingLine[];
  repo?: {
    available: boolean;
    reason?: string;
    path?: string | null;
    branch?: string | null;
    shortHead?: string | null;
    dirty?: boolean | null;
    upstream?: string | null;
    ahead?: number | null;
    behind?: number | null;
    fetched?: boolean;
    fetchError?: string | null;
  };
  buildBehind?: { unknownCommit: boolean; commits: number | null } | null;
  checkedAt?: string;
  error?: string;
};

type ProgressEntry = { step: string; ok: boolean; detail: string | null };

const shortDate = (value?: string | null) => {
  if (!value) return '--';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '--' : date.toLocaleString('pt-BR');
};

const Row: React.FC<{ label: string; children: React.ReactNode }> = ({ label, children }) => (
  <div className="flex items-baseline justify-between gap-3 py-0.5">
    <span className="num text-[10px] uppercase tracking-wider text-slate-600">{label}</span>
    <span className="num text-[11px] text-slate-300 text-right">{children}</span>
  </div>
);

export const VersionPanel: React.FC = () => {
  const [status, setStatus] = useState<VersionStatus | null>(null);
  const [checking, setChecking] = useState(false);
  const [updating, setUpdating] = useState(false);
  const [progress, setProgress] = useState<ProgressEntry[]>([]);
  const [message, setMessage] = useState<string | null>(null);

  const bridge = typeof window !== 'undefined' ? window.automobilistaDesktop : undefined;

  const load = useCallback(async (fetchRemote: boolean) => {
    if (!bridge?.versionStatus) return;
    setChecking(true);
    try {
      setStatus(await bridge.versionStatus({ fetch: fetchRemote }));
    } catch (error) {
      setStatus({ error: String(error) });
    } finally {
      setChecking(false);
    }
  }, [bridge]);

  useEffect(() => { load(false); }, [load]);

  useEffect(() => {
    if (!bridge?.onUpdateProgress) return;
    return bridge.onUpdateProgress((entry: ProgressEntry) => {
      setProgress((current) => [...current, entry]);
    });
  }, [bridge]);

  const update = useCallback(async () => {
    if (!bridge?.runUpdate) return;
    setUpdating(true);
    setProgress([]);
    setMessage(null);
    try {
      const result = await bridge.runUpdate();
      setMessage(result?.ok
        ? 'Atualizado. Reinicie o aplicativo para rodar a versao nova.'
        : result?.error || 'A atualizacao falhou.');
      if (result?.ok) await load(false);
    } catch (error) {
      setMessage(String(error));
    } finally {
      setUpdating(false);
    }
  }, [bridge, load]);

  if (!bridge?.versionStatus) {
    return (
      <div className="panel p-3">
        <span className="num text-[11px] uppercase tracking-widest text-slate-500">Versao</span>
        <p className="num text-[10px] text-slate-600 mt-2">
          Disponivel apenas no aplicativo desktop.
        </p>
      </div>
    );
  }

  const app = status?.app;
  const repo = status?.repo;
  const behind = status?.buildBehind?.commits ?? null;
  const lines = status?.racingLines ?? [];

  return (
    <div className="panel flex flex-col">
      <div className="flex items-center justify-between px-3 py-1.5"
        style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
        <span className="num text-[11px] font-bold uppercase tracking-widest text-slate-400">Versao</span>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => { setMessage(null); load(true); }}
            disabled={checking || updating}
            className="num text-[10px] uppercase tracking-wider px-2 py-1 rounded-sm disabled:opacity-40"
            style={{ background: 'rgba(255,255,255,0.05)', color: '#cbd5e1' }}
          >
            <RefreshCw size={10} className="inline mr-1" />
            {checking ? 'Verificando' : 'Verificar'}
          </button>
          <button
            type="button"
            onClick={update}
            disabled={updating || checking || !repo?.available || behind === 0}
            className="num text-[10px] uppercase tracking-wider px-2 py-1 rounded-sm disabled:opacity-40"
            style={{ background: 'rgba(34,211,238,0.12)', color: '#22d3ee' }}
          >
            {updating ? 'Atualizando...' : 'Atualizar'}
          </button>
        </div>
      </div>

      <div className="px-3 py-2 flex flex-col gap-3">
        <section>
          <div className="num text-[10px] uppercase tracking-widest text-slate-500 mb-1">Aplicativo</div>
          <Row label="versao">{app?.version ?? '--'}</Row>
          <Row label="commit">
            {app?.shortCommit ?? '--'}{app?.dirty ? ' + alteracoes locais' : ''}
          </Row>
          <Row label="compilado em">{shortDate(app?.builtAt)}</Row>
          {app?.stamped === false && (
            <p className="num text-[10px] text-amber-500/80 mt-1">
              Build sem carimbo — provavelmente uma execucao de desenvolvimento.
            </p>
          )}
          <Row label="atras do repositorio">
            {behind === null
              ? (status?.buildBehind?.unknownCommit ? 'commit desconhecido' : '--')
              : behind === 0
                ? 'em dia'
                : `${behind} commit${behind === 1 ? '' : 's'}`}
          </Row>
        </section>

        <section>
          <div className="num text-[10px] uppercase tracking-widest text-slate-500 mb-1">
            Tracado do modelo
          </div>
          {lines.length === 0 ? (
            <p className="num text-[10px] text-slate-600">
              Nenhum tracado instalado — o coach usa apenas o melhor do proprio piloto.
            </p>
          ) : lines.map((line) => (
            <div key={line.track} className="mb-1.5">
              <Row label={line.track}>
                {line.lapSeconds !== null ? `${line.lapSeconds.toFixed(3)}s` : '--'}
                {' · '}
                {line.current === null ? 'sem repositorio' : line.current ? 'em dia' : 'desatualizado'}
              </Row>
              <Row label="gerado em">{shortDate(line.builtAt)}</Row>
            </div>
          ))}
        </section>

        <section>
          <div className="num text-[10px] uppercase tracking-widest text-slate-500 mb-1">Repositorio</div>
          {!repo?.available ? (
            <p className="num text-[10px] text-slate-600">
              {repo?.reason === 'git_unavailable'
                ? 'git nao encontrado nesta maquina.'
                : 'Nenhum repositorio nesta maquina; atualizar exige o projeto clonado.'}
            </p>
          ) : (
            <>
              <Row label="branch">{repo.branch ?? '--'} @ {repo.shortHead ?? '--'}</Row>
              <Row label="upstream">
                {repo.upstream ?? 'sem upstream'}
                {repo.behind ? ` · ${repo.behind} atras` : ''}
                {repo.ahead ? ` · ${repo.ahead} a frente` : ''}
              </Row>
              {repo.dirty && (
                <p className="num text-[10px] text-amber-500/80 mt-1">
                  Arvore com mudancas nao commitadas — atualizar esta bloqueado.
                </p>
              )}
              {repo.fetchError && (
                <p className="num text-[10px] text-rose-400/80 mt-1">fetch: {repo.fetchError}</p>
              )}
            </>
          )}
        </section>

        {progress.length > 0 && (
          <section>
            <div className="num text-[10px] uppercase tracking-widest text-slate-500 mb-1">Progresso</div>
            {progress.map((entry, index) => (
              <div key={index} className="num text-[10px] flex gap-2">
                <span className={entry.ok ? 'text-emerald-400' : 'text-rose-400'}>
                  {entry.ok ? 'ok' : 'erro'}
                </span>
                <span className="text-slate-400">{entry.step}</span>
              </div>
            ))}
          </section>
        )}

        {message && <p className="num text-[10px] text-slate-400">{message}</p>}
      </div>
    </div>
  );
};
