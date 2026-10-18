/**
 * Mensagens de rádio (pedido 29): a frase do coach, montada em português a
 * partir dos números do evento.
 *
 * O backend manda a frase pronta, sem acento e com ponto decimal ("0.31s atras
 * da volta da IA"); mudar isso seria mudar o coach. Os números estão todos no
 * `evidence` do evento, então a tela monta a frase com eles: os mesmos números
 * e a mesma regra, só a escrita muda. Evento sem os números → a frase do
 * backend, como veio.
 *
 * "Setor N" no coach é o índice N do microssetor, contado a partir de 0
 * (`int(progresso × 60)` em `driving_coach.py`). O piloto vê o microssetor
 * contado a partir de 1, como no mapa e no relatório de evolução (pedido 31,
 * A.2): o índice 2 do coach é o microssetor 3. O índice interno não muda.
 */

/** Índice do coach (a partir de 0) → número que o piloto vê (a partir de 1). */
export function microssetorParaOPiloto(indice: number): number {
  return indice + 1;
}

export type EventoCoach = {
  type?: string;
  event?: string;
  message?: string;
  severity?: number;
  evidence?: unknown;
  focusSectors?: number[];
  focusSource?: string;
  lap_number?: number;
  timestamp?: number;
};

export type MensagemRadio = {
  id: string;
  tipo: 'diferenca' | 'foco' | 'outro';
  tag: string;
  onde: string;
  hora: string;
  frase: string;
  detalhe: string | null;
  /** Segundos perdidos no trecho, quando o evento é uma diferença. */
  perdaS: number | null;
};

function numero(valor: unknown): number | null {
  if (valor === null || valor === undefined || typeof valor === 'boolean') return null;
  const n = Number(valor);
  return Number.isFinite(n) ? n : null;
}

/** 0,31 (sempre com `casas` casas e vírgula). */
export function decimal(valor: number, casas = 2): string {
  return valor.toLocaleString('pt-BR', { minimumFractionDigits: casas, maximumFractionDigits: casas });
}

/** +0,31 s / −0,12 s: o sinal sempre vai junto do número. */
export function diferencaComSinal(segundos: number, casas = 2): string {
  const sinal = segundos > 0 ? '+' : segundos < 0 ? '−' : '';
  return `${sinal}${decimal(Math.abs(segundos), casas)} s`;
}

export function horaDoEvento(timestamp: number | null | undefined): string {
  const t = numero(timestamp);
  if (t === null) return '';
  const data = new Date(t > 1e12 ? t : t * 1000);
  if (Number.isNaN(data.getTime())) return '';
  const dois = (n: number) => String(n).padStart(2, '0');
  return `${dois(data.getHours())}:${dois(data.getMinutes())}:${dois(data.getSeconds())}`;
}

function listaPorExtenso(itens: Array<string | number>): string {
  const textos = itens.map(String);
  if (textos.length <= 1) return textos.join('');
  return `${textos.slice(0, -1).join(', ')} e ${textos[textos.length - 1]}`;
}

function clausulaDaFreada(tipo: string | null, deltaM: number): string {
  const metros = Math.abs(Math.round(deltaM));
  const lado = deltaM > 0 ? 'depois' : 'antes';
  if (tipo === 'minha_melhor') {
    return metros < 1 ? 'na sua melhor volta você freou no mesmo ponto' : `na sua melhor volta você freou ${metros} m ${lado}`;
  }
  const quem = tipo === 'volta_ia' ? 'a IA' : 'a referência';
  return metros < 1 ? `${quem} freia no mesmo ponto que você` : `${quem} freia ${metros} m ${lado} de você`;
}

function clausulaDaMinima(tipo: string | null, referenciaKmh: number, suaKmh: number): string {
  const ref = Math.round(referenciaKmh);
  const sua = Math.round(suaKmh);
  if (tipo === 'volta_ia') return `mínima da IA ${ref} km/h, a sua ${sua} km/h`;
  if (tipo === 'minha_melhor') return `mínima na sua melhor volta ${ref} km/h, agora ${sua} km/h`;
  return `mínima na referência ${ref} km/h, a sua ${sua} km/h`;
}

/**
 * Pedido 31: a mensagem que o backend montou (`/api/radio/mensagens`, ou o campo
 * `radio` das frases de uma volta gravada). O texto vem pronto, igual ao do app
 * do jogo; aqui ela só vira o formato do cartão.
 */
export type MensagemDoBackend = {
  id?: number;
  origem: 'coach' | 'resumo' | 'teste' | string;
  titulo: string;
  texto: string;
  detalhe: string | null;
  fala?: string;
  microssetor: number | null;
  curva: string | null;
  s: number | null;
  sCarro?: number | null;
  voltaDoCarro?: number | null;
  entregueEm?: string | null;
  audio?: string | null;
  perdaS?: number | null;
};

