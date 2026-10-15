/**
 * Conferência da tela Volta contra o protótipo A (pedido 30, seção 6).
 *
 *   node scripts/conferencia_prototipo.ts <url-do-backend> [saida.json]
 *
 * A volta 8 da sessão de 05/10 às 20:33 contra a volta da IA. Compara três
 * fontes:
 * - app: as linhas do store v2 lidas pelas rotas do app e as medidas de
 *   `src/volta/medidas.ts` (o que a tela mostra);
 * - protótipo: os números embutidos em `mockups/prototipo_dashboard.html`;
 * - oficial: o `por_volta` do `sessao_2026-10-05-2.json`, que o
 *   `atualizar_coach` gravou (só existe contra a volta da IA).
 */
import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  curvasDoRelatorio,
  diferencaPorMicrossetor,
  estadoDoFantasma,
  medidasDasCurvas,
  type Curva,
  type Grade,
  type Linhas,
} from '../src/volta/medidas.ts';

const base = process.argv[2];
const destino = process.argv[3];
if (!base) {
  console.error('uso: node scripts/conferencia_prototipo.ts <url-do-backend> [saida.json]');
  process.exit(2);
}
const VOLTA = '2026-10-05_20-33-47_vhe_interlagos#0008';
const SESSAO = '2026-10-05-2';

const pegar = async (rota: string) => {
  const r = await fetch(`${base}${rota}`);
  if (!r.ok) throw new Error(`${rota}: ${r.status}`);
  return r.json();
};

const refs = await pegar('/api/coach/referencias');
const idIA = refs.referencias.volta_ia.volta as string;
const [sessao, volta, ia] = await Promise.all([
  pegar(`/api/evolucao/sessoes/${SESSAO}`),
  pegar(`/api/store/voltas/${encodeURIComponent(VOLTA)}`),
  pegar(`/api/store/voltas/${encodeURIComponent(idIA)}`),
]);

const linhas = (v: any): Linhas => ({
  elapsed: v.elapsedS, total: v.tempoS, velocidade: v.velocidadeKmh, acelerador: v.acelerador, freio: v.freio, lateral: v.lateralM,
});
const g: Grade = { n: volta.pontosDaGrade, comprimento: volta.comprimentoM, passo: volta.passoM };
const curvas: Curva[] = curvasDoRelatorio(g, sessao.sessao.curvas);
const geo = await pegar('/api/geometria/oficial');
const bordas: number[] = geo.bordasDosMicrossetores;

const app = medidasDasCurvas(g, linhas(volta), linhas(ia), curvas);
const appMs = diferencaPorMicrossetor(g, linhas(volta), linhas(ia), bordas);

// O protótipo A: os dados embutidos.
const aqui = dirname(fileURLToPath(import.meta.url));
const html = readFileSync(join(aqui, '..', 'mockups', 'prototipo_dashboard.html'), 'utf-8');
const D = JSON.parse(/<script type="application\/json" id="dados">([\s\S]*?)<\/script>/.exec(html)![1]);
const chave = `${VOLTA}|${D.ref.ia}`;
const proto = D.cmp[chave];
if (!proto) throw new Error(`o protótipo não tem ${chave}`);
const pLap = D.laps[VOLTA];
const pRef = D.laps[D.ref.ia];

// O fantasma por curva do protótipo, com os dados dele (a mesma conta de `ghostState`).
const S: number[] = D.step_s;
const pInterp = (xs: number[], ys: number[], x: number) => {
  if (x <= xs[0]) return ys[0];
  for (let i = 1; i < xs.length; i += 1) if (x <= xs[i]) return ys[i - 1] + ((x - xs[i - 1]) / (xs[i] - xs[i - 1])) * (ys[i] - ys[i - 1]);
  return ys[ys.length - 1];
};
const protoGhost = (s: number) => {
  const c = curvas.find((k) => (k.trecho[1] >= k.trecho[0] ? s >= k.trecho[0] && s < k.trecho[1] : s >= k.trecho[0] || s < k.trecho[1]))!;
  const [a, b] = c.trecho;
  const s0 = b >= a ? a : s >= a ? a : 0;
  const tme = pInterp(S, pLap.e, s);
  return (tme - pInterp(S, pLap.e, s0)) - (pInterp(S, pRef.e, s) - pInterp(S, pRef.e, s0));
};

