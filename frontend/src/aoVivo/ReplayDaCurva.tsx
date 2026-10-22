/**
 * O replay da curva na tela Ao vivo (pedido 36, Parte E.5): o engenheiro mostra o que diz.
 *
 * Sob o cartão da análise e da frase do coach com causa: a curva vista de cima, sobre a
 * pista tratada (as camadas do cache que o mapa do app desenha), com as duas linhas
 * ("você" e "IA (referência)"), os dois carros andando cada um no seu próprio tempo a
 * partir da mesma entrada, as duas freadas com a distância, as duas mínimas com o valor,
 * o traçado no ponto da mínima da referência e o tempo perdido na curva. Toca cada curva
 * citada uma vez; o botão repete.
 */
import React, { useEffect, useRef, useState } from 'react';
import { api } from '../api/client';
import { drawTrackSurface } from '../components/map/OverlayRenderer';
import { lerCamadasDaPista, useLeitura } from '../volta/dados';
import { transformarCamadas } from '../volta/projecao';
import {
  QuadroDeRotulos, cameraDaCurva, posicaoNoTempo, textoDaFreada, textoDaMinima, textoDaPerda, textoDoTracado,
  type CurvaDoReplay, type DadosDoReplay, type LugarDoRotulo,
} from './replay';

const ALTURA = 250;
const PAUSA_NO_FIM_S = 1.2;      // o fim de cada curva fica parado um pouco, antes da próxima
const COR_VOCE = '#e10600';
const COR_REF = 'rgba(233,237,242,0.9)';

