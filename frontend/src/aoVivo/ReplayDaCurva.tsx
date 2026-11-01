/**
 * O replay da curva na tela Ao vivo (pedido 36, Parte E.5): o engenheiro mostra o que diz.
 *
 * Sob o cartão da análise e da frase do coach com causa: a curva vista de cima, sobre a
 * pista tratada (as camadas do cache que o mapa do app desenha), com as duas linhas
 * ("você" e "IA (referência)"), os dois carros andando cada um no seu próprio tempo a
 * partir da mesma entrada, as duas freadas com a distância, as duas mínimas com o valor,
 * o traçado no ponto da mínima da referência e o tempo perdido na curva. Toca cada curva
 * citada uma vez; o botão repete.
 *
 * Pedido 43:
 * - **na frase do coach, os números da voz** (a freada, as mínimas e o tempo, nos pontos onde o
 *   coach mediu) e o trecho da fala, uma faixa clara na pista e nos visuais; sem o traçado;
 * - **os visuais sob a animação:** a faixa do pedal (C.3), a diferença acumulada (C.2) e a
 *   velocidade (C.1), pela distância desde a entrada, com o cursor de cada carro.
 */
import React, { useEffect, useRef, useState } from 'react';
import { api } from '../api/client';
import { drawTrackSurface } from '../components/map/OverlayRenderer';
import { lerCamadasDaPista, useLeitura } from '../volta/dados';
import { transformarCamadas } from '../volta/projecao';
import {
  ALTURAS_DOS_VISUAIS, QuadroDeRotulos, cameraDaCurva, diferencaAcumulada, distanciaNoTempo, dividirAArea,
  faixasDoPedal, indicesDoTrecho, posicaoNoTempo, temVisuais, textoDaFreada, textoDaMinima, textoDoAlto,
  textoDoTracado, type Area, type CurvaDoReplay, type DadosDoReplay, type LugarDoRotulo,
} from './replay';

const ALTURA_DO_REPLAY = 250;
const PAUSA_NO_FIM_S = 1.2;      // o fim de cada curva fica parado um pouco, antes da próxima
const COR_VOCE = '#e10600';
const COR_REF = 'rgba(233,237,242,0.9)';
const COR_TRECHO = 'rgba(255,255,255,0.16)';           // o trecho da fala nos visuais
const COR_TRECHO_NA_PISTA = 'rgba(255,255,255,0.32)';  // e sobre a pista, mais forte
// As cores do pedal, as do traçado pintado pelo pedal (a tela Volta e o mapa aproximado do jogo).
const CORES_DO_PEDAL: Record<number, string> = { 0: '#f5c542', 1: '#3ddc84', 2: '#ff5a5f' };
const COR_PERDA = 'rgba(255,162,74,0.35)';
const COR_GANHO = 'rgba(111,155,255,0.35)';
const FONTE = '600 11px "Barlow", "Segoe UI", sans-serif';
const FONTE_PEQUENA = '600 10px "Barlow", "Segoe UI", sans-serif';
const COLUNA_DOS_NOMES = 34;     // à esquerda dos visuais: "você", "IA" e os títulos

