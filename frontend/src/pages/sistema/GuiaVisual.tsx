/**
 * Sistema › Guia visual (pedido 29): as cores, as fontes e os componentes,
 * para revisão e para o documento do TCC. As cores são lidas das variáveis em
 * uso (tokens.css), então o guia nunca diverge do app. O porquê de cada
 * escolha está em docs/sistema_visual.md.
 */
import React, { useMemo, useState } from 'react';
import { CartaoNumero, Chip, Dica, EtiquetaEstado, MensagemRadioCartao, PainelVidro, Segmentado } from '../../components/ui/base';
import { tabelaDeContraste, type Tokens } from '../../theme/contraste';
import { mensagemDoEvento } from '../../utils/radio';

type Grupo = { nome: string; onde: string; cores: Array<{ token: string; nome: string; papel: string }> };

const GRUPOS: Grupo[] = [
  { nome: 'Fundo e superfícies', onde: 'carbono', cores: [
    { token: '--fundo', nome: 'Fundo', papel: 'o app, com o brilho vermelho, o frio e a trama' },
    { token: '--superficie', nome: 'Superfície', papel: 'opaca: gráficos, tabelas e mapas' },
    { token: '--superficie-2', nome: 'Superfície 2', papel: 'vidro sem transparência; botões' },
    { token: '--linha', nome: 'Linha', papel: 'divisórias e bordas opacas' },
  ] },
  { nome: 'Texto', onde: 'branco e cinzas', cores: [
    { token: '--texto-1', nome: 'Texto 1', papel: 'títulos, números e corpo' },
    { token: '--texto-2', nome: 'Texto 2', papel: 'texto de apoio' },
    { token: '--texto-3', nome: 'Texto 3', papel: 'rótulos e legendas' },
  ] },
  { nome: 'Destaque', onde: 'transmissão', cores: [
    { token: '--vermelho', nome: 'Vermelho', papel: 'tela ativa, gravação, rádio; botão com texto branco' },
    { token: '--vermelho-claro', nome: 'Vermelho claro', papel: 'o vermelho como texto ou ícone' },
  ] },
  { nome: 'Dados', onde: 'do protótipo', cores: [
    { token: '--freio', nome: 'Freio', papel: 'pedal de freio' },
    { token: '--acelerador', nome: 'Acelerador', papel: 'pedal do acelerador' },
    { token: '--parcial', nome: 'Parcial', papel: 'pedal parcial' },
    { token: '--perda', nome: 'Perda', papel: 'tempo perdido, sempre com + e o número' },
    { token: '--ganho', nome: 'Ganho', papel: 'tempo ganho, sempre com − e o número' },
  ] },
  { nome: 'Volta', onde: 'traços e mapa', cores: [
    { token: '--voce', nome: 'Você', papel: 'a sua volta' },
    { token: '--referencia', nome: 'Referência', papel: 'volta da IA ou sua melhor' },
  ] },
  { nome: 'Cronometragem', onde: 'só em tempos', cores: [
    { token: '--tempo-roxo', nome: 'Roxo', papel: 'a melhor de todas' },
    { token: '--tempo-verde', nome: 'Verde', papel: 'a sua melhor' },
    { token: '--tempo-amarelo', nome: 'Amarelo', papel: 'sem melhora' },
  ] },
  { nome: 'Estados', onde: 'coleta e backend', cores: [
    { token: '--estado-ok', nome: 'Ok', papel: 'canal ok, backend pronto' },
    { token: '--estado-aviso', nome: 'Aviso', papel: 'fora da faixa, taxa baixa, esperando' },
    { token: '--estado-erro', nome: 'Erro', papel: 'ausente, parado, sem resposta' },
  ] },
];

const TOKENS_DO_CONTRASTE = [
  '--fundo', '--fundo-trama', '--fundo-brilho-vermelho', '--fundo-brilho-frio', '--vidro-fundo', '--vidro-fundo-forte',
  '--superficie-no-vidro', '--superficie', '--vermelho', '--texto-sobre-vermelho',
  '--texto-1', '--texto-2', '--texto-3', '--vermelho-claro', '--perda', '--ganho', '--tempo-verde', '--tempo-roxo',
  '--tempo-amarelo', '--estado-ok', '--estado-aviso', '--estado-erro',
];

function valorDoToken(token: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(token).trim();
}

const EXEMPLO_RADIO = [
  mensagemDoEvento({
    type: 'coaching_event',
    evidence: { microsector: 12, yourSeconds: 3.12, referenceSeconds: 2.81, lossSeconds: 0.31, referenceKind: 'volta_ia', referenceLabel: 'volta da IA', brakeDeltaM: -12 },
    lap_number: 7,
  }),
  mensagemDoEvento({ type: 'coaching_focus', focusSectors: [3, 12, 41], focusSource: 'modelo', lap_number: 6 }),
];

