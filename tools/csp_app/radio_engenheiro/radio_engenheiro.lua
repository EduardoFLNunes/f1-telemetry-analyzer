-- Rádio do engenheiro (pedido 31, ADR 0020).
--
-- O que faz:
--   * a cada 0,3 s, pede ao backend local as mensagens novas (/api/radio/mensagens),
--     com uma requisição por vez (a API do CSP permite no máximo duas);
--   * mostra um cartão de rádio por alguns segundos, numa janela transparente
--     (carbono e vermelho, como o app), e toca a vinheta e a voz da mensagem;
--   * com o backend fora do ar, mostra um indicador discreto e não repete o aviso;
--   * se a API do CSP não tiver o que o app usa, avisa uma vez e fica calado.
--
-- O que não faz: não muda o carro, os controles nem o jogo, e não desenha na pista.
-- O áudio toca direto da URL do backend (ui.MediaPlayer aceita URL), sem ler nem
-- gravar arquivo fora da pasta do app.

local BACKEND = 'http://127.0.0.1:8000'
local PERIODO_S = 0.3
local CARTAO_MINIMO_S = 5
local FOLGA_DEPOIS_DA_VOZ_S = 2.5
local AVISO_S = 10

local CORES = {
  fundo = rgbm(0.031, 0.035, 0.043, 0.9),
  vermelho = rgbm(0.882, 0.024, 0.0, 1),
  texto = rgbm(0.949, 0.957, 0.961, 1),
  apoio = rgbm(0.72, 0.76, 0.80, 1),
  fraco = rgbm(0.55, 0.59, 0.63, 1),
}
local TAG = { coach = 'RÁDIO', resumo = 'VOLTA', teste = 'TESTE' }

-- A API que o app usa, conferida uma vez ao abrir. Confere só se existe: no CSP,
-- várias funções são nativas (FFI) e o `type()` delas é 'cdata', e não 'function'.
-- No teste no jogo de 18/10, conferir 'function' calou o app com a API inteira lá.
local function existe(tabela, nome)
  return tabela ~= nil and tabela[nome] ~= nil
end