export type MensagemRadioComAudio = MensagemRadio & { audio: string | null; sCarro: number | null };

const TAG_DA_ORIGEM: Record<string, string> = { coach: 'Rádio', resumo: 'Volta', teste: 'Teste' };

export function mensagemDoRadio(m: MensagemDoBackend, indice = 0): MensagemRadioComAudio {
  const ponto = numero(m.sCarro) ?? numero(m.s);
  const onde = [
    m.titulo,
    m.microssetor ? `microssetor ${m.microssetor}` : null,
    ponto !== null && m.origem !== 'teste' ? `${Math.round(ponto).toLocaleString('pt-BR')} m` : null,
  ].filter(Boolean).join(' · ');
  return {
    id: `${m.id ?? 'sem-id'}-${indice}`,
    tipo: m.origem === 'coach' ? 'diferenca' : 'outro',
    tag: TAG_DA_ORIGEM[m.origem] ?? 'Rádio',
    onde,
    hora: m.entregueEm ? m.entregueEm.slice(11, 19) : '',
    frase: m.texto,
    detalhe: m.detalhe ?? null,
    perdaS: numero(m.perdaS),
    audio: m.audio ?? null,
    sCarro: numero(m.sCarro),
  };
}

/** Um evento de `/api/live/coach` (ou do WebSocket) como mensagem de rádio. */
export function mensagemDoEvento(evento: EventoCoach, indice = 0): MensagemRadio {
  const volta = numero(evento.lap_number);
  const hora = horaDoEvento(evento.timestamp);
  const id = `${evento.timestamp ?? 'sem-hora'}-${evento.type ?? 'evento'}-${indice}`;
  const textoOriginal = String(evento.event ?? evento.message ?? '').trim();

  if (evento.type === 'coaching_focus' && Array.isArray(evento.focusSectors) && evento.focusSectors.length) {
    const setores = evento.focusSectors.map((indice) => microssetorParaOPiloto(Number(indice)));
    const onde = evento.focusSource === 'sessao' ? 'nas últimas 5 voltas válidas da sessão' : 'nas suas voltas do modelo';
    return {
      id,
      tipo: 'foco',
      tag: 'Foco',
      onde: volta ? `volta ${volta}` : 'antes da volta',
      hora,
      frase: `Foco nas próximas voltas: ${setores.length === 1 ? 'microssetor' : 'microssetores'} ${listaPorExtenso(setores)}`,
      detalhe: `maior diferença mediana para a referência ${onde}`,
      perdaS: null,
    };
  }

  const ev = evento.evidence && typeof evento.evidence === 'object' ? (evento.evidence as Record<string, unknown>) : null;
  const microssetor = numero(ev?.microsector);
  const sua = numero(ev?.yourSeconds);
  const referencia = numero(ev?.referenceSeconds) ?? numero(ev?.bestSeconds);
  const perda = numero(ev?.lossSeconds) ?? (sua !== null && referencia !== null ? sua - referencia : null);

  if (ev && microssetor !== null && sua !== null && referencia !== null && perda !== null) {
    const tipoRef = typeof ev.referenceKind === 'string' ? ev.referenceKind : null;
    const rotulo = typeof ev.referenceLabel === 'string' && ev.referenceLabel
      ? ev.referenceLabel
      : numero(ev.bestSeconds) !== null && numero(ev.referenceSeconds) === null
        ? 'seu melhor neste microssetor'
        : 'referência';
    const partes = [`${decimal(sua)} s contra ${decimal(referencia)} s`];
    const freada = numero(ev.brakeDeltaM);
    if (freada !== null) partes.push(clausulaDaFreada(tipoRef, freada));
    const minRef = numero(ev.referenceMinSpeedKmh);
    const minSua = numero(ev.yourMinSpeedKmh);
    if (minRef !== null && minSua !== null) partes.push(clausulaDaMinima(tipoRef, minRef, minSua));
    const artigo = rotulo.startsWith('seu ') ? 'o' : 'a';
    return {
      id,
      tipo: 'diferenca',
      tag: 'Rádio',
      onde: [volta ? `volta ${volta}` : null, `microssetor ${microssetorParaOPiloto(microssetor)}`].filter(Boolean).join(' · '),
      hora,
      frase: `${diferencaComSinal(perda)} para ${artigo} ${rotulo} neste trecho`,
      detalhe: partes.join(' · '),
      perdaS: perda,
    };
  }

  return {
    id,
    tipo: 'outro',
    tag: 'Rádio',
    onde: volta ? `volta ${volta}` : '',
    hora,
    frase: textoOriginal || 'Mensagem sem texto',
    detalhe: null,
    perdaS: null,
  };
}