const ESTADOS: Array<{ estado: string; tom: 'ok' | 'aviso' | 'erro' | 'neutro'; texto: string }> = [
  { estado: 'ok', tom: 'ok', texto: 'ok' },
  { estado: 'ausente', tom: 'erro', texto: 'ausente' },
  { estado: 'parado', tom: 'erro', texto: 'parado' },
  { estado: 'fora_da_faixa', tom: 'aviso', texto: 'fora da faixa' },
  { estado: 'taxa_baixa', tom: 'aviso', texto: 'taxa baixa' },
  { estado: 'sem_dados', tom: 'neutro', texto: 'sem dados' },
];

export const GuiaVisual: React.FC = () => {
  const [referencia, setReferencia] = useState<'ia' | 'melhor'>('ia');
  const [volta, setVolta] = useState(5);
  const [dica, setDica] = useState<{ x: number; y: number } | null>(null);
  const contraste = useMemo(() => {
    const t: Tokens = {};
    for (const nome of TOKENS_DO_CONTRASTE) t[nome] = valorDoToken(nome);
    try {
      return tabelaDeContraste(t);
    } catch {
      return null;
    }
  }, []);

  return (
    <>
      <PainelVidro id="guia-paleta" titulo="Paleta" nota="lida das variáveis em uso (tokens.css)">
        <div className="grade-3">
          {GRUPOS.map((g) => (
            <div key={g.nome} className="superficie" style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 12 }}>
              <div className="painel-cabeca">
                <h3 className="titulo-painel" style={{ fontSize: 19 }}>{g.nome}</h3>
                <span className="texto-fraco dado">{g.onde}</span>
              </div>
              {g.cores.map((c) => (
                <div key={c.token} className="guia-amostra">
                  <div className="guia-amostra__cor" style={{ background: `var(${c.token})` }} />
                  <div style={{ display: 'flex', flexDirection: 'column', minWidth: 0 }}>
                    <div style={{ display: 'flex', gap: 10, alignItems: 'baseline', flexWrap: 'wrap' }}>
                      <b style={{ fontWeight: 600 }}>{c.nome}</b>
                      <span className="dado texto-apoio" style={{ fontSize: 12 }}>{c.token} · {valorDoToken(c.token)}</span>
                    </div>
                    <span className="texto-fraco">{c.papel}</span>
                  </div>
                </div>
              ))}
            </div>
          ))}
        </div>
      </PainelVidro>

      <PainelVidro id="guia-fontes" titulo="Tipografia" nota="arquivos locais, licença OFL 1.1 em src/assets/fonts">
        <div className="grade-3">
          <div className="superficie" style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 8 }}>
            <span className="rotulo">Títulos e números grandes · Barlow Condensed</span>
            <div style={{ fontFamily: 'var(--fonte-titulo)', fontWeight: 700, fontSize: 54, lineHeight: 0.95, textTransform: 'uppercase' }}>Sessões<br />Ao vivo</div>
            <div className="cartao-numero__valor">1:29,389 · 1:24,828</div>
            <span className="texto-fraco">Condensada, com algarismos de largura igual (tnum).</span>
          </div>
          <div className="superficie" style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 8 }}>
            <span className="rotulo">Texto · Instrument Sans</span>
            <div style={{ fontSize: 24, fontWeight: 600, lineHeight: 1.2 }}>A IA freia 12 m depois de você</div>
            <p className="texto-apoio" style={{ margin: 0 }}>Diferença medida contra uma volta real, nunca ganho prometido. Ação, trajetória, mínima, cedilha e til.</p>
            <span className="texto-fraco">Corpo do app, 14 px; frase do rádio, 16 px.</span>
          </div>
          <div className="superficie" style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 8 }}>
            <span className="rotulo">Dados · IBM Plex Mono</span>
            <div className="dado" style={{ fontWeight: 700, fontSize: 32 }}>+4,561 s</div>
            <div className="dado texto-apoio" style={{ fontSize: 14, lineHeight: 1.6 }}>0ed16f0dd2225990<br />60 microssetores · C01 a C14</div>
            <span className="texto-fraco">Tempos em tabela, diferenças e rótulos de dado.</span>
          </div>
        </div>
      </PainelVidro>

      <div className="grade-2">
        <PainelVidro id="guia-vidro" titulo="Vidro">
          <ul className="texto-apoio" style={{ margin: 0, paddingLeft: 18, display: 'flex', flexDirection: 'column', gap: 4 }}>
            <li>Só nos recipientes: navegação, hero, cartões, painéis, HUD e dicas.</li>
            <li>Número nunca sobre vidro puro: gráficos, tabelas e mapas ficam numa superfície opaca.</li>
            <li>Uma camada de desfoque por região: nunca vidro dentro de vidro.</li>
            <li>Sem transparência quando o sistema pede (prefers-reduced-transparency) ou pela Depuração.</li>
            <li>Sem animação quando o sistema pede (prefers-reduced-motion).</li>
          </ul>
        </PainelVidro>

        <PainelVidro id="guia-contraste" titulo="Contraste" nota="WCAG 2.1, pior caso do fundo">
          {contraste ? (
            <div className="superficie tabela-caixa">
              <table className="tabela">
                <thead><tr><th scope="col">Texto</th><th scope="col">Uso</th><th scope="col" className="num">Pior razão</th><th scope="col">AA</th></tr></thead>
                <tbody>
                  {contraste.linhas.map((l) => (
                    <tr key={l.token}>
                      <td><span className="dado" style={{ color: `var(${l.token})` }}>{l.token}</span></td>
                      <td className="texto-apoio">{l.uso}</td>
                      <td className="num">{l.pior.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}:1</td>
                      <td>{l.passaAA ? <EtiquetaEstado tom="ok">passa</EtiquetaEstado> : <EtiquetaEstado tom="erro">não passa</EtiquetaEstado>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : <p className="texto-fraco">Não deu para ler as variáveis.</p>}
        </PainelVidro>
      </div>

      <PainelVidro id="guia-componentes" titulo="Componentes">
        <div className="grade-3">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <span className="rotulo">Cartão de número</span>
            <div className="grade-cartoes" style={{ gridTemplateColumns: 'repeat(2, minmax(0, 1fr))' }}>
              <CartaoNumero rotulo="Sua melhor volta" valor="1:29,389" cor="tempo-verde" detalhe="04/10 · volta 18" />
              <CartaoNumero rotulo="Para a volta da IA" valor="+4,561 s" cor="perda" detalhe="IA: 1:24,828" />
              <CartaoNumero rotulo="Sem dado" valor={null} detalhe="sem dados" />
            </div>
            <span className="rotulo" style={{ marginTop: 6 }}>Etiqueta de estado</span>
            <div className="chips">
              {ESTADOS.map((e) => <EtiquetaEstado key={e.estado} tom={e.tom} estado={e.estado}>{e.texto}</EtiquetaEstado>)}
            </div>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <span className="rotulo">Segmentado e chips</span>
            <Segmentado rotulo="Comparar com" opcoes={[{ id: 'ia', texto: 'Volta da IA' }, { id: 'melhor', texto: 'Sua melhor' }]} valor={referencia} aoMudar={setReferencia} />
            <div className="chips">
              {[3, 5, 8].map((n) => <Chip key={n} ativo={volta === n} onClick={() => setVolta(n)}>V{n}</Chip>)}
              <Chip disabled>V9 · inválida</Chip>
            </div>
            <span className="rotulo" style={{ marginTop: 6 }}>Botões</span>
            <div className="chips">
              <button type="button" className="botao botao--primario">Coleta de dados</button>
              <button type="button" className="botao">Última volta</button>
            </div>
            <span className="rotulo" style={{ marginTop: 6 }}>Dica</span>
            <div
              className="superficie"
              style={{ height: 80, display: 'grid', placeItems: 'center', color: 'var(--texto-3)', fontSize: 13 }}
              onMouseMove={(e) => setDica({ x: e.clientX, y: e.clientY })}
              onMouseLeave={() => setDica(null)}
            >
              passe o mouse aqui
            </div>
            {dica && <Dica x={dica.x} y={dica.y}>812 m · C04<br /><span className="cor-perda">+0,214 s</span> · 176 km/h (ref. 181)</Dica>}
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <span className="rotulo">Mensagem de rádio · exemplo</span>
            {EXEMPLO_RADIO.map((m) => <MensagemRadioCartao key={m.id} mensagem={m} />)}
            <span className="rotulo" style={{ marginTop: 6 }}>Tabela</span>
            <div className="superficie tabela-caixa">
              <table className="tabela">
                <thead><tr><th scope="col">Curva</th><th scope="col" className="num">Perda</th></tr></thead>
                <tbody>
                  <tr><td>C01</td><td className="num cor-perda">+1,267 s</td></tr>
                  <tr><td>C14</td><td className="num cor-perda">+0,352 s</td></tr>
                </tbody>
              </table>
            </div>
            <span className="texto-fraco">Exemplos de forma. Os números da tabela são as perdas de C01 e C14 de 04/10 no relatório de evolução.</span>
          </div>
        </div>
      </PainelVidro>
    </>
  );
};

export default GuiaVisual;