local function faltando()
  local f = {}
  local usadas = {
    { web, 'web', 'get' }, { web, 'web', 'timeouts' }, { JSON, 'JSON', 'parse' },
    { ui, 'ui', 'MediaPlayer' }, { ui, 'ui', 'dwriteDrawText' }, { ui, 'ui', 'drawRectFilled' },
    { ui, 'ui', 'windowSize' }, { os, 'os', 'preciseClock' }, { ac, 'ac', 'log' },
  }
  for _, u in ipairs(usadas) do
    if not existe(u[1], u[3]) then f[#f + 1] = u[2] .. '.' .. u[3] end
  end
  if setInterval == nil then f[#f + 1] = 'setInterval' end
  return f
end

local FALTA = faltando()
local CALADO = #FALTA > 0
if CALADO then
  ac.log('[radio_engenheiro] a API do CSP não tem: ' .. table.concat(FALTA, ', ') .. '. O app fica calado.')
else
  ac.log('[radio_engenheiro] ligado; pede as mensagens a ' .. BACKEND)
end

local estado = {
  desde = 0,
  instancia = nil,
  primeira = true,
  pedindo = false,
  fora = false,
  avisouFora = false,
  fila = {},
  atual = nil,
  inicio = 0,
  ateQuando = 0,
  player = nil,
}

local function agora()
  return os.preciseClock()
end

-- ── conversa com o backend ──────────────────────────────────────────────

local function receber(err, resposta)
  estado.pedindo = false
  if err or not resposta or resposta.status ~= 200 then
    estado.fora = true
    if not estado.avisouFora then
      ac.log('[radio_engenheiro] o backend não respondeu em ' .. BACKEND)
      estado.avisouFora = true
    end
    return
  end
  estado.fora = false
  local ok, dados = pcall(JSON.parse, resposta.body)
  if not ok or type(dados) ~= 'table' then
    return
  end
  local mensagens = type(dados.mensagens) == 'table' and dados.mensagens or {}
  if estado.primeira then
    -- Ao abrir, o que já tinha sido dito fica para trás.
    estado.primeira = false
  else
    -- Mensagens novas (ou todas, se o backend reiniciou: outra instância).
    for _, m in ipairs(mensagens) do
      estado.fila[#estado.fila + 1] = m
    end
  end
  estado.instancia = dados.instancia
  estado.desde = tonumber(dados.ultimoId) or estado.desde
end

local function pedir()
  if CALADO or estado.pedindo then
    return
  end
  estado.pedindo = true
  local url = BACKEND .. '/api/radio/mensagens?desde=' .. tostring(estado.desde)
  if type(estado.instancia) == 'string' then
    url = url .. '&instancia=' .. estado.instancia
  end
  local ok = pcall(web.get, url, receber)
  if not ok then
    estado.pedindo = false
  end
end

if not CALADO then
  pcall(web.timeouts, 500, 500, 1000, 1500)
  setInterval(pedir, PERIODO_S)
end

-- ── a voz ───────────────────────────────────────────────────────────────

local function tocar(m)
  if type(m.audio) ~= 'string' then
    return
  end
  if not estado.player then
    local ok, player = pcall(ui.MediaPlayer, nil, { use3D = false, reverbResponse = false })
    if not ok or not player then
      return
    end
    estado.player = player
  end
  pcall(function()
    estado.player:setSource(BACKEND .. m.audio)
    estado.player:setVolume(1)
    estado.player:setAutoPlay(true)
    estado.player:play()
  end)
end

local function avancar(t)
  if estado.atual and t < estado.ateQuando then
    return
  end
  estado.atual = nil
  local proxima = table.remove(estado.fila, 1)
  if not proxima then
    return
  end
  estado.atual = proxima
  estado.inicio = t
  estado.ateQuando = t + math.max(CARTAO_MINIMO_S, (tonumber(proxima.duracaoS) or 3) + FOLGA_DEPOIS_DA_VOZ_S)
  tocar(proxima)
end

-- ── o cartão ────────────────────────────────────────────────────────────

local function comAlfa(cor, alfa)
  return rgbm(cor.r, cor.g, cor.b, cor.mult * alfa)
end

local function corte(texto, limite)
  texto = tostring(texto or '')
  if #texto <= limite then
    return texto
  end
  return texto:sub(1, limite - 1) .. '…'
end

local function desenharCartao(m, alfa, tamanho)
  local w, h = tamanho.x, tamanho.y - 26
  ui.drawRectFilled(vec2(0, 0), vec2(w, h), comAlfa(CORES.fundo, alfa), 10)
  ui.drawRectFilled(vec2(0, 0), vec2(6, h), comAlfa(CORES.vermelho, alfa), 3)
  ui.dwriteDrawText(TAG[m.origem] or 'RÁDIO', 13, vec2(20, 10), comAlfa(CORES.vermelho, alfa))
  ui.dwriteDrawText(corte(m.titulo, 48), 22, vec2(20, 28), comAlfa(CORES.texto, alfa))
  ui.dwriteDrawText(corte(m.texto, 64), 17, vec2(20, 60), comAlfa(CORES.texto, alfa))
  if type(m.detalhe) == 'string' and m.detalhe ~= '' then
    ui.dwriteDrawText(corte(m.detalhe, 86), 13, vec2(20, 88), comAlfa(CORES.apoio, alfa))
  end
end

local function desenharAviso(texto, tamanho)
  ui.drawRectFilled(vec2(0, 0), vec2(tamanho.x, 44), CORES.fundo, 8)
  ui.dwriteDrawText(corte(texto, 90), 13, vec2(14, 14), CORES.apoio)
end

-- Chamada a cada quadro pela janela do app (manifest.ini, FUNCTION_MAIN).
function janela(dt)
  local t = os.preciseClock and agora() or 0
  local tamanho = ui.windowSize()
  if CALADO then
    if t < AVISO_S then
      desenharAviso('Rádio do engenheiro: esta versão do CSP não tem ' .. table.concat(FALTA, ', ') .. '.', tamanho)
    end
    return
  end
  avancar(t)
  if estado.fora then
    -- Discreto: um ponto apagado e duas palavras, no rodapé da janela.
    ui.drawRectFilled(vec2(10, tamanho.y - 16), vec2(18, tamanho.y - 8), CORES.fraco, 4)
    ui.dwriteDrawText('rádio sem backend', 12, vec2(24, tamanho.y - 20), CORES.fraco)
  end
  local m = estado.atual
  if not m then
    return
  end
  local alfa = math.max(0, math.min(1, (t - estado.inicio) / 0.25, (estado.ateQuando - t) / 0.6))
  desenharCartao(m, alfa, tamanho)
end