function desenharACurva(ctx: CanvasRenderingContext2D, c: CurvaDoReplay, t: number, a: Area, camadas: any) {
  const { x: X, y: Y, w: W, h: H } = a;
  const cam0 = cameraDaCurva(c, W, H);
  const tela = (x: number, z: number): [number, number] => {
    const [sx, sy] = cam0.tela(x, z);
    return [X + sx, Y + sy];
  };
  ctx.save();
  ctx.beginPath();
  ctx.rect(X, Y, W, H);
  ctx.clip();
  ctx.fillStyle = '#111214';
  ctx.fillRect(X, Y, W, H);
  if (camadas) {
    // A pista tratada, na mesma câmera: tela = A + k (R base(x, z) − rc).
    ctx.save();
    ctx.translate(X + cam0.ax, Y + cam0.ay);
    ctx.scale(cam0.k, cam0.k);
    ctx.translate(-cam0.rcx, -cam0.rcy);
    ctx.rotate(cam0.ang);
    transformarCamadas(ctx);
    drawTrackSurface(ctx, camadas, null, cam0.k);
    ctx.restore();
  }
  const linha = (pts: CurvaDoReplay['linhas']['voce'], cor: string, largura: number) => {
    ctx.beginPath();
    pts.forEach((p, i) => {
      const [x, y] = tela(p[0], p[1]);
      if (i) ctx.lineTo(x, y);
      else ctx.moveTo(x, y);
    });
    ctx.strokeStyle = cor;
    ctx.lineWidth = largura;
    ctx.lineJoin = 'round';
    ctx.lineCap = 'round';
    ctx.stroke();
  };
  // Pedido 43: o trecho da fala, uma faixa clara sobre a pista (o microssetor que a voz mediu).
  const trecho = indicesDoTrecho(c);
  if (trecho) linha(c.linhas.referencia.slice(trecho[0], trecho[1] + 1), COR_TRECHO_NA_PISTA, 16);
  ctx.lineCap = 'butt';
  linha(c.linhas.referencia, COR_REF, 2.5);
  linha(c.linhas.voce, COR_VOCE, 2.5);
  // Os pontos que os rótulos não cobrem: os dois carros, as freadas, as mínimas e o traçado.
  const q = new QuadroDeRotulos([X + 2, Y + 26, X + W - 2, Y + H - 2]);
  const [rx, rz] = posicaoNoTempo(c.linhas.referencia, t);
  const [vx, vz] = posicaoNoTempo(c.linhas.voce, t);
  const [rsx, rsy] = tela(rx, rz);
  const [vsx, vsy] = tela(vx, vz);
  q.ocupar(rsx, rsy, 9);
  q.ocupar(vsx, vsy, 9);
  const mv = c.minimas ? tela(c.minimas.voce.x, c.minimas.voce.z) : null;
  const mr = c.minimas ? tela(c.minimas.referencia.x, c.minimas.referencia.z) : null;
  const tv = c.tracado ? tela(c.tracado.voce[0], c.tracado.voce[1]) : null;
  const tr = c.tracado ? tela(c.tracado.referencia[0], c.tracado.referencia[1]) : null;
  for (const p of [mv, mr, tv, tr]) if (p) q.ocupar(p[0], p[1], 5);
  ctx.font = FONTE;
  ctx.textAlign = 'left';
  ctx.textBaseline = 'top';
  const rotulo = (texto: string, x: number, y: number, cor: string, preferido: LugarDoRotulo) => {
    const w = ctx.measureText(texto).width + 6;
    const [bx, by, longe] = q.colocar(x, y, w, 15, preferido);
    if (longe) {
      ctx.beginPath();
      ctx.moveTo(x, y);
      ctx.lineTo(Math.min(Math.max(x, bx), bx + w), Math.min(Math.max(y, by), by + 15));
      ctx.strokeStyle = cor;
      ctx.lineWidth = 1;
      ctx.stroke();
    }
    ctx.fillStyle = 'rgba(8,9,11,0.7)';
    ctx.fillRect(bx, by, w, 15);
    ctx.fillStyle = cor;
    ctx.fillText(texto, bx + 3, by + 1);
  };
  if (trecho) {
    const meio = c.linhas.referencia[Math.round((trecho[0] + trecho[1]) / 2)];
    const [x, y] = tela(meio[0], meio[1]);
    rotulo('trecho da fala', x, y, '#f2f4f5', 'esquerda');
  }
  // As freadas: um traço atravessando cada linha, e a distância entre elas.
  const traco = (m: { x: number; z: number } | null, cor: string) => {
    if (!m) return null;
    const [x, y] = tela(m.x, m.z);
    ctx.beginPath();
    ctx.moveTo(x - 7, y);
    ctx.lineTo(x + 7, y);
    ctx.strokeStyle = cor;
    ctx.lineWidth = 3;
    ctx.stroke();
    q.ocupar(x, y, 7);
    return [x, y];
  };
  const fv = traco(c.freadas.voce, COR_VOCE);
  traco(c.freadas.referencia, COR_REF);
  const contra = c.referencia === 'minha_melhor' ? 'da sua melhor' : 'da IA';
  const tf = textoDaFreada(c.freadas.distanciaM, contra);
  if (fv && tf) rotulo(tf, fv[0], fv[1], COR_VOCE, 'direita');
  // O traçado: uma seta entre as duas linhas, no ponto da mínima da referência (só na análise).
  if (c.tracado && tv && tr) {
    const [tvx, tvy] = tv;
    const [trx, try_] = tr;
    if (Math.hypot(tvx - trx, tvy - try_) > 2) {
      ctx.beginPath();
      ctx.moveTo(trx, try_);
      ctx.lineTo(tvx, tvy);
      ctx.strokeStyle = '#f5c542';
      ctx.lineWidth = 1.5;
      ctx.stroke();
      const ang = Math.atan2(tvy - try_, tvx - trx);
      ctx.beginPath();
      ctx.moveTo(tvx, tvy);
      ctx.lineTo(tvx - 7 * Math.cos(ang - 0.5), tvy - 7 * Math.sin(ang - 0.5));
      ctx.lineTo(tvx - 7 * Math.cos(ang + 0.5), tvy - 7 * Math.sin(ang + 0.5));
      ctx.closePath();
      ctx.fillStyle = '#f5c542';
      ctx.fill();
    }
    rotulo(textoDoTracado(c.tracado), (tvx + trx) / 2, (tvy + try_) / 2, '#f5c542', 'abaixo');
  }
  // As mínimas, no ponto de cada uma.
  if (c.minimas && mv && mr) {
    for (const [x, y, cor] of [[mv[0], mv[1], COR_VOCE], [mr[0], mr[1], COR_REF]] as [number, number, string][]) {
      ctx.beginPath();
      ctx.arc(x, y, 3.5, 0, 2 * Math.PI);
      ctx.fillStyle = cor;
      ctx.fill();
    }
    rotulo(`mínima ${textoDaMinima(c.minimas.voce.kmh)}`, mv[0], mv[1], COR_VOCE, 'esquerda');
    rotulo(`mínima ${textoDaMinima(c.minimas.referencia.kmh)}`, mr[0], mr[1], COR_REF, 'direita');
  }
  // Os dois carros, cada um no seu tempo.
  const marca = (x: number, y: number, miolo: string, borda: string) => {
    ctx.beginPath();
    ctx.arc(x, y, 6.5, 0, 2 * Math.PI);
    ctx.fillStyle = miolo;
    ctx.fill();
    ctx.lineWidth = 2.5;
    ctx.strokeStyle = borda;
    ctx.stroke();
  };
  marca(rsx, rsy, 'rgba(8,9,11,0.6)', COR_REF);
  marca(vsx, vsy, '#ffffff', COR_VOCE);
  rotulo(c.rotuloDaReferencia, rsx, rsy, COR_REF, 'direitaAcima');
  rotulo('você', vsx, vsy, '#ffffff', 'esquerdaAbaixo');
  // O alto: a curva, a volta e o tempo (na frase do coach, o da voz).
  ctx.fillStyle = 'rgba(8,9,11,0.8)';
  ctx.fillRect(X, Y, W, 24);
  ctx.textBaseline = 'alphabetic';
  ctx.fillStyle = '#f2f4f5';
  ctx.font = '600 12px "Barlow", "Segoe UI", sans-serif';
  ctx.fillText(textoDoAlto(c), X + 10, Y + 16);
  ctx.restore();
}

