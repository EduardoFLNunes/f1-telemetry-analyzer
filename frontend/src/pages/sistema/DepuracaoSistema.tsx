/**
 * Sistema › Depuração (pedido 29): tudo o que era de desenvolvimento e estava
 * nas telas do piloto (inventário, problema C).
 *
 * - O mapa com o PERF, os modos de depuração da linha (DIAG, RAW, PTS, SEGS,
 *   SMTH, SPEED), o HUD técnico ("N m | N pts | fonte") e as coordenadas de
 *   mundo dos oponentes.
 * - O estado da volta do store (o antigo LAP DBG dos traços).
 * - Os eventos crus do coach, com o `evidence` (antes no CoachingFeed).
 * - A medida de quadros por segundo, com e sem vidro.
 */
import React, { useEffect, useState } from 'react';
import { api } from '../../api/client';
import { TrackRenderer } from '../../components/map/TrackRenderer';
import { PainelVidro, Segmentado } from '../../components/ui/base';
import { useTelemetryStore, type LapDebugState } from '../../store/useTelemetryStore';
import { aplicarVidro, medirQuadros, vidroLigado } from '../../theme/vidro';

const MapaComDepuracao: React.FC = () => {
  const [pista, setPista] = useState<any>(null);
  const [motivo, setMotivo] = useState<string | null>('lendo a geometria…');
  useEffect(() => {
    let cancelado = false;
    api.getTrackGeometry()
      .then((g) => {
        if (cancelado) return;
        setPista(g?.track ?? null);
        setMotivo(g?.track ? null : 'o backend ainda não tem a pista pronta');
      })
      .catch(() => !cancelado && setMotivo('o backend não respondeu'));
    return () => {
      cancelado = true;
    };
  }, []);
  return (
    <PainelVidro id="dep-mapa" titulo="Mapa com depuração" nota="PERF, modos da linha, HUD técnico e oponentes">
      <div className="superficie" style={{ position: 'relative', height: 560, overflow: 'hidden' }}>
        {pista ? <TrackRenderer trackData={pista} depuracao /> : <p className="texto-fraco" style={{ margin: 16 }}>{motivo}</p>}
      </div>
    </PainelVidro>
  );
};

const ROTULOS_VOLTA: Array<[keyof LapDebugState, string]> = [
  ['currentLapNumber', 'Volta atual'],
  ['referenceLapNumber', 'Volta de referência'],
  ['currentLapSamplesLength', 'Amostras da volta atual'],
  ['previousLapSamplesLength', 'Amostras da volta anterior'],
  ['currentLapIsPartial', 'Volta parcial'],
  ['lastCompletedLapNumber', 'Última volta fechada'],
  ['lastLapTransitionReason', 'Motivo da última troca'],
  ['lastRejectedLapReason', 'Motivo da última rejeição'],
  ['previousLapValid', 'Anterior válida'],
  ['finalizedProgressStart', 'Progresso inicial'],
  ['finalizedProgressEnd', 'Progresso final'],
  ['finalizedLapDuration', 'Duração (s)'],
];

