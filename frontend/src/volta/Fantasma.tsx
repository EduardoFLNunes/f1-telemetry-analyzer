/**
 * "Volta com fantasma" (pedido 30; `docs/dashboard_visoes.md`, seção 8), como
 * no protótipo A:
 *
 * - câmera próxima que acompanha o carro (80, 150 ou 400 m; pode girar com ele);
 * - traçado desde o início da volta, colorido pelo pedal (freio ≥ 0,15 em
 *   vermelho, acelerador ≥ 0,9 em verde, o resto em amarelo);
 * - fantasma da referência posicionado pelo tempo, por curva (recomeça junto no
 *   início de cada curva) ou na volta inteira; fora da tela, uma seta com a
 *   distância;
 * - relevo no canto superior direito, com a altitude e a inclinação no ponto
 *   do carro, e a pista inteira no inferior direito;
 * - a leitura dos dois carros e o replay.
 *
 * A pista desenhada são as camadas do cache que o mapa do app usa
 * (`drawTrackSurface`): asfalto, pintura classificada e zebras. As posições são
 * a linha central oficial mais o deslocamento lateral do store v2.
 *
 * Pedido 35 (Parte D): a pista é desenhada uma vez num bitmap (`camadaDaPista`) e
 * reaproveitada a cada quadro; ela só é refeita quando o zoom ou o tamanho mudam.
 * Na tela Ao vivo (`fonteAoVivo`), o desenho roda a cada quadro, com a posição que a
 * fonte dá (o carro andando entre duas posições), sem o React renderizar de novo.
 */
import React, { useCallback, useEffect, useMemo, useRef } from 'react';
import clsx from 'clsx';
import { drawTrackSurface } from '../components/map/OverlayRenderer';
import { Segmentado } from '../components/ui/base';
import { useEstadoDaVolta } from './estado';
import type { Geometria, VoltaDoStore } from './dados';
import { CORES_DO_PEDAL, misturar, token } from './cores';
import {
  curvaEm,
  estadoDoFantasma,
  pedalEm,
  sNoTempo,
  tempoEm,
  valorEm,
  type Curva,
  type Grade,
  type Pedal,
} from './medidas';
import { nf, numeroDaVolta, sg, tempo } from './formato';
import { linhaCentral, posicaoEm, rotuloDaCurva, tracadoDaVolta, transformarCamadas, type Ponto } from './projecao';

type Props = {
  grade: Grade;
  geometria: Geometria;
  curvas: Curva[];
  volta: VoltaDoStore;
  voltaRef: VoltaDoStore;
  referencia: 'ia' | 'melhor';
  /** As camadas da pista do cache (`/api/track/geometry`); sem elas, a linha central. */
  camadas: any | null;
  /** O que vai embaixo do replay (as frases do coach). */
  children?: React.ReactNode;
  /** Pedido 31: a volta em andamento (tela Ao vivo), sem o replay. */
  aoVivo?: boolean;
  /** Pedido 35: a posição a cada quadro e a versão dos dados da volta ao vivo. */
  fonteAoVivo?: React.MutableRefObject<FonteAoVivo | null>;
};

/** Pedido 35: o que a tela Ao vivo entrega ao desenho, a cada quadro, fora do React. */
export type FonteAoVivo = { s: () => number; versao: () => number };

// O bitmap da pista inteira fica com no máximo isto de pixels (um pouco menos de 100 MB);
// perto disso, a aproximação de 80 m usa a pista um pouco ampliada.
const PIXELS_DA_PISTA = 24e6;
const MARGEM_DA_PISTA_M = 120;

const NOME_DO_PEDAL: Record<Pedal, string> = { freio: 'FREANDO', acelerador: 'ACELERANDO', parcial: 'PARCIAL' };

function ajustar(cv: HTMLCanvasElement) {
  const W = cv.clientWidth;
  const H = cv.clientHeight;
  const d = window.devicePixelRatio || 1;
  if (cv.width !== Math.round(W * d) || cv.height !== Math.round(H * d)) {
    cv.width = Math.round(W * d);
    cv.height = Math.round(H * d);
  }
  const ctx = cv.getContext('2d')!;
  ctx.setTransform(d, 0, 0, d, 0, 0);
  ctx.clearRect(0, 0, W, H);
  return { ctx, W, H };
}

