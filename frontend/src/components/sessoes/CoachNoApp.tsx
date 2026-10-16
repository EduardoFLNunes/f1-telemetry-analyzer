/**
 * Pedido 32, Parte B, na seção "Gravações fora do relatório" da tela Sessões:
 *
 * - `BotaoDoCoach`: "Atualizar coach e relatório" roda o mesmo
 *   `tools/atualizar_coach.py` pelo backend (`/api/coleta/coach/rodada`). Mostra
 *   por que está desligado, os 7 passos durante a rodada, o log e, no fim, o
 *   resumo. Uma parada numa trava mostra a mensagem do comando e não tenta de
 *   novo sozinha. Depois de uma rodada completa, as telas leem de novo.
 * - `ConfirmarAnotacao`: a confirmação de "Todas as voltas foram minhas", com a
 *   sessão, a data, as voltas válidas e o carro.
 */
import React, { useEffect, useRef, useState } from 'react';
import { api } from '../../api/client';
import { esquecerLeituras, textoDoErro } from '../../volta/dados';
import { EtiquetaEstado, type Tom } from '../ui/base';
import { ROTULO_DO_PASSO, tempoDaReferencia, type EstadoDoPasso } from './regrasDoCoachNoApp';

const TOM_DO_PASSO: Record<EstadoDoPasso, Tom> = { pendente: 'neutro', rodando: 'aviso', feito: 'ok', parado: 'erro' };
const NOME_DA_REFERENCIA: Record<string, string> = { volta_ia: 'Volta da IA', minha_melhor: 'Sua melhor' };