function desenhar(ctx: CanvasRenderingContext2D, c: CurvaDoReplay, t: number, W: number, H: number, camadas: any) {
  const cam = cameraDaCurva(c, W, H);
  ctx.fillStyle = '#111214';
  ctx.fillRect(0, 0, W, H);
  if (camadas) {
    // A pista tratada, na mesma câmera: tela = A + k (R base(x, z) − rc).
    ctx.save();
    ctx.translate(cam.ax, cam.ay);
    ctx.scale(cam.k, cam.k);
    ctx.translate(-cam.rcx, -cam.rcy);
    ctx.rotate(cam.ang);
    transformarCamadas(ctx);
    drawTrackSurface(ctx, camadas, null, cam.k);
    ctx.restore();
  }
  const linha = (pts: CurvaDoReplay['linhas']['voce'], cor: string, largura: number) => {
    ctx.beginPath();
    pts.forEach((p, i) => {
      const [x, y] = cam.tela(p[0], p[1]);
      if (i) ctx.lineTo(x, y);
      else ctx.moveTo(x, y);
    });
    ctx.strokeStyle = cor;
    ctx.lineWidth = largura;
    ctx.lineJoin = 'round';
    ctx.stroke();
  };
  linha(c.linhas.referencia, COR_REF, 2.5);
  linha(c.linhas.voce, COR_VOCE, 2.5);
  // Os pontos que os rótulos não cobrem: os dois carros, as freadas, as mínimas e o traçado.
  const q = new QuadroDeRotulos([2, 26, W - 2, H - 2]);
  const [rx, rz] = posicaoNoTempo(c.linhas.referencia, t);
  const [vx, vz] = posicaoNoTempo(c.linhas.voce, t);
  const [rsx, rsy] = cam.tela(rx, rz);
  const [vsx, vsy] = cam.tela(vx, vz);
  const [mvx, mvy] = cam.tela(c.minimas.voce.x, c.minimas.voce.z);
  const [mrx, mry] = cam.tela(c.minimas.referencia.x, c.minimas.referencia.z);
  const [tvx, tvy] = cam.tela(c.tracado.voce[0], c.tracado.voce[1]);
  const [trx, try_] = cam.tela(c.tracado.referencia[0], c.tracado.referencia[1]);
  q.ocupar(rsx, rsy, 9);
  q.ocupar(vsx, vsy, 9);
  for (const [x, y] of [[mvx, mvy], [mrx, mry], [tvx, tvy], [trx, try_]]) q.ocupar(x, y, 5);
  ctx.font = '600 11px "Barlow", "Segoe UI", sans-serif';
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
  // As freadas: um traço atravessando cada linha, e a distância entre elas.
  const traco = (m: { x: number; z: number } | null, cor: string) => {
    if (!m) return null;
    const [x, y] = cam.tela(m.x, m.z);
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
  // O traçado: uma seta entre as duas linhas, no ponto da mínima da referência.
  if (Math.hypot(tvx - trx, tvy - try_) > 2) {
    ctx.beginPath();
    ctx.moveTo(trx, try_);
    ctx.lineTo(tvx, tvy);
    ctx.strokeStyle = '#f5c542';
    ctx.lineWidth = 1.5;
    ctx.stroke();
    const a = Math.atan2(tvy - try_, tvx - trx);
    ctx.beginPath();
    ctx.moveTo(tvx, tvy);
    ctx.lineTo(tvx - 7 * Math.cos(a - 0.5), tvy - 7 * Math.sin(a - 0.5));
    ctx.lineTo(tvx - 7 * Math.cos(a + 0.5), tvy - 7 * Math.sin(a + 0.5));
    ctx.closePath();
    ctx.fillStyle = '#f5c542';
    ctx.fill();
  }
  rotulo(textoDoTracado(c.tracado), (tvx + trx) / 2, (tvy + try_) / 2, '#f5c542', 'abaixo');
  // As mínimas, no ponto de cada uma.
  for (const [x, y, cor] of [[mvx, mvy, COR_VOCE], [mrx, mry, COR_REF]] as [number, number, string][]) {
    ctx.beginPath();
    ctx.arc(x, y, 3.5, 0, 2 * Math.PI);
    ctx.fillStyle = cor;
    ctx.fill();
  }
  rotulo(`mínima ${textoDaMinima(c.minimas.voce.kmh)}`, mvx, mvy, COR_VOCE, 'esquerda');
  rotulo(`mínima ${textoDaMinima(c.minimas.referencia.kmh)}`, mrx, mry, COR_REF, 'direita');
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
  // O alto: a curva, a volta e o tempo perdido.
  ctx.fillStyle = 'rgba(8,9,11,0.8)';
  ctx.fillRect(0, 0, W, 24);
  ctx.textBaseline = 'alphabetic';
  ctx.fillStyle = '#f2f4f5';
  ctx.font = '600 12px "Barlow", "Segoe UI", sans-serif';
  ctx.fillText(`${c.curva}, ${c.lado}${c.volta ? ` · volta ${c.volta}` : ''} · ${textoDaPerda(c.perdaS)}`, 10, 16);
}

export const ReplayDaCurva: React.FC<{ url: string }> = ({ url }) => {
  const [dados, setDados] = useState<DadosDoReplay | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [vez, setVez] = useState(0);
  const camadas = useLeitura('camadas', lerCamadasDaPista);
  const tela = useRef<HTMLCanvasElement | null>(null);

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
    cv.height = Math.round(ALTURA * d);
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
      desenhar(ctx, curvas[i], Math.min(t, curvas[i].duracaoS), W, ALTURA, camadas.dado);
      if (i < curvas.length - 1 || t < curvas[i].duracaoS + PAUSA_NO_FIM_S) quadro = requestAnimationFrame(passo);
    };
    quadro = requestAnimationFrame(passo);
    return () => cancelAnimationFrame(quadro);
  }, [dados, vez, camadas.dado]);

  if (erro) return <p className="texto-fraco" style={{ margin: 0 }}>Replay: {erro}.</p>;
  if (!dados) return <p className="texto-fraco" style={{ margin: 0 }}>Lendo o replay da curva…</p>;
  return (
    <div className="replay-da-curva" style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <canvas ref={tela} style={{ width: '100%', height: ALTURA, borderRadius: 8 }} aria-label="Replay da curva: você e a referência" />
      <button type="button" className="botao botao--pequeno" style={{ alignSelf: 'flex-start' }} onClick={() => setVez((v) => v + 1)}>
        Repetir o replay
      </button>
    </div>
  );
};