const oficial = Object.fromEntries(sessao.sessao.curvas.map((c: any) => [String(c.curva).split('-')[0], c.por_volta.find((p: any) => p.volta === VOLTA)]));
const r3 = (v: number | null | undefined) => (v === null || v === undefined || !Number.isFinite(v) ? null : Math.round(v * 1000) / 1000);

const linhasCurvas = curvas.map((c, i) => {
  const fim = c.trecho[1] - 0.01 < 0 ? c.trecho[1] + g.comprimento - 0.01 : c.trecho[1] - 0.01;
  const fantasmaApp = estadoDoFantasma(g, linhas(volta), linhas(ia), curvas, fim % g.comprimento, 'curva').diferenca;
  return {
    curva: c.codigo,
    perda: { app: r3(app[i].perdaS), prototipo: r3(proto.c[i][0]), oficial: r3(oficial[c.codigo]?.perda_s) },
    freadaM: { app: r3(app[i].freadaM), prototipo: proto.c[i][3], oficial: r3(oficial[c.codigo]?.frenagem_vs_ia_m) },
    minimaKmh: { app: r3(app[i].minimaKmh), prototipo: proto.c[i][1], oficial: r3(oficial[c.codigo]?.velocidade_minima_vs_ia_kmh) },
    lateralM: { app: r3(app[i].lateralApiceM), prototipo: proto.c[i][2], oficial: r3(oficial[c.codigo]?.lateral_apice_vs_ia_m) },
    fantasmaNoFimDaCurva: { app: r3(fantasmaApp), prototipo: r3(protoGhost(fim % g.comprimento)) },
  };
});
const maior = (f: (l: any) => number | null) => Math.max(...linhasCurvas.map((l) => Math.abs(f(l) ?? 0)));
const msDif = appMs.map((v, i) => Math.abs(v - proto.ms[i]));

const resultado = {
  formato: 'conferencia-prototipo/1',
  volta: VOLTA,
  referencia: idIA,
  tempo: { app: volta.tempoS, prototipo: pLap.t, refApp: ia.tempoS, refPrototipo: pRef.t },
  diferencaDaVolta: { app: r3(volta.tempoS - ia.tempoS), prototipo: r3(pLap.t - pRef.t), somaDasCurvasApp: r3(app.reduce((a, c) => a + c.perdaS, 0)) },
  curvas: linhasCurvas,
  microssetores: appMs.map((v, i) => ({ microssetor: i + 1, app: Math.round(v * 10000) / 10000, prototipo: proto.ms[i] })),
  maioresDiferencas: {
    perdaAppPrototipoS: r3(maior((l) => (l.perda.app ?? 0) - (l.perda.prototipo ?? 0))),
    perdaAppOficialS: r3(maior((l) => (l.perda.app ?? 0) - (l.perda.oficial ?? 0))),
    freadaAppOficialM: r3(maior((l) => (l.freadaM.app ?? 0) - (l.freadaM.oficial ?? 0))),
    minimaAppOficialKmh: r3(maior((l) => (l.minimaKmh.app ?? 0) - (l.minimaKmh.oficial ?? 0))),
    lateralAppOficialM: r3(maior((l) => (l.lateralM.app ?? 0) - (l.lateralM.oficial ?? 0))),
    microssetorAppPrototipoS: r3(Math.max(...msDif)),
    fantasmaAppPrototipoS: r3(maior((l) => (l.fantasmaNoFimDaCurva.app ?? 0) - (l.fantasmaNoFimDaCurva.prototipo ?? 0))),
  },
};
console.log(JSON.stringify(resultado.maioresDiferencas, null, 2));
console.log(JSON.stringify({ tempo: resultado.tempo, diferencaDaVolta: resultado.diferencaDaVolta }, null, 2));
for (const l of linhasCurvas) console.log(l.curva, JSON.stringify(l.perda), JSON.stringify(l.freadaM), JSON.stringify(l.fantasmaNoFimDaCurva));
if (destino) {
  writeFileSync(destino, JSON.stringify(resultado, null, 2) + '\n', 'utf-8');
  console.log(`gravado em ${destino}`);
}