/** O fundo de um visual, a faixa do trecho da fala, o nome à esquerda e a escala de x (metros). */
function moldura(ctx: CanvasRenderingContext2D, c: CurvaDoReplay, a: Area, titulo: string) {
  ctx.fillStyle = '#16181b';
  ctx.fillRect(a.x, a.y, a.w, a.h - 2);
  const x0 = a.x + COLUNA_DOS_NOMES;
  const largura = a.w - COLUNA_DOS_NOMES - 8;
  const total = Math.max((c.linhas.voce.length - 1) * (c.passoM ?? 1), 1);
  const x = (d: number) => x0 + (largura * d) / total;
  if (c.voz) {
    ctx.fillStyle = COR_TRECHO;
    ctx.fillRect(x(c.voz.inicioM), a.y, x(c.voz.fimM) - x(c.voz.inicioM), a.h - 2);
  }
  ctx.font = FONTE_PEQUENA;
  ctx.textBaseline = 'top';
  ctx.textAlign = 'left';
  ctx.fillStyle = '#8c949c';
  ctx.fillText(titulo, x0 + 2, a.y + 2);
  return x;
}

function cursores(ctx: CanvasRenderingContext2D, c: CurvaDoReplay, t: number, a: Area, x: (d: number) => number) {
  const passo = c.passoM ?? 1;
  for (const [linha, cor] of [[c.linhas.referencia, COR_REF], [c.linhas.voce, COR_VOCE]] as const) {
    const xx = x(distanciaNoTempo(linha, t, passo));
    ctx.beginPath();
    ctx.moveTo(xx, a.y);
    ctx.lineTo(xx, a.y + a.h - 2);
    ctx.strokeStyle = cor;
    ctx.lineWidth = 1.5;
    ctx.stroke();
  }
}