const EstadoDaVolta: React.FC = () => {
  const [volta, setVolta] = useState<LapDebugState | null>(null);
  useEffect(() => {
    const ler = () => setVolta(useTelemetryStore.getState().lapDebug);
    ler();
    const timer = window.setInterval(ler, 500);
    return () => window.clearInterval(timer);
  }, []);
  return (
    <PainelVidro id="dep-volta" titulo="Estado da volta" nota="store do front, a cada 0,5 s">
      <div className="superficie tabela-caixa">
        <table className="tabela">
          <tbody>
            {ROTULOS_VOLTA.map(([chave, rotulo]) => {
              const v = volta ? (volta as any)[chave] : null;
              return (
                <tr key={String(chave)}>
                  <td className="texto-apoio">{rotulo}</td>
                  <td className="num">{v === null || v === undefined ? '—' : typeof v === 'boolean' ? (v ? 'sim' : 'não') : typeof v === 'number' ? v.toLocaleString('pt-BR', { maximumFractionDigits: 3 }) : String(v)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </PainelVidro>
  );
};

const EventosCrus: React.FC = () => {
  const [eventos, setEventos] = useState<any[] | null>(null);
  useEffect(() => {
    let cancelado = false;
    const ler = () => api.getLiveCoach().then((d) => !cancelado && setEventos(Array.isArray(d?.events) ? d.events : [])).catch(() => !cancelado && setEventos(null));
    ler();
    const timer = window.setInterval(ler, 3000);
    return () => {
      cancelado = true;
      window.clearInterval(timer);
    };
  }, []);
  return (
    <PainelVidro id="dep-coach" titulo="Eventos crus do coach" nota="/api/live/coach, sem tradução">
      <pre className="superficie dado" style={{ margin: 0, padding: 14, maxHeight: 320, overflow: 'auto', fontSize: 12, color: 'var(--texto-2)', whiteSpace: 'pre-wrap' }}>
        {eventos === null ? 'o backend não respondeu' : eventos.length ? JSON.stringify(eventos.slice(0, 8), null, 2) : 'nenhum evento nesta abertura do app'}
      </pre>
    </PainelVidro>
  );
};

type Medida = { vidro: 'ligado' | 'desligado'; fps: number; quadros: number; piorQuadroMs: number; p95Ms: number };

const VidroEDesempenho: React.FC = () => {
  const [ligado, setLigado] = useState(vidroLigado());
  const [medidas, setMedidas] = useState<Medida[]>([]);
  const [medindo, setMedindo] = useState(false);
  const mudar = (id: 'ligado' | 'desligado') => {
    setLigado(id === 'ligado');
    aplicarVidro(id === 'ligado');
  };
  const medir = async () => {
    setMedindo(true);
    const r = await medirQuadros(10_000);
    const medida: Medida = { vidro: ligado ? 'ligado' : 'desligado', ...r };
    setMedidas((m) => [medida, ...m].slice(0, 6));
    setMedindo(false);
  };
  return (
    <PainelVidro id="dep-vidro" titulo="Vidro e desempenho" nota="quadros por segundo da janela, por requestAnimationFrame">
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'center' }}>
        <Segmentado rotulo="Vidro" opcoes={[{ id: 'ligado', texto: 'Vidro ligado' }, { id: 'desligado', texto: 'Sem transparência' }]} valor={ligado ? 'ligado' : 'desligado'} aoMudar={mudar} />
        <button type="button" className="botao" onClick={medir} disabled={medindo}>{medindo ? 'Medindo (10 s)…' : 'Medir quadros por segundo (10 s)'}</button>
      </div>
      <p className="texto-fraco" style={{ margin: 0 }}>
        Para medir o mapa animado, deixe uma volta tocando no replay: o mapa acima redesenha a cada quadro.
      </p>
      {medidas.length > 0 && (
        <div className="superficie tabela-caixa">
          <table className="tabela">
            <thead>
              <tr><th scope="col">Vidro</th><th scope="col" className="num">Quadros/s</th><th scope="col" className="num">p95 (ms)</th><th scope="col" className="num">Pior quadro (ms)</th><th scope="col" className="num">Quadros</th></tr>
            </thead>
            <tbody>
              {medidas.map((m, i) => (
                <tr key={i}>
                  <td>{m.vidro}</td>
                  <td className="num">{m.fps.toLocaleString('pt-BR')}</td>
                  <td className="num">{m.p95Ms.toLocaleString('pt-BR')}</td>
                  <td className="num">{m.piorQuadroMs.toLocaleString('pt-BR')}</td>
                  <td className="num">{m.quadros}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </PainelVidro>
  );
};

export const DepuracaoSistema: React.FC = () => (
  <>
    <VidroEDesempenho />
    <MapaComDepuracao />
    <div className="grade-2">
      <EstadoDaVolta />
      <EventosCrus />
    </div>
  </>
);

export default DepuracaoSistema;
