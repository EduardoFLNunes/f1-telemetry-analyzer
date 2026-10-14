/**
 * Interlagos no hero (pedido 29): as mesmas camadas do mapa do app (asfalto,
 * pintura e zebras do cache, por `drawTrackSurface`) e a sua melhor volta
 * traçada por cima.
 *
 * Sentido: o cache e as amostras estão em coordenadas de mapa (x, −z). Com
 * `scale(s, −s)` a tela fica com x para a direita e z para baixo, como o
 * minimapa e o relevo, e Interlagos gira no anti-horário. É o mesmo sentido que
 * o mapa principal passa a usar neste pedido.
 *
 * O traço anima uma vez (cerca de 5 s); com `prefers-reduced-motion` ele já
 * aparece inteiro.
 */
import React, { useEffect, useMemo, useRef } from 'react';
import { drawTrackSurface } from '../map/OverlayRenderer';

export type PontoMapa = { x: number; y: number };

type Limites = { minX: number; maxX: number; minY: number; maxY: number };

const MARGEM_PX = 16;
const DURACAO_MS = 5500;

function limitesDe(pista: any, volta: PontoMapa[] | null): Limites | null {
  const l: Limites = { minX: Infinity, maxX: -Infinity, minY: Infinity, maxY: -Infinity };
  const somar = (x: number, y: number) => {
    if (!Number.isFinite(x) || !Number.isFinite(y)) return;
    if (x < l.minX) l.minX = x;
    if (x > l.maxX) l.maxX = x;
    if (y < l.minY) l.minY = y;
    if (y > l.maxY) l.maxY = y;
  };
  for (const loop of pista?.asphaltSurface?.loops || []) {
    for (const p of loop?.points || []) somar(Number(p[0]), Number(p[1]));
  }
  if (!Number.isFinite(l.minX)) for (const p of volta || []) somar(p.x, p.y);
  return Number.isFinite(l.minX) && l.maxX > l.minX && l.maxY > l.minY ? l : null;
}

function token(nome: string, padrao: string): string {
  if (typeof window === 'undefined') return padrao;
  return getComputedStyle(document.documentElement).getPropertyValue(nome).trim() || padrao;
}

function semMovimento(): boolean {
  return typeof window !== 'undefined' && Boolean(window.matchMedia?.('(prefers-reduced-motion: reduce)').matches);
}

export const PistaHero: React.FC<{
  pista: any | null;
  volta: PontoMapa[] | null;
  altura: number;
  descricao: string;
}> = ({ pista, volta, altura, descricao }) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const limites = useMemo(() => limitesDe(pista, volta), [pista, volta]);

  const geometria = useMemo(() => {
    if (!limites) return null;
    const alturaUtil = altura - 2 * MARGEM_PX;
    const s = alturaUtil / (limites.maxY - limites.minY);
    const largura = Math.round((limites.maxX - limites.minX) * s + 2 * MARGEM_PX);
    return { s, largura };
  }, [limites, altura]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !limites || !geometria) return undefined;
    const ctx = canvas.getContext('2d');
    if (!ctx) return undefined;
    const dpr = window.devicePixelRatio || 1;
    const { s, largura } = geometria;
    canvas.width = Math.round(largura * dpr);
    canvas.height = Math.round(altura * dpr);

    // (x, −z) do mapa → tela com x para a direita e z para baixo.
    const transformar = (c: CanvasRenderingContext2D) => {
      c.setTransform(dpr * s, 0, 0, -dpr * s, dpr * (MARGEM_PX - s * limites.minX), dpr * (MARGEM_PX + s * limites.maxY));
    };

    // A pista é desenhada uma vez, numa camada parada.
    const fundo = document.createElement('canvas');
    fundo.width = canvas.width;
    fundo.height = canvas.height;
    const f = fundo.getContext('2d');
    if (f && pista) {
      transformar(f);
      drawTrackSurface(f, pista, null, s);
    }

    const corVolta = token('--voce', '#ffffff');
    const corCabeca = token('--vermelho', '#e10600');
    const corContorno = token('--fundo', '#08090b');
    const pontos = volta || [];

    const desenhar = (progresso: number) => {
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      // Com a volta por cima, a pista recua: na escala do hero a pintura branca
      // competiria com o traço, que é o que o hero quer mostrar.
      ctx.globalAlpha = pontos.length >= 2 ? 0.42 : 1;
      ctx.drawImage(fundo, 0, 0);
      ctx.globalAlpha = 1;
      if (pontos.length < 2) return;
      const ate = Math.max(1, Math.min(pontos.length - 1, Math.floor(progresso * (pontos.length - 1))));
      transformar(ctx);
      ctx.lineJoin = 'round';
      ctx.lineCap = 'round';
      ctx.strokeStyle = corVolta;
      ctx.lineWidth = 2.6 / s;
      ctx.shadowColor = corVolta;
      ctx.shadowBlur = 6 * dpr;
      ctx.beginPath();
      ctx.moveTo(pontos[0].x, pontos[0].y);
      for (let i = 1; i <= ate; i += 1) ctx.lineTo(pontos[i].x, pontos[i].y);
      ctx.stroke();
      ctx.shadowBlur = 0;
      const cabeca = pontos[ate];
      ctx.fillStyle = corCabeca;
      ctx.strokeStyle = corContorno;
      ctx.lineWidth = 2 / s;
      ctx.beginPath();
      ctx.arc(cabeca.x, cabeca.y, 5 / s, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();
    };

    if (semMovimento() || pontos.length < 2) {
      desenhar(1);
      return undefined;
    }
    let quadro = 0;
    const inicio = performance.now();
    const passo = (t: number) => {
      const bruto = Math.min(1, (t - inicio) / DURACAO_MS);
      const suave = bruto < 0.5 ? 2 * bruto * bruto : 1 - (-2 * bruto + 2) ** 2 / 2;
      desenhar(suave);
      if (bruto < 1) quadro = requestAnimationFrame(passo);
    };
    quadro = requestAnimationFrame(passo);
    return () => cancelAnimationFrame(quadro);
  }, [pista, volta, limites, geometria, altura]);

  if (!geometria) {
    return (
      <div className="superficie" style={{ width: 300, height: altura, display: 'grid', placeItems: 'center', color: 'var(--texto-3)', fontSize: 13 }}>
        pista ainda não carregada
      </div>
    );
  }
  return <canvas ref={canvasRef} role="img" aria-label={descricao} style={{ width: geometria.largura, height: altura }} />;
};

export default PistaHero;