function Referencias({ antes, depois }: { antes: any; depois: any }) {
  const tipos = Array.from(new Set([...Object.keys(antes || {}), ...Object.keys(depois || {})]));
  return (
    <table className="tabela" style={{ minWidth: 520 }}>
      <thead>
        <tr>
          <th scope="col">Referência</th>
          <th scope="col">Antes</th>
          <th scope="col">Depois</th>
        </tr>
      </thead>
      <tbody>
        {tipos.map((tipo) => {
          const a = antes?.[tipo];
          const d = depois?.[tipo];
          const mudou = a?.volta !== d?.volta;
          return (
            <tr key={tipo}>
              <th scope="row" style={{ color: 'var(--texto-1)', fontSize: 13.5 }}>{NOME_DA_REFERENCIA[tipo] ?? tipo}</th>
              <td className="dado" title={a?.volta}>{a ? tempoDaReferencia(a.tempo_s) : '—'}</td>
              <td className="dado" title={d?.volta}>
                {d ? tempoDaReferencia(d.tempo_s) : '—'}
                {mudou && d && <span className="texto-fraco"> · {d.volta}</span>}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

export const BotaoDoCoach: React.FC<{ pronto: boolean }> = ({ pronto }) => {
  const [estado, setEstado] = useState<any>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [pedindo, setPedindo] = useState(false);
  const recarregadoPara = useRef<string | null>(null);

  useEffect(() => {
    if (!pronto) return undefined;
    let cancelado = false;
    let timer = 0;
    const ler = async () => {
      try {
        const e = await api.getCoachRodada();
        if (cancelado) return;
        setEstado(e);
        setErro(null);
        const r = e?.rodada;
        // Rodada completa: as telas leem de novo, uma vez por rodada.
        // Na primeira leitura só guarda qual foi a última rodada; as telas acabaram de ler.
        const fim = r?.situacao === 'concluida' ? String(r.fim || '') : '';
        if (recarregadoPara.current === null) recarregadoPara.current = fim;
        else if (fim && fim !== recarregadoPara.current) {
          recarregadoPara.current = fim;
          esquecerLeituras();
        }
        timer = window.setTimeout(ler, e?.emAndamento ? 1500 : 10_000);
      } catch (falha) {
        if (cancelado) return;
        setErro(textoDoErro(falha));
        timer = window.setTimeout(ler, 5000);
      }
    };
    ler();
    return () => {
      cancelado = true;
      window.clearTimeout(timer);
    };
  }, [pronto]);

  const iniciar = async () => {
    setPedindo(true);
    try {
      setEstado(await api.postCoachRodada());
      setErro(null);
    } catch (falha) {
      setErro(textoDoErro(falha));
    } finally {
      setPedindo(false);
    }
  };

  const rodada = estado?.rodada;
  const passos: Array<{ id: string; nome: string }> = estado?.passos ?? [];
  const ligado = Boolean(estado?.ligado) && !pedindo;
  const linhas: string[] = rodada?.linhas ?? [];
  return (
    <div className="superficie" style={{ padding: '14px 16px', display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 12 }}>
        <button type="button" className="botao botao--primario" disabled={!ligado} onClick={iniciar}>
          Atualizar coach e relatório
        </button>
        <span className="texto-apoio" style={{ fontSize: 13 }}>
          Roda o <span className="dado">tools/atualizar_coach.py</span> do repositório configurado, incremental, como no terminal.
        </span>
      </div>
      {erro && <p className="texto-apoio" style={{ margin: 0 }}>Sem dados: {erro}</p>}
      {estado && !estado.ligado && (estado.motivos?.length ?? 0) > 0 && (
        <ul className="texto-apoio" style={{ margin: 0, paddingLeft: 18, fontSize: 13 }} aria-label="Por que o botão está desligado">
          {estado.motivos.map((m: string) => <li key={m}>{m}</li>)}
        </ul>
      )}
      {rodada && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }} aria-live="polite">
          <ol className="passos-do-coach" aria-label="Passos da rodada">
            {passos.map((p) => {
              const situacao = (rodada.passos?.[p.id] ?? 'pendente') as EstadoDoPasso;
              return (
                <li key={p.id}>
                  <span className="dado texto-fraco">{p.id}/7</span>
                  <span>{p.nome}</span>
                  <EtiquetaEstado tom={TOM_DO_PASSO[situacao]}>{ROTULO_DO_PASSO[situacao]}</EtiquetaEstado>
                </li>
              );
            })}
          </ol>
          {rodada.situacao === 'parada' && (
            <div className="vidro" role="alert" style={{ padding: '10px 14px', background: 'var(--vermelho-fundo)', borderColor: 'var(--vermelho-borda)' }}>
              <b>O comando parou numa trava.</b> Nada foi tentado de novo.
              <div className="dado" style={{ marginTop: 4, fontSize: 13 }}>{rodada.mensagemDeParada}</div>
            </div>
          )}
          {rodada.situacao === 'falhou' && (
            <p className="texto-apoio" style={{ margin: 0 }}>O comando terminou com o código {String(rodada.codigo)}. O log está abaixo.</p>
          )}
          {rodada.situacao === 'concluida' && rodada.resumo && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              <b>Rodada concluída{rodada.coachRecarregado ? '; o coach ao vivo já usa o modelo novo.' : '.'}</b>
              <div className="fatos dado">
                {(rodada.resumo.sessoesLidas ?? []).length === 0 ? (
                  <span>nenhuma sessão nova ou mudada</span>
                ) : (
                  rodada.resumo.sessoesLidas.map((s: any) => (
                    <span key={s.sessao}>{s.sessao}: {s.voltasNoStore} voltas no store</span>
                  ))
                )}
              </div>
              <div className="tabela-caixa">
                <Referencias antes={rodada.resumo.referenciasAntes} depois={rodada.resumo.referenciasDepois} />
              </div>
              <span className="texto-apoio">
                Contagem oficial da M1:{' '}
                {rodada.resumo.m1?.disponivel === false
                  ? rodada.resumo.m1?.motivo
                  : rodada.resumo.m1?.texto ?? '—'}
                {(rodada.resumo.m1?.sessoesQueContam ?? []).length > 0 && ` (${rodada.resumo.m1.sessoesQueContam.join(', ')})`}
              </span>
            </div>
          )}
          <details>
            <summary className="texto-fraco" style={{ cursor: 'pointer' }}>
              Log da rodada ({linhas.length} linhas{rodada.log ? ` · ${rodada.log}` : ''})
            </summary>
            <pre className="log-do-coach">{linhas.slice(-120).join('\n')}</pre>
          </details>
        </div>
      )}
    </div>
  );
};

export const ConfirmarAnotacao: React.FC<{
  sessao: string;
  quando: string | null;
  voltasValidas: number | null;
  carro: string;
  confirmarCarro: boolean;
  aoCancelar: () => void;
  aoConfirmar: () => void;
  gravando: boolean;
}> = ({ sessao, quando, voltasValidas, carro, confirmarCarro, aoCancelar, aoConfirmar, gravando }) => {
  const confirmar = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    confirmar.current?.focus();
    const tecla = (ev: KeyboardEvent) => ev.key === 'Escape' && aoCancelar();
    window.addEventListener('keydown', tecla);
    return () => window.removeEventListener('keydown', tecla);
  }, [aoCancelar]);
  return (
    <div className="fundo-do-dialogo" onClick={aoCancelar}>
      <div
        className="vidro dialogo"
        role="dialog"
        aria-modal="true"
        aria-labelledby="anotacao-titulo"
        onClick={(ev) => ev.stopPropagation()}
      >
        <h2 id="anotacao-titulo" className="titulo-painel">Todas as voltas foram minhas</h2>
        <p className="texto-apoio" style={{ margin: 0 }}>
          A gravação não tem o indicador de IA. Confirme que você pilotou todas as voltas dela.
        </p>
        <dl className="dados-da-anotacao">
          <dt>Sessão</dt>
          <dd className="dado">{sessao}</dd>
          <dt>Data</dt>
          <dd className="dado">{quando ?? '—'}</dd>
          <dt>Voltas válidas</dt>
          <dd className="dado">{voltasValidas ?? '—'} (pela conferência da Coleta)</dd>
          <dt>Carro</dt>
          <dd className="dado">
            {carro}
            {confirmarCarro && (
              <EtiquetaEstado tom="aviso">confirme o carro</EtiquetaEstado>
            )}
          </dd>
        </dl>
        <p className="texto-fraco" style={{ margin: 0 }}>
          A linha entra em <span className="dado">docs/experimentos/anotacoes_de_sessao.csv</span>, ainda sem commit. Ela vale para o coach na
          próxima rodada.
        </p>
        <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
          <button type="button" className="botao" onClick={aoCancelar}>Cancelar</button>
          <button type="button" className="botao botao--primario" ref={confirmar} onClick={aoConfirmar} disabled={gravando}>
            {gravando ? 'Gravando…' : 'Confirmar'}
          </button>
        </div>
      </div>
    </div>
  );
};