/** C.3: as duas faixas do pedal, você e a IA, pela distância. */
function desenharOPedal(ctx: CanvasRenderingContext2D, c: CurvaDoReplay, t: number, a: Area) {
  const x = moldura(ctx, c, a, '');
  const passo = c.passoM ?? 1;
  const faixa = (linha: CurvaDoReplay['linhas']['voce'], y: number, nome: string, cor: string) => {
    for (const [de, ate, pedal] of faixasDoPedal(linha, passo)) {
      ctx.fillStyle = CORES_DO_PEDAL[pedal] ?? CORES_DO_PEDAL[0];
      ctx.fillRect(x(de), y, Math.max(x(ate) - x(de), 1), 10);
    }
    ctx.fillStyle = cor;
    ctx.font = FONTE_PEQUENA;
    ctx.textBaseline = 'top';
    ctx.fillText(nome, a.x + 4, y);
  };
  faixa(c.linhas.voce, a.y + 3, 'você', COR_VOCE);
  faixa(c.linhas.referencia, a.y + 15, c.referencia === 'minha_melhor' ? 'sua' : 'IA', COR_REF);
  cursores(ctx, c, t, a, x);
}

/** C.2: a diferença acumulada desde a entrada, com as separações na freada, na mínima e na saída. */
function desenharADiferenca(ctx: CanvasRenderingContext2D, c: CurvaDoReplay, t: number, a: Area) {
  const x = moldura(ctx, c, a, 'diferença acumulada (s): sobe quando você perde');
  const dif = diferencaAcumulada(c);
  const passo = c.passoM ?? 1;
  const maior = Math.max(0.05, ...dif.map(Math.abs));
  const topo = a.y + 16;
  const meio = topo + (a.h - 20) / 2;
  const y = (v: number) => meio - ((a.h - 22) / 2) * (v / maior);
  ctx.beginPath();
  ctx.moveTo(x(0), meio);
  ctx.lineTo(x((dif.length - 1) * passo), meio);
  ctx.strokeStyle = 'rgba(233,237,242,0.35)';
  ctx.lineWidth = 1;
  ctx.stroke();
  // a área: a perda acima de zero, o ganho abaixo
  for (const [sinal, cor] of [[1, COR_PERDA], [-1, COR_GANHO]] as const) {
    ctx.beginPath();
    ctx.moveTo(x(0), meio);
    dif.forEach((v, i) => ctx.lineTo(x(i * passo), y(sinal > 0 ? Math.max(v, 0) : Math.min(v, 0))));
    ctx.lineTo(x((dif.length - 1) * passo), meio);
    ctx.closePath();
    ctx.fillStyle = cor;
    ctx.fill();
  }
  ctx.beginPath();
  dif.forEach((v, i) => (i ? ctx.lineTo(x(i * passo), y(v)) : ctx.moveTo(x(0), y(v))));
  ctx.strokeStyle = COR_VOCE;
  ctx.lineWidth = 1.5;
  ctx.stroke();
  const s = c.secoes;
  if (s) {
    ctx.font = FONTE_PEQUENA;
    ctx.textAlign = 'center';
    for (const [d, nome] of [[s.freadaM, 'freada'], [s.minimaM, 'mínima'], [s.saidaM, 'saída']] as [number | null, string][]) {
      if (d === null || d === undefined) continue;
      ctx.setLineDash([3, 3]);
      ctx.beginPath();
      ctx.moveTo(x(d), topo);
      ctx.lineTo(x(d), a.y + a.h - 2);
      ctx.strokeStyle = 'rgba(233,237,242,0.5)';
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle = '#b8c1cc';
      ctx.fillText(nome, x(d), a.y + a.h - 13);
    }
    ctx.textAlign = 'left';
  }
  cursores(ctx, c, t, a, x);
}

