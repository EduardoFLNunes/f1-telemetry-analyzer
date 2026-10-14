/**
 * O vidro ligado ou desligado (pedido 29). O sistema pode pedir menos
 * transparência (`prefers-reduced-transparency`, tratado em tokens.css); este
 * é o botão manual da tela Sistema, para quem quer o app sem vidro e para medir
 * os quadros por segundo com e sem ele. A escolha fica só neste computador.
 */
const CHAVE = 'sto-vidro';

export function vidroLigado(): boolean {
  try {
    return window.localStorage.getItem(CHAVE) !== 'desligado';
  } catch {
    return true;
  }
}

export function aplicarVidro(ligado: boolean): void {
  if (typeof document === 'undefined') return;
  if (ligado) delete document.documentElement.dataset.vidro;
  else document.documentElement.dataset.vidro = 'desligado';
  try {
    window.localStorage.setItem(CHAVE, ligado ? 'ligado' : 'desligado');
  } catch {
    /* sem armazenamento: vale até fechar o app */
  }
}

/** Quadros por segundo medidos com `requestAnimationFrame` durante `ms`. */
export function medirQuadros(ms = 10_000): Promise<{ fps: number; quadros: number; piorQuadroMs: number; p95Ms: number }> {
  return new Promise((resolve) => {
    const tempos: number[] = [];
    let inicio = 0;
    let anterior = 0;
    const passo = (t: number) => {
      if (!inicio) {
        inicio = t;
        anterior = t;
      } else {
        tempos.push(t - anterior);
        anterior = t;
      }
      if (t - inicio < ms) requestAnimationFrame(passo);
      else {
        const ordenados = [...tempos].sort((a, b) => a - b);
        const p95 = ordenados[Math.floor(ordenados.length * 0.95)] ?? 0;
        resolve({
          fps: Math.round((tempos.length / ((t - inicio) / 1000)) * 10) / 10,
          quadros: tempos.length,
          piorQuadroMs: Math.round((ordenados[ordenados.length - 1] ?? 0) * 10) / 10,
          p95Ms: Math.round(p95 * 10) / 10,
        });
      }
    };
    requestAnimationFrame(passo);
  });
}
