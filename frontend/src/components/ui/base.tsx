/**
 * Componentes base do sistema visual (pedido 29). O desenho está em
 * src/theme/componentes.css; aqui só a estrutura e a acessibilidade.
 */
import React from 'react';
import clsx from 'clsx';
import type { MensagemRadio } from '../../utils/radio';

// ── Painel de vidro ──────────────────────────────────────────────────────────

type PainelProps = {
  titulo?: React.ReactNode;
  /** Texto pequeno à direita do título (fonte, janela, unidade). */
  nota?: React.ReactNode;
  acao?: React.ReactNode;
  id?: string;
  className?: string;
  style?: React.CSSProperties;
  children?: React.ReactNode;
};

export const PainelVidro: React.FC<PainelProps> = ({ titulo, nota, acao, id, className, style, children }) => {
  const tituloId = id ? `${id}-titulo` : undefined;
  return (
    <section id={id} className={clsx('vidro painel', className)} style={style} aria-labelledby={titulo ? tituloId : undefined}>
      {(titulo || nota || acao) && (
        <div className="painel-cabeca">
          {titulo && <h2 id={tituloId} className="titulo-painel">{titulo}</h2>}
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
            {nota && <span className="texto-fraco dado">{nota}</span>}
            {acao}
          </div>
        </div>
      )}
      {children}
    </section>
  );
};

// ── Cartão de número ─────────────────────────────────────────────────────────

export type CorDoNumero = 'perda' | 'ganho' | 'tempo-roxo' | 'tempo-verde' | 'tempo-amarelo' | null;

export const CartaoNumero: React.FC<{
  rotulo: React.ReactNode;
  /** `null` mostra "—": o número não existe, e nada é inventado no lugar. */
  valor: React.ReactNode | null;
  detalhe?: React.ReactNode;
  cor?: CorDoNumero;
  className?: string;
}> = ({ rotulo, valor, detalhe, cor = null, className }) => (
  <div className={clsx('superficie cartao-numero', className)}>
    <span className="cartao-numero__rotulo">{rotulo}</span>
    <span className={clsx('cartao-numero__valor', valor === null && 'cartao-numero__valor--vazio', cor && `cor-${cor}`)}>
      {valor === null ? '—' : valor}
    </span>
    {detalhe && <span className="cartao-numero__detalhe">{detalhe}</span>}
  </div>
);

// ── Etiqueta de estado ───────────────────────────────────────────────────────

export type Tom = 'ok' | 'aviso' | 'erro' | 'neutro';

/** Cada tom tem um desenho próprio, além da cor. */
const ICONE_DO_TOM: Record<Tom, string> = {
  ok: 'M3 8.5l3 3 7-7',
  aviso: 'M8 3v6M8 12.5v.5',
  erro: 'M4 4l8 8M12 4l-8 8',
  neutro: 'M4 8h8',
};

/** Os estados da Coleta têm desenho próprio: o texto e a forma dizem o que é. */
const ICONE_DO_ESTADO: Record<string, string> = {
  ok: ICONE_DO_TOM.ok,
  ausente: ICONE_DO_TOM.erro,
  parado: 'M5.5 3.5v9M10.5 3.5v9',
  fora_da_faixa: 'M2 8h4M10 8h4M8 2v12',
  taxa_baixa: 'M2 12c2-6 4-8 6-8s4 2 6 8M8 12l2-4',
  sem_dados: ICONE_DO_TOM.neutro,
};

export const EtiquetaEstado: React.FC<{
  tom: Tom;
  /** O estado da Coleta (`parado`, `taxa_baixa`…), para escolher o desenho. */
  estado?: string | null;
  children: React.ReactNode;
  title?: string;
}> = ({ tom, estado, children, title }) => (
  <span className={`etiqueta etiqueta--${tom}`} title={title}>
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={(estado && ICONE_DO_ESTADO[estado]) || ICONE_DO_TOM[tom]} />
    </svg>
    {children}
  </span>
);

// ── Segmentado e chip ────────────────────────────────────────────────────────

export function Segmentado<T extends string>({
  rotulo,
  opcoes,
  valor,
  aoMudar,
  desabilitado,
}: {
  rotulo: string;
  opcoes: ReadonlyArray<{ id: T; texto: React.ReactNode }>;
  valor: T | null | undefined;
  aoMudar: (id: T) => void;
  desabilitado?: boolean;
}) {
  return (
    <div className="segmentado" role="group" aria-label={rotulo}>
      {opcoes.map((opcao) => (
        <button
          key={opcao.id}
          type="button"
          aria-pressed={valor === opcao.id}
          disabled={desabilitado}
          onClick={() => aoMudar(opcao.id)}
        >
          {opcao.texto}
        </button>
      ))}
    </div>
  );
}

export const Chip: React.FC<React.ButtonHTMLAttributes<HTMLButtonElement> & { ativo?: boolean }> = ({ ativo, className, ...resto }) => (
  <button type="button" aria-pressed={ativo} className={clsx('chip', className)} {...resto} />
);

// ── Dica ─────────────────────────────────────────────────────────────────────

/** Dica que segue o mouse. `x` e `y` em coordenadas da janela. */
export const Dica: React.FC<{ x: number; y: number; children: React.ReactNode }> = ({ x, y, children }) => (
  <div className="dica" role="tooltip" style={{ left: x + 12, top: y + 12 }}>
    {children}
  </div>
);

// ── Mensagem de rádio ────────────────────────────────────────────────────────

export const MensagemRadioCartao: React.FC<{ mensagem: MensagemRadio; esmaecida?: number }> = ({ mensagem, esmaecida = 1 }) => (
  <article className="radio" style={{ opacity: esmaecida }}>
    <div className="radio__topo">
      <span className={clsx('radio__tag', mensagem.tipo === 'foco' && 'radio__tag--foco')}>
        <svg width="14" height="12" viewBox="0 0 14 12" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" aria-hidden="true">
          <path d="M1 6v0M4 3.5v5M7 1v10M10 3.5v5M13 6v0" />
        </svg>
        {mensagem.tag}
      </span>
      {mensagem.onde && <span className="radio__onde">{mensagem.onde}</span>}
      {mensagem.hora && <time className="radio__hora">{mensagem.hora}</time>}
    </div>
    <p className="radio__frase">{mensagem.frase}</p>
    {mensagem.detalhe && <p className="radio__detalhe">{mensagem.detalhe}</p>}
  </article>
);