const voltaAngulo = (a: number) => {
  let x = a;
  while (x > Math.PI) x -= 2 * Math.PI;
  while (x < -Math.PI) x += 2 * Math.PI;
  return x;
};

function rotulo(ctx: CanvasRenderingContext2D, texto: string, x: number, y: number) {
  ctx.lineWidth = 4;
  ctx.strokeStyle = 'rgba(8,9,11,0.9)';
  ctx.strokeText(texto, x, y);
  ctx.fillText(texto, x, y);
}

export const Fantasma: React.FC<Props> = ({ grade: g, geometria: geo, curvas, volta, voltaRef: ref, referencia, camadas, children, aoVivo = false, fonteAoVivo }) => {
  const principal = useRef<HTMLCanvasElement>(null);
  const relevo = useRef<HTMLCanvasElement>(null);
  const mini = useRef<HTMLCanvasElement>(null);
  const textoDoRelevo = useRef<HTMLSpanElement>(null);
  const angulo = useRef<number | null>(null);
  const caixa = useRef<HTMLDivElement>(null);

  // A roda do mouse dentro da visão aproxima e afasta, sem rolar a página. O `onWheel` do React é
  // passivo e não consegue impedir a rolagem; por isso o ouvinte nativo, com `passive: false`.
  useEffect(() => {
    const el = caixa.current;
    if (!el) return undefined;
    const aoRolar = (ev: WheelEvent) => {
      ev.preventDefault();
      const z = useEstadoDaVolta.getState().zoom;
      useEstadoDaVolta.getState().setZoom(Math.max(40, Math.min(1200, z * (ev.deltaY > 0 ? 1.15 : 1 / 1.15))));
    };
    el.addEventListener('wheel', aoRolar, { passive: false });
    return () => el.removeEventListener('wheel', aoRolar);
  }, []);
  const modo = useEstadoDaVolta((e) => e.modo);
  const zoom = useEstadoDaVolta((e) => e.zoom);
  const girar = useEstadoDaVolta((e) => e.girar);
  const { setModo, setZoom, setGirar } = useEstadoDaVolta.getState();

  const central = useMemo(() => linhaCentral(geo), [geo]);
  const trVolta = useMemo(() => tracadoDaVolta(geo, volta.linhas.lateral), [geo, volta]);
  const trRef = useMemo(() => tracadoDaVolta(geo, ref.linhas.lateral), [geo, ref]);
  const pedais = useMemo(() => {
    const doPonto = (v: VoltaDoStore) => v.linhas.freio.map((f, i) => (Number(f) >= 0.15 ? 'freio' : Number(v.linhas.acelerador[i]) >= 0.9 ? 'acelerador' : 'parcial') as Pedal);
    return { volta: doPonto(volta), ref: doPonto(ref) };
  }, [volta, ref]);
  const rotuloRef = referencia === 'ia' ? 'IA' : 'Sua melhor';

  // Pedido 35: na tela Ao vivo os dados da volta mudam no mesmo objeto a cada leitura; o traçado e
  // os pedais da volta são refeitos quando a versão dos dados muda, sem renderizar de novo.
  const vivoTr = useRef<{ versao: number; tr: { x: number[]; y: number[] }; ped: Pedal[] } | null>(null);
  const tracadoAtual = () => {
    const fonte = fonteAoVivo?.current;
    if (!fonte) return { tr: trVolta, ped: pedais.volta };
    const versao = fonte.versao();
    if (!vivoTr.current || vivoTr.current.versao !== versao) {
      const l = volta.linhas;
      vivoTr.current = {
        versao,
        tr: tracadoDaVolta(geo, l.lateral),
        ped: l.freio.map((f, i) => (Number(f) >= 0.15 ? 'freio' : Number(l.acelerador[i]) >= 0.9 ? 'acelerador' : 'parcial') as Pedal),
      };
    }
    return vivoTr.current;
  };

  // Pedido 35: a pista desenhada uma vez, num bitmap do circuito inteiro, refeito só quando o zoom
  // ou o tamanho mudam (a escala do bitmap anda em degraus de raiz de 2).
  const pistaPronta = useRef<{ chave: string; tela: HTMLCanvasElement; x0: number; y0: number; k: number } | null>(null);
  useEffect(() => {
    pistaPronta.current = null;
  }, [camadas, central]);
  const camadaDaPista = (sc: number, W: number, H: number, zoomAtual: number) => {
    if (!camadas) return null;
    const d = window.devicePixelRatio || 1;
    let x0 = Infinity;
    let x1 = -Infinity;
    let y0 = Infinity;
    let y1 = -Infinity;
    for (let i = 0; i < central.n; i += 1) {
      x0 = Math.min(x0, central.cx[i]);
      x1 = Math.max(x1, central.cx[i]);
      y0 = Math.min(y0, central.cy[i]);
      y1 = Math.max(y1, central.cy[i]);
    }
    x0 -= MARGEM_DA_PISTA_M;
    y0 -= MARGEM_DA_PISTA_M;
    x1 += MARGEM_DA_PISTA_M;
    y1 += MARGEM_DA_PISTA_M;
    const kMax = Math.sqrt(PIXELS_DA_PISTA / ((x1 - x0) * (y1 - y0)));
    const k = Math.min(kMax, 2 ** (Math.round(Math.log2(sc * d) * 2) / 2));
    const chave = `${k.toFixed(4)}|${W}x${H}|${zoomAtual}`;
    if (pistaPronta.current?.chave === chave) return pistaPronta.current;
    const tela = document.createElement('canvas');
    tela.width = Math.ceil((x1 - x0) * k);
    tela.height = Math.ceil((y1 - y0) * k);
    const c = tela.getContext('2d');
    if (!c) return null;
    c.setTransform(k, 0, 0, k, -x0 * k, -y0 * k);
    transformarCamadas(c);
    drawTrackSurface(c, camadas, null, sc);
    pistaPronta.current = { chave, tela, x0, y0, k };
    return pistaPronta.current;
  };
  const ultimoCanto = useRef(0);

  const desenhar = useCallback(() => {
    const cv = principal.current;
    if (!cv) return;
    const est = useEstadoDaVolta.getState();
    const fonte = fonteAoVivo?.current;
    const sAgora = fonte ? fonte.s() : est.s ?? 0;
    const f = estadoDoFantasma(g, volta.linhas, ref.linhas, curvas, sAgora, est.modo);
    const { ctx, W, H } = ajustar(cv);
    const passo = g.passo;
    const { tr: trV, ped: pedV } = tracadoAtual();
    const carro = posicaoEm(trV, passo, f.s);
    const fantasma = posicaoEm(trRef, passo, f.sFantasma);
    const i = Math.round(f.s / passo) % central.n;
    const i2 = (i + 4) % central.n;
    const alvo = est.girar ? -Math.PI / 2 - Math.atan2(central.cy[i2] - central.cy[i], central.cx[i2] - central.cx[i]) : 0;
    angulo.current = angulo.current === null || !est.tocando ? alvo : angulo.current + voltaAngulo(alvo - angulo.current) * 0.12;
    const ang = angulo.current;
    const sc = Math.min(W, H) / est.zoom;
    const cxs = W < 600 ? W * 0.5 : W * 0.42;
    const cys = W < 600 ? H * 0.52 : H * 0.44;
    const cs = Math.cos(ang);
    const sn = Math.sin(ang);
    const naTela = (p: Ponto): Ponto => {
      const dx = p[0] - carro[0];
      const dy = p[1] - carro[1];
      return [cxs + sc * (dx * cs - dy * sn), cys + sc * (dx * sn + dy * cs)];
    };

    ctx.save();
    ctx.translate(cxs, cys);
    ctx.rotate(ang);
    ctx.scale(sc, sc);
    ctx.translate(-carro[0], -carro[1]);
    const pista = camadaDaPista(sc, W, H, est.zoom);
    if (pista) {
      ctx.drawImage(pista.tela, pista.x0, pista.y0, pista.tela.width / pista.k, pista.tela.height / pista.k);
    } else {
      ctx.beginPath();
      central.cx.forEach((x, k) => (k ? ctx.lineTo(x, central.cy[k]) : ctx.moveTo(x, central.cy[k])));
      ctx.closePath();
      ctx.strokeStyle = token('--pista-desenho', '#2a2f36');
      ctx.lineWidth = 14;
      ctx.stroke();
    }
    if (est.curva) {
      const c = curvas.find((k) => k.codigo === est.curva);
      if (c) {
        const a0 = Math.round(c.trecho[0] / passo);
        const b0 = Math.round(c.trecho[1] / passo) % central.n;
        ctx.beginPath();
        for (let q = a0 % central.n, primeiro = true; ; q = (q + 1) % central.n) {
          if (primeiro) {
            ctx.moveTo(central.cx[q], central.cy[q]);
            primeiro = false;
          } else ctx.lineTo(central.cx[q], central.cy[q]);
          if (q === b0) break;
        }
        ctx.strokeStyle = 'rgba(233,237,242,0.18)';
        ctx.lineWidth = 14;
        ctx.stroke();
      }
    }
    const tracar = (tr: { x: number[]; y: number[] }, ped: Pedal[], s0: number, s1: number, alfa: number, largura: number) => {
      const n = tr.x.length;
      const j0 = Math.max(0, Math.floor(s0 / passo));
      const j1 = Math.min(n - 1, Math.floor(s1 / passo));
      if (j1 <= j0) return;
      const fim = posicaoEm(tr, passo, s1);
      ctx.globalAlpha = alfa;
      ctx.lineWidth = largura;
      ctx.lineCap = 'round';
      ctx.lineJoin = 'round';
      let j = j0;
      while (j < j1) {
        const k = ped[j];
        let jj = j;
        ctx.beginPath();
        ctx.moveTo(tr.x[j], tr.y[j]);
        while (jj < j1 && ped[jj] === k) {
          jj += 1;
          ctx.lineTo(tr.x[jj], tr.y[jj]);
        }
        if (jj >= j1) ctx.lineTo(fim[0], fim[1]);
        ctx.strokeStyle = CORES_DO_PEDAL[k]();
        ctx.stroke();
        j = jj;
      }
      ctx.globalAlpha = 1;
    };
    tracar(trRef, pedais.ref, est.modo === 'curva' ? f.s0 : 0, f.sFantasma, 0.6, Math.max(0.7, 3.5 / sc));
    tracar(trV, pedV, 0, f.s, 1, Math.max(0.9, 5 / sc));
    ctx.restore();

    const texto = token('--texto-1', '#f2f4f5');
    ctx.font = `600 11px ${token('--fonte-dado', 'monospace')}`;
    ctx.textAlign = 'center';
    curvas.forEach((c) => {
      const p = naTela(rotuloDaCurva(geo, c.apice, c.lado));
      if (p[0] > 8 && p[0] < W - 8 && p[1] > 8 && p[1] < H - 8) {
        ctx.fillStyle = 'rgba(233,237,242,0.75)';
        rotulo(ctx, c.codigo, p[0], p[1]);
      }
    });
    const gs = naTela(fantasma);
    const dentro = gs[0] > 14 && gs[0] < W - 14 && gs[1] > 14 && gs[1] < H - 14;
    if (dentro) {
      ctx.beginPath();
      ctx.arc(gs[0], gs[1], 8, 0, 2 * Math.PI);
      ctx.fillStyle = 'rgba(8,9,11,0.6)';
      ctx.fill();
      ctx.lineWidth = 2.5;
      ctx.strokeStyle = token('--fantasma', 'rgba(233,237,242,0.9)');
      ctx.stroke();
      ctx.fillStyle = texto;
      rotulo(ctx, rotuloRef, gs[0], gs[1] - 14);
    } else {
      const cxm = Math.max(18, Math.min(W - 18, gs[0]));
      const cym = Math.max(18, Math.min(H - 18, gs[1]));
      ctx.save();
      ctx.translate(cxm, cym);
      ctx.rotate(Math.atan2(gs[1] - cys, gs[0] - cxs));
      ctx.beginPath();
      ctx.moveTo(8, 0);
      ctx.lineTo(-6, -6);
      ctx.lineTo(-6, 6);
      ctx.closePath();
      ctx.fillStyle = token('--fantasma', 'rgba(233,237,242,0.9)');
      ctx.fill();
      ctx.restore();
      const dm = f.sFantasma - f.s;
      ctx.fillStyle = texto;
      ctx.textAlign = cxm > W / 2 ? 'right' : 'left';
      rotulo(ctx, `${rotuloRef} · ${nf(Math.abs(dm), 0)} m ${dm >= 0 ? 'à frente' : 'atrás'}`, cxm + (cxm > W / 2 ? -12 : 12), cym + (cym > H / 2 ? -12 : 18));
    }
    ctx.beginPath();
    ctx.arc(cxs, cys, 8.5, 0, 2 * Math.PI);
    ctx.fillStyle = token('--voce', '#ffffff');
    ctx.fill();
    ctx.lineWidth = 2.5;
    ctx.strokeStyle = token('--vermelho', '#e10600');
    ctx.stroke();
    ctx.fillStyle = texto;
    ctx.textAlign = 'center';
    rotulo(ctx, `Você · V${numeroDaVolta(volta.lapId)}`, cxs, cys + 26);

    // Ao vivo, os cantos (relevo e pista inteira) acompanham até 10 vezes por segundo.
    const agora = performance.now();
    if (!fonte || agora - ultimoCanto.current >= 100) {
      ultimoCanto.current = agora;
      desenharRelevo(f.s, f.sFantasma);
      desenharMini(f.s, f.sFantasma, carro, fantasma);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [g, geo, curvas, volta, ref, camadas, central, trVolta, trRef, pedais, rotuloRef, fonteAoVivo]);

  const desenharRelevo = (s: number, sFantasma: number) => {
    const cv = relevo.current;
    if (!cv) return;
    const { ctx, W, H } = ajustar(cv);
    const el = geo.elevacaoM;
    const n = central.n;
    if (!el) {
      if (textoDoRelevo.current) textoDoRelevo.current.textContent = 'sem a altitude da geometria oficial';
      return;
    }
    const EX = 3.2;
    const INCL = 0.5;
    const emin = Math.min(...el);
    const umin = Math.min(...central.cx);
    const umax = Math.max(...central.cx);
    const proj = (i: number, chao: boolean): Ponto => [central.cx[i], central.cy[i] * INCL - (chao ? 0 : el[i] - emin) * EX];
    let ymin = Infinity;
    let ymax = -Infinity;
    for (let i = 0; i < n; i += 4) {
      const a = proj(i, false);
      const b = proj(i, true);
      ymin = Math.min(ymin, a[1], b[1]);
      ymax = Math.max(ymax, a[1], b[1]);
    }
    const padT = 24;
    const padB = 22;
    const padX = 16;
    const k = Math.min((W - 2 * padX) / (umax - umin), (H - padT - padB) / (ymax - ymin));
    const ox = (W - k * (umax - umin)) / 2 - k * umin;
    const oy = padT + (H - padT - padB - k * (ymax - ymin)) / 2 - k * ymin;
    const P = (i: number, chao: boolean): Ponto => {
      const p = proj(i, chao);
      return [ox + k * p[0], oy + k * p[1]];
    };
    ctx.beginPath();
    for (let j = 0; j <= n; j += 3) {
      const q = P(j % n, true);
      if (!j) ctx.moveTo(q[0], q[1]);
      else ctx.lineTo(q[0], q[1]);
    }
    ctx.strokeStyle = token('--superficie-3', '#1d2126');
    ctx.lineWidth = 3;
    ctx.stroke();
    ctx.lineWidth = 3.2;
    ctx.lineCap = 'round';
    const plano = token('--relevo-plano', '#8a96a3');
    const subida = token('--relevo-subida', '#ff9f43');
    const descida = token('--relevo-descida', '#4c8dff');
    for (let m = 0; m < n; m += 3) {
      const n2 = (m + 3) % n;
      const t = Math.max(-1, Math.min(1, (el[n2] - el[m]) / (3 * g.passo) / 0.06));
      ctx.strokeStyle = t >= 0 ? misturar(plano, subida, t) : misturar(plano, descida, -t);
      const a1 = P(m, false);
      const b1 = P(n2, false);
      ctx.beginPath();
      ctx.moveTo(a1[0], a1[1]);
      ctx.lineTo(b1[0], b1[1]);
      ctx.stroke();
    }
    const ponto = (sp: number, cheio: string, borda: string) => {
      const ii = Math.round(sp / g.passo) % n;
      const p = P(ii, false);
      const q = P(ii, true);
      ctx.beginPath();
      ctx.moveTo(q[0], q[1]);
      ctx.lineTo(p[0], p[1]);
      ctx.strokeStyle = 'rgba(233,237,242,0.35)';
      ctx.lineWidth = 1;
      ctx.stroke();
      ctx.beginPath();
      ctx.arc(p[0], p[1], 5, 0, 2 * Math.PI);
      ctx.fillStyle = cheio;
      ctx.fill();
      ctx.lineWidth = 2;
      ctx.strokeStyle = borda;
      ctx.stroke();
    };
    ponto(sFantasma, 'rgba(8,9,11,0.6)', token('--fantasma', 'rgba(233,237,242,0.9)'));
    ponto(s, token('--voce', '#ffffff'), token('--vermelho', '#e10600'));
    const ic = Math.round(s / g.passo) % n;
    const ia = (ic - 5 + n) % n;
    const ib = (ic + 5) % n;
    const inclinacao = ((el[ib] - el[ia]) / (10 * g.passo)) * 100;
    if (textoDoRelevo.current) textoDoRelevo.current.textContent = `altitude ${nf(el[ic] - emin, 1)} m · inclinação ${sg(inclinacao, 1)}%`;
  };

  const desenharMini = (s: number, sFantasma: number, carro: Ponto, fantasma: Ponto) => {
    const cv = mini.current;
    if (!cv) return;
    const { ctx, W, H } = ajustar(cv);
    const n = central.n;
    const umin = Math.min(...central.cx);
    const umax = Math.max(...central.cx);
    const vmin = Math.min(...central.cy);
    const vmax = Math.max(...central.cy);
    const pt = 18;
    const pd = 10;
    const k = Math.min((W - 2 * pd) / (umax - umin), (H - pt - pd) / (vmax - vmin));
    const ox = (W - k * (umax - umin)) / 2 - k * umin;
    const oy = pt + (H - pt - pd - k * (vmax - vmin)) / 2 - k * vmin;
    const P = (i: number): Ponto => [ox + k * central.cx[i], oy + k * central.cy[i]];
    ctx.beginPath();
    for (let j = 0; j <= n; j += 3) {
      const q = P(j % n);
      if (!j) ctx.moveTo(q[0], q[1]);
      else ctx.lineTo(q[0], q[1]);
    }
    ctx.strokeStyle = 'rgba(233,237,242,0.55)';
    ctx.lineWidth = 2;
    ctx.stroke();
    const c = curvaEm(curvas, s);
    if (c) {
      const a = Math.round(c.trecho[0] / g.passo) % n;
      const b = Math.round(c.trecho[1] / g.passo) % n;
      ctx.beginPath();
      for (let q = a, primeiro = true; ; q = (q + 1) % n) {
        const pp = P(q);
        if (primeiro) {
          ctx.moveTo(pp[0], pp[1]);
          primeiro = false;
        } else ctx.lineTo(pp[0], pp[1]);
        if (q === b) break;
      }
      ctx.strokeStyle = token('--texto-1', '#f2f4f5');
      ctx.lineWidth = 4;
      ctx.stroke();
    }
    const s0 = P(0);
    ctx.fillStyle = token('--texto-1', '#f2f4f5');
    ctx.fillRect(s0[0] - 1, s0[1] - 5, 2, 10);
    const marca = (p: Ponto, cheio: string, borda: string) => {
      ctx.beginPath();
      ctx.arc(ox + k * p[0], oy + k * p[1], 4.5, 0, 2 * Math.PI);
      ctx.fillStyle = cheio;
      ctx.fill();
      ctx.lineWidth = 2;
      ctx.strokeStyle = borda;
      ctx.stroke();
    };
    marca(fantasma, 'rgba(8,9,11,0.6)', token('--fantasma', 'rgba(233,237,242,0.9)'));
    marca(carro, token('--voce', '#ffffff'), token('--vermelho', '#e10600'));
    void sFantasma;
  };

  // Redesenha quando o cursor, o modo ou a câmera mudam, e quando a janela muda de tamanho. Ao vivo
  // (pedido 35), a cada quadro da tela.
  useEffect(() => {
    let quadro = 0;
    const continuo = Boolean(fonteAoVivo);
    const laco = () => {
      desenhar();
      quadro = requestAnimationFrame(laco);
    };
    const pedir = () => {
      if (continuo) return;
      cancelAnimationFrame(quadro);
      quadro = requestAnimationFrame(desenhar);
    };
    if (continuo) quadro = requestAnimationFrame(laco);
    else pedir();
    const desassinar = useEstadoDaVolta.subscribe(pedir);
    const ro = new ResizeObserver(pedir);
    if (principal.current) ro.observe(principal.current);
    return () => {
      cancelAnimationFrame(quadro);
      desassinar();
      ro.disconnect();
    };
  }, [desenhar, fonteAoVivo]);

  return (
    <section className="vidro painel" aria-labelledby="fantasma-titulo">
      <div className="painel-cabeca">
        <h2 id="fantasma-titulo" className="titulo-painel">Volta com fantasma</h2>
        <div className="chips" style={{ alignItems: 'center' }}>
          <Segmentado rotulo="Fantasma" opcoes={[{ id: 'curva', texto: 'Fantasma por curva' }, { id: 'volta', texto: 'Volta inteira' }]} valor={modo} aoMudar={setModo} />
          <Segmentado
            rotulo="Aproximação"
            opcoes={[80, 150, 400].map((z) => ({ id: String(z), texto: `${z} m` }))}
            valor={String(Math.round(zoom))}
            aoMudar={(z) => setZoom(Number(z))}
          />
          <button type="button" className={clsx('chip')} aria-pressed={girar} onClick={() => setGirar(!girar)}>
            Girar com o carro
          </button>
        </div>
      </div>
      <div
        className="fantasma"
        ref={caixa}
      >
        <canvas ref={principal} className="fantasma-principal" aria-label="Visão próxima da volta, com o fantasma da referência" />
        <TituloDoFantasma grade={g} volta={volta} ref_={ref} curvas={curvas} referencia={referencia} aoVivo={aoVivo} />
        <div className="fantasma-canto fantasma-relevo">
          <canvas ref={relevo} aria-label="Relevo da pista" />
          <span className="fantasma-rotulo">Relevo</span>
          <span className="fantasma-leitura" ref={textoDoRelevo} />
        </div>
        <div className="fantasma-canto fantasma-mini">
          <canvas ref={mini} aria-label="Pista inteira" />
          <span className="fantasma-rotulo">Pista inteira</span>
        </div>
        <Hud grade={g} volta={volta} ref_={ref} curvas={curvas} referencia={referencia} />
      </div>
      <div className="legenda">
        <span><i className="amostra" style={{ background: 'var(--freio)' }} />freio</span>
        <span><i className="amostra" style={{ background: 'var(--acelerador)' }} />acelerador</span>
        <span><i className="amostra" style={{ background: 'var(--parcial)' }} />acelerador parcial ou sem pedal</span>
        <span><i className="ponto" style={{ border: '2px solid var(--fantasma)', width: 10, height: 10 }} />fantasma</span>
      </div>
      {!aoVivo && <Replay grade={g} volta={volta} ref_={ref} curvas={curvas} />}
      {children}
    </section>
  );
};

type PropsDaLeitura = { grade: Grade; volta: VoltaDoStore; ref_: VoltaDoStore; curvas: Curva[]; referencia?: 'ia' | 'melhor'; aoVivo?: boolean };

function TituloDoFantasma({ grade: g, volta, curvas, referencia, aoVivo }: PropsDaLeitura) {
  const s = useEstadoDaVolta((e) => e.s) ?? 0;
  const modo = useEstadoDaVolta((e) => e.modo);
  const c = curvaEm(curvas, s);
  return (
    <div className="fantasma-titulo">
      <b>{aoVivo ? 'Ao vivo: volta' : 'Volta'} {numeroDaVolta(volta.lapId)} contra a {referencia === 'ia' ? 'volta da IA' : 'sua melhor'}</b>
      <span>{modo === 'curva' ? 'fantasma por curva' : 'fantasma na volta inteira'} · {nf(s, 0)} m{c ? ` · ${c.codigo}` : ''}</span>
      {void g}
    </div>
  );
}

function Hud({ grade: g, volta, ref_: ref, curvas, referencia }: PropsDaLeitura) {
  const s = useEstadoDaVolta((e) => e.s) ?? 0;
  const modo = useEstadoDaVolta((e) => e.modo);
  const f = estadoDoFantasma(g, volta.linhas, ref.linhas, curvas, s, modo);
  const pv = pedalEm(g, volta.linhas, f.s);
  const pr = pedalEm(g, ref.linhas, f.sFantasma);
  const cor = (p: Pedal) => `var(--${p === 'freio' ? 'freio' : p === 'acelerador' ? 'acelerador' : 'parcial'})`;
  return (
    <div className="fantasma-hud" aria-live="off">
      <div className="hud-coluna">
        <span className="hud-quem">Você · V{numeroDaVolta(volta.lapId)}</span>
        <span className="hud-estado" style={{ color: cor(pv) }}>{NOME_DO_PEDAL[pv]}</span>
        <span className="hud-velocidade">{nf(valorEm(g, volta.linhas.velocidade, f.s), 0)}</span>
        <span className="hud-unidade">KM/H</span>
        <span className="hud-tempo">{tempo(f.tempoVolta)}</span>
      </div>
      <div className="hud-coluna hud-centro">
        <span className={clsx('hud-diferenca', f.diferenca > 0 ? 'cor-perda' : 'cor-ganho')}>{sg(f.diferenca, 3)} s</span>
        <span className="hud-unidade">{modo === 'curva' ? `diferença nesta curva${f.curva ? ` (${f.curva})` : ''}` : 'diferença na volta'}</span>
      </div>
      <div className="hud-coluna">
        <span className="hud-quem">{referencia === 'ia' ? 'Volta da IA' : 'Sua melhor'}</span>
        <span className="hud-estado" style={{ color: cor(pr) }}>{NOME_DO_PEDAL[pr]}</span>
        <span className="hud-velocidade">{nf(valorEm(g, ref.linhas.velocidade, f.sFantasma), 0)}</span>
        <span className="hud-unidade">KM/H</span>
        <span className="hud-tempo">{tempo(f.tempoFantasma)}</span>
      </div>
    </div>
  );
}

/** Replay: tocar, velocidade, posição e a leitura no cursor. */
function Replay({ grade: g, volta, ref_: ref, curvas }: PropsDaLeitura) {
  const s = useEstadoDaVolta((e) => e.s);
  const tocando = useEstadoDaVolta((e) => e.tocando);
  const velocidade = useEstadoDaVolta((e) => e.velocidade);
  const { setS, setTocando, setVelocidade } = useEstadoDaVolta.getState();

  useEffect(() => {
    if (!tocando) return undefined;
    const atual = useEstadoDaVolta.getState().s;
    let tVolta = tempoEm(g, volta.linhas, atual === null || atual >= g.comprimento - 2 ? 0 : atual);
    if (atual === null || atual >= g.comprimento - 2) setS(0);
    let anterior = performance.now();
    let quadro = 0;
    const passo = (agora: number) => {
      tVolta += ((agora - anterior) / 1000) * useEstadoDaVolta.getState().velocidade;
      anterior = agora;
      if (tVolta >= volta.linhas.total) {
        setS(g.comprimento);
        setTocando(false);
        return;
      }
      setS(sNoTempo(g, volta.linhas, tVolta));
      quadro = requestAnimationFrame(passo);
    };
    quadro = requestAnimationFrame(passo);
    return () => cancelAnimationFrame(quadro);
  }, [tocando, g, volta, setS, setTocando]);

  const sAtual = s ?? 0;
  const tm = tempoEm(g, volta.linhas, sAtual);
  const tr = tempoEm(g, ref.linhas, sAtual);
  const c = curvaEm(curvas, sAtual);
  return (
    <div className="replay" aria-label="Replay">
      <button type="button" className="replay-tocar" aria-label={tocando ? 'Pausar' : 'Reproduzir'} onClick={() => setTocando(!tocando)}>
        {tocando ? (
          <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true"><rect x="3" y="2" width="4" height="12" fill="currentColor" /><rect x="9" y="2" width="4" height="12" fill="currentColor" /></svg>
        ) : (
          <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true"><path d="M4 2 L13 8 L4 14 Z" fill="currentColor" /></svg>
        )}
      </button>
      <Segmentado
        rotulo="Velocidade do replay"
        opcoes={[0.5, 1, 2, 4].map((v) => ({ id: String(v), texto: `${nf(v, v % 1 ? 1 : 0)}×` }))}
        valor={String(velocidade)}
        aoMudar={(v) => setVelocidade(Number(v))}
      />
      <label className="replay-posicao">
        Posição
        <input
          type="range"
          min={0}
          max={Math.round(g.comprimento)}
          value={Math.round(sAtual)}
          onChange={(ev) => {
            setTocando(false);
            setS(Number(ev.target.value));
          }}
        />
      </label>
      <div className="replay-leitura dado">
        <span>{nf(sAtual, 0)} m · {c ? c.codigo : '—'}</span>
        <span>{tempo(tm)} <span className="texto-fraco">(ref. {tempo(tr)})</span></span>
        <span className={tm - tr > 0 ? 'cor-perda' : 'cor-ganho'}>{sg(tm - tr, 3)} s</span>
        <span>{nf(valorEm(g, volta.linhas.velocidade, sAtual), 0)} km/h <span className="texto-fraco">(ref. {nf(valorEm(g, ref.linhas.velocidade, sAtual), 0)})</span></span>
      </div>
    </div>
  );
}