/** C.1: as duas velocidades pela distância, com as freadas e as mínimas marcadas. */
function desenharAVelocidade(ctx: CanvasRenderingContext2D, c: CurvaDoReplay, t: number, a: Area) {
  const x = moldura(ctx, c, a, 'velocidade (km/h) pela distância (m)');
  const vel = c.velocidades;
  if (!vel) return;
  const passo = c.passoM ?? 1;
  const todas = [...vel.voce, ...vel.referencia];
  const v0 = Math.min(...todas);
  const v1 = Math.max(...todas);
  const y = (v: number) => a.y + a.h - 6 - ((a.h - 24) * (v - v0)) / Math.max(v1 - v0, 1);
  for (const [serie, cor] of [[vel.referencia, COR_REF], [vel.voce, COR_VOCE]] as const) {
    ctx.beginPath();
    serie.forEach((v, i) => (i ? ctx.lineTo(x(i * passo), y(v)) : ctx.moveTo(x(0), y(v))));
    ctx.strokeStyle = cor;
    ctx.lineWidth = 1.5;
    ctx.stroke();
  }
  const naSerie = (serie: number[], d: number) => serie[Math.min(serie.length - 1, Math.max(0, Math.round(d / passo)))];
  // as freadas: um traço vertical em cada linha; as mínimas: um ponto
  for (const [m, serie, cor] of [[c.freadas.voce, vel.voce, COR_VOCE], [c.freadas.referencia, vel.referencia, COR_REF]] as const) {
    if (!m || m.dM === undefined) continue;
    const yy = y(naSerie(serie as number[], m.dM));
    ctx.beginPath();
    ctx.moveTo(x(m.dM), yy - 6);
    ctx.lineTo(x(m.dM), yy + 6);
    ctx.strokeStyle = cor;
    ctx.lineWidth = 3;
    ctx.stroke();
  }
  if (c.minimas) {
    for (const [m, serie, cor] of [[c.minimas.voce, vel.voce, COR_VOCE], [c.minimas.referencia, vel.referencia, COR_REF]] as const) {
      if (m.dM === undefined) continue;
      ctx.beginPath();
      ctx.arc(x(m.dM), y(naSerie(serie as number[], m.dM)), 3.5, 0, 2 * Math.PI);
      ctx.fillStyle = cor;
      ctx.fill();
    }
  }
  cursores(ctx, c, t, a, x);
}

