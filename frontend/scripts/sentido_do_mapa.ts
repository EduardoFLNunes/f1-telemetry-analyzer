/**
 * Sentido de giro de uma volta real no mapa principal, antes e depois do pedido 29.
 *
 *   node scripts/sentido_do_mapa.ts <url-do-backend> <lapId> [<lapId> ...]
 *
 * Lê as amostras da volta (`/api/laps/{id}/replay`, posições de mapa (x, −z)) e
 * calcula a área com sinal do traçado na tela:
 * - antes: `scale(s, s)`, a tela recebia y = (−z);
 * - depois: `scale(s, −s)`, a tela recebe y = z (o mesmo do minimapa e do relevo).
 * Na tela, com y para baixo, área positiva pela fórmula do laço é sentido horário.
 * Interlagos é anti-horário.
 */
const [base, ...voltas] = process.argv.slice(2);
if (!base || !voltas.length) {
  console.error('uso: node scripts/sentido_do_mapa.ts <url-do-backend> <lapId> [...]');
  process.exit(2);
}

function areaNaTela(pontos: Array<[number, number]>): number {
  let a = 0;
  for (let i = 0; i < pontos.length; i += 1) {
    const [x1, y1] = pontos[i];
    const [x2, y2] = pontos[(i + 1) % pontos.length];
    a += x1 * y2 - x2 * y1;
  }
  return a / 2;
}

const sentido = (area: number) => (area > 0 ? 'horário' : 'anti-horário');

for (const lapId of voltas) {
  const resposta = await fetch(`${base}/api/laps/${encodeURIComponent(lapId)}/replay?maxSamples=4000`);
  const dados = await resposta.json();
  const mapa: Array<[number, number]> = (dados.samples || [])
    .map((s: any) => s?.mapPosition)
    .filter((p: any) => p && Number.isFinite(p.x) && Number.isFinite(p.y))
    .map((p: any) => [p.x, p.y]);
  const antes = areaNaTela(mapa.map(([x, y]) => [x, y]));
  const depois = areaNaTela(mapa.map(([x, y]) => [x, -y]));
  console.log(JSON.stringify({
    lapId,
    amostras: mapa.length,
    antes: { areaM2: Math.round(antes), sentido: sentido(antes) },
    depois: { areaM2: Math.round(depois), sentido: sentido(depois) },
  }));
}