export function desenhar(ctx: CanvasRenderingContext2D, c: CurvaDoReplay, t: number, W: number, H: number, camadas: any) {
  const div = dividirAArea(0, 0, W, H, temVisuais(c));
  desenharACurva(ctx, c, t, div.replay, camadas);
  if (div.pedal) desenharOPedal(ctx, c, t, div.pedal);
  if (div.diferenca) desenharADiferenca(ctx, c, t, div.diferenca);
  if (div.velocidade) desenharAVelocidade(ctx, c, t, div.velocidade);
}

/** A altura do quadro: o replay e, quando a rota traz os dados, os três visuais. */
export function alturaDoQuadro(dados: DadosDoReplay | null): number {
  const com = !!dados && dados.curvas.some(temVisuais);
  return ALTURA_DO_REPLAY + (com ? ALTURAS_DOS_VISUAIS.pedal + ALTURAS_DOS_VISUAIS.diferenca + ALTURAS_DOS_VISUAIS.velocidade : 0);
}

export const ReplayDaCurva: React.FC<{ url: string }> = ({ url }) => {
  const [dados, setDados] = useState<DadosDoReplay | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [vez, setVez] = useState(0);
  const camadas = useLeitura('camadas', lerCamadasDaPista);
  const tela = useRef<HTMLCanvasElement | null>(null);
  const altura = alturaDoQuadro(dados);

  useEffect(() => {
    let vivo = true;
    api.getRadioReplay(url).then((d) => vivo && setDados(d)).catch(() => vivo && setErro('o backend não entregou o replay'));
    return () => {
      vivo = false;
    };
  }, [url]);

  useEffect(() => {
    const cv = tela.current;
    if (!cv || !dados || !dados.curvas.length) return undefined;
    const ctx = cv.getContext('2d');
    if (!ctx) return undefined;
    const W = cv.clientWidth || 360;
    const d = window.devicePixelRatio || 1;
    cv.width = Math.round(W * d);
    cv.height = Math.round(altura * d);
    ctx.setTransform(d, 0, 0, d, 0, 0);
    const curvas = dados.curvas;
    const inicio = performance.now();
    let quadro = 0;
    const passo = () => {
      let t = (performance.now() - inicio) / 1000;
      let i = 0;
      while (i < curvas.length - 1 && t > curvas[i].duracaoS + PAUSA_NO_FIM_S) {
        t -= curvas[i].duracaoS + PAUSA_NO_FIM_S;
        i += 1;
      }
      ctx.setTransform(d, 0, 0, d, 0, 0);
      ctx.clearRect(0, 0, W, altura);
      desenhar(ctx, curvas[i], Math.min(t, curvas[i].duracaoS), W, altura, camadas.dado);
      if (i < curvas.length - 1 || t < curvas[i].duracaoS + PAUSA_NO_FIM_S) quadro = requestAnimationFrame(passo);
    };
    quadro = requestAnimationFrame(passo);
    return () => cancelAnimationFrame(quadro);
  }, [dados, vez, camadas.dado, altura]);

  if (erro) return <p className="texto-fraco" style={{ margin: 0 }}>Replay: {erro}.</p>;
  if (!dados) return <p className="texto-fraco" style={{ margin: 0 }}>Lendo o replay da curva…</p>;
  return (
    <div className="replay-da-curva" style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <canvas ref={tela} style={{ width: '100%', height: altura, borderRadius: 8 }}
        aria-label="Replay da curva: você e a referência, com o pedal, a diferença acumulada e a velocidade" />
      <button type="button" className="botao botao--pequeno" style={{ alignSelf: 'flex-start' }} onClick={() => setVez((v) => v + 1)}>
        Repetir o replay
      </button>
    </div>
  );
};
