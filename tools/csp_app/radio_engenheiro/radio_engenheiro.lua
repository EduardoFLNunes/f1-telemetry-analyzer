-- Rádio do engenheiro (pedido 31, ADR 0020; pedido 35, ADR 0021).
--
-- Três janelas, cada uma ligada e desligada na barra de apps do jogo (manifest.ini):
--
--   * o rádio (`janela`): a cada 0,3 s, pede ao backend local as mensagens novas
--     (/api/radio/mensagens) e mostra o cartão por alguns segundos, com a vinheta e a
--     voz. Com o backend fora do ar, mostra um indicador discreto; se a API do CSP
--     não tiver o que o app usa, avisa uma vez e fica calado;
--   * o minimapa (`minimapa`, pedido 35, Parte E): a pista tratada, o carro (lido do
--     jogo a cada quadro), o fantasma da referência escolhida na Coleta (pelo tempo da
--     volta), a diferença ao vivo e as curvas da última análise;
--   * o mapa aproximado (`aproximado`, pedido 35, depois do teste no jogo): a vista de
--     perto da tela Volta ("fantasma por curva"). A câmera segue o carro e gira com a
--     pista; a pista detalhada (asfalto, pintura e zebras) é uma imagem desenhada uma vez
--     (`pista_detalhada.png`); por cima, o seu traçado e o do fantasma, pintados pelo
--     pedal, o carro, o fantasma, o nome das curvas e a diferença.
--
-- A voz tem três caminhos, um depois do outro (pedido 35, Parte B): a URL do backend;
-- o arquivo que o backend grava em data/radio/audio/; e o áudio baixado para a
-- subpasta `voz` da pasta do app, que o próprio app limpa ao abrir. O app começa pelo
-- caminho que tocou da última vez e escreve uma linha no log do CSP por mensagem.
--
-- O que não faz: não muda o carro, os controles nem o jogo, e não desenha na pista.
-- Só grava dentro da pasta dele: a subpasta `voz` (ADR 0021, item 6).

local BACKEND = 'http://127.0.0.1:8000'
local PERIODO_S = 0.3
local CARTAO_MINIMO_S = 5
local CARTAO_DA_ANALISE_S = 12      -- a análise traz uma linha por curva para ler
local FOLGA_DEPOIS_DA_VOZ_S = 2.5
local MENSAGEM_VELHA_S = 20         -- com o cartão desligado, a mensagem que esperou isto fica para trás
local AVISO_S = 10
local MAXIMO_DE_PEDIDOS = 2         -- o web.get do CSP aceita no máximo dois pedidos de uma vez

-- O volume do rádio, de 0 a 1: o volume do player do CSP. O som sai pelo áudio do
-- jogo (FMOD), então o volume geral do Assetto Corsa ainda vale por cima deste. Em 1,
-- a voz toca como o backend gravou; abaixe (por exemplo, para 0.6) se ela cobrir
-- demais o motor, ou suba o volume geral do jogo se ela ficar baixa.
local VOLUME_DO_RADIO = 1.0

-- A voz: os três caminhos, na ordem em que são tentados.
local CAMINHOS_DA_VOZ = { 'url', 'arquivo', 'baixado' }
local ESPERA_PARA_TOCAR_S = 2.5     -- sem tocar nesse tempo, o app passa ao caminho seguinte
local ESPERA_NA_PRIMEIRA_S = 5      -- na primeira mensagem, o CSP ainda pode estar carregando o Media Foundation
local ESPERA_DO_DOWNLOAD_S = 4

-- O minimapa.
local TOPO_DO_MINIMAPA = 30         -- a faixa de cima, com a diferença ou o aviso (até duas linhas)
local MARGEM_DO_MINIMAPA = 12
local DIFERENCA_MAXIMA_S = 20       -- mais que isto é a linha (o relógio do jogo ainda na volta anterior)
local LONGE_DA_REFERENCIA_M = 60    -- mais longe que isto da volta de referência (os boxes): sem diferença
local FPS_AMOSTRA_S = 1             -- o FPS do jogo lido a cada 1 s...
local FPS_REGISTRO_S = 10           -- ...e registrado no log a cada 10 s, com os mapas ligados ou desligados

-- O mapa aproximado, como a vista "fantasma por curva" da tela Volta.
local ZOOM_INICIAL_M = 120          -- o que cabe no lado menor da janela (a tela Volta abre com 150 m)
local ZOOM_MINIMO_M = 50            -- a roda do mouse, com o ponteiro sobre a janela, aproxima até isto...
local ZOOM_MAXIMO_M = 400           -- ...e afasta até isto
local CENTRO_VERTICAL = 0.62        -- o carro um pouco abaixo do meio: dá para ver mais da pista à frente
local GIRO_S = 0.15                 -- quanto a câmera demora para acompanhar a direção da pista
local RASTRO_PASSO_M = 1.5          -- o seu traçado: um ponto a cada 1,5 m...
local RASTRO_PERIODO_S = 0.05       -- ...lidos do jogo 20 vezes por segundo
local SALTO_M = 20                  -- mais que isto entre dois pontos (os boxes, um reset): o traço não liga

local CORES = {
  fundo = rgbm(0.031, 0.035, 0.043, 0.9),
  painel = rgbm(0.031, 0.035, 0.043, 0.62),
  vermelho = rgbm(0.882, 0.024, 0.0, 1),
  texto = rgbm(0.949, 0.957, 0.961, 1),
  apoio = rgbm(0.72, 0.76, 0.80, 1),
  fraco = rgbm(0.55, 0.59, 0.63, 1),
  -- As da tela Volta (frontend/src/theme/tokens.css): o carro é "você" e o fantasma é "fantasma".
  voce = rgbm(1, 1, 1, 1),
  fantasma = rgbm(0.914, 0.929, 0.949, 0.9),
  fantasmaMiolo = rgbm(0.031, 0.035, 0.043, 0.6),
  pista = rgbm(0.165, 0.184, 0.212, 1),       -- --pista-desenho (#2a2f36)
  borda = rgbm(0.914, 0.929, 0.949, 0.35),
  perda = rgbm(1.0, 0.635, 0.29, 1),          -- --perda (#ffa24a)
  ganho = rgbm(0.435, 0.608, 1.0, 1),         -- --ganho (#6f9bff)
  fundoDoMapa = rgbm(0.067, 0.071, 0.078, 0.92),
  branco = rgbm(1, 1, 1, 1),
  rotulo = rgbm(0.914, 0.929, 0.949, 0.75),
  faixaDoTexto = rgbm(0.067, 0.071, 0.078, 0.78),
}
-- O traçado pintado pelo pedal, como a tela Volta: 0 = parcial ou sem pedal, 1 = acelerador cheio, 2 = freio.
local CORES_DO_PEDAL = {
  [0] = rgbm(0.961, 0.773, 0.259, 1),        -- --parcial (#f5c542)
  [1] = rgbm(0.239, 0.863, 0.518, 1),        -- --acelerador (#3ddc84)
  [2] = rgbm(1.0, 0.353, 0.373, 1),          -- --freio (#ff5a5f)
}
local TAG = { coach = 'RÁDIO', resumo = 'VOLTA', analise = 'ANÁLISE', teste = 'TESTE' }

local function log(texto)
  if ac ~= nil and ac.log ~= nil then
    ac.log('[radio_engenheiro] ' .. texto)
  end
end

local function decimal(valor, casas)
  local s = string.format('%.' .. tostring(casas) .. 'f', valor)
  return (s:gsub('%.', ','))
end

-- A API que o app usa, conferida uma vez ao abrir. Confere só se existe: no CSP,
-- várias funções são nativas (FFI) e o `type()` delas é 'cdata', e não 'function'.
-- No teste no jogo de 18/10, conferir 'function' calou o app com a API inteira lá.
local function existe(tabela, nome)
  return tabela ~= nil and tabela[nome] ~= nil
end

local function conferir(usadas)
  local f = {}
  for _, u in ipairs(usadas) do
    if not existe(u[1], u[3]) then f[#f + 1] = u[2] .. '.' .. u[3] end
  end
  return f
end

local FALTA = conferir({
  { web, 'web', 'get' }, { web, 'web', 'timeouts' }, { JSON, 'JSON', 'parse' },
  { ui, 'ui', 'MediaPlayer' }, { ui, 'ui', 'dwriteDrawText' }, { ui, 'ui', 'dwriteDrawTextClipped' },
  { ui, 'ui', 'drawRectFilled' }, { ui, 'ui', 'windowSize' }, { os, 'os', 'preciseClock' }, { ac, 'ac', 'log' },
})
if setInterval == nil then FALTA[#FALTA + 1] = 'setInterval' end
-- O minimapa e o terceiro caminho da voz usam mais; sem isto, só eles ficam de fora.
local FALTA_NO_MINIMAPA = conferir({
  { ui, 'ui', 'ExtraCanvas' }, { ui, 'ui', 'drawImage' }, { ui, 'ui', 'pathClear' }, { ui, 'ui', 'pathLineTo' },
  { ui, 'ui', 'pathStroke' }, { ui, 'ui', 'drawLine' }, { ui, 'ui', 'drawCircle' }, { ui, 'ui', 'drawCircleFilled' },
  { ac, 'ac', 'getCar' }, { ac, 'ac', 'getSim' },
})
local FALTA_NA_PASTA = conferir({
  { ac, 'ac', 'getFolder' }, { ac, 'ac', 'FolderID' }, { io, 'io', 'load' }, { io, 'io', 'save' },
  { io, 'io', 'createDir' }, { io, 'io', 'scanDir' }, { io, 'io', 'deleteFile' }, { io, 'io', 'fileExists' },
})

local FALTA_NO_APROXIMADO = conferir({
  { ui, 'ui', 'drawImageQuad' }, { ui, 'ui', 'isImageReady' }, { ui, 'ui', 'drawTriangleFilled' },
  { ui, 'ui', 'windowHovered' }, { ui, 'ui', 'mouseWheel' },
})

local CALADO = #FALTA > 0
local MINIMAPA = not CALADO and #FALTA_NO_MINIMAPA == 0
local APROXIMADO = MINIMAPA and #FALTA_NO_APROXIMADO == 0
local ALINHAR_NO_INICIO = ui ~= nil and ui.Alignment ~= nil and ui.Alignment.Start or nil

-- A pasta do app (onde o instalar.ps1 o copiou) e a subpasta da voz baixada.
local PASTA = nil
local PASTA_DA_VOZ = nil
if not CALADO and #FALTA_NA_PASTA == 0 then
  local ok, pasta = pcall(ac.getFolder, ac.FolderID.ScriptOrigin)
  if ok and type(pasta) == 'string' and pasta ~= '' then
    PASTA = pasta
    PASTA_DA_VOZ = pasta .. '\\voz'
  end
end

-- O relógio do app: o do CSP ou, se ele faltar (o app calado), a soma dos dt dos quadros.
local somaDosQuadros = 0
local abertoEm = nil

local function relogio()
  if os.preciseClock ~= nil then
    return os.preciseClock()
  end
  return somaDosQuadros
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

local mini = {
  pista = nil,             -- {esquerda = {{x, z}, ...}, direita = {...}}
  origem = nil,            -- 'backend' ou 'arquivo do app'
  referencia = nil,        -- {tipo, tempoNaLinhaDoJogoS, pontos = {{x, z, t}, ...}}
  curvas = {},
  rotulos = {},            -- o nome das 14 curvas e onde ele vai: {curva, x, z}
  imagem = nil,            -- a pista detalhada: {arquivo, x0, y0, pxPorMetro, largura, altura}
  motivo = nil,
  versao = nil,            -- a versão que o rádio anunciou quando o app baixou o minimapa
  baixando = false,
  proximaTentativa = 0,
  avisouFalha = false,
  canvas = nil,
  desenhado = nil,
  tamanho = nil,
  mudouEm = nil,
  k = 1, ox = 0, oy = 0,
  ultimoQuadro = -100,
  voltas = nil,
  tempoAnterior = nil,
  desdeALinha = false,
  iFantasma = 1,
  iCarro = nil,
  diferenca = nil,
  mostrada = nil,
  mostradaEm = 0,
}

-- ── conversa com o backend (no máximo dois pedidos de uma vez) ──────────

local rede = { emVoo = 0, fila = {} }

local function bombear()
  while rede.emVoo < MAXIMO_DE_PEDIDOS and #rede.fila > 0 do
    local p = table.remove(rede.fila, 1)
    rede.emVoo = rede.emVoo + 1
    local ok = pcall(web.get, p.url, function(err, resposta)
      rede.emVoo = rede.emVoo - 1
      local okCb, erro = pcall(p.cb, err, resposta)
      if not okCb then log('erro: ' .. tostring(erro)) end
      bombear()
    end)
    if not ok then
      rede.emVoo = rede.emVoo - 1
      pcall(p.cb, 'o web.get recusou o pedido', nil)
    end
  end
end

local function pedirAoBackend(url, cb)
  rede.fila[#rede.fila + 1] = { url = url, cb = cb }
  bombear()
end

-- ── o minimapa: o que vem do backend (ou da pasta do app) ───────────────

local function lerAPistaDoApp()
  if not PASTA then return end
  local ok, texto = pcall(io.load, PASTA .. '\\pista.json')
  if not ok or type(texto) ~= 'string' then return end
  local okJ, dados = pcall(JSON.parse, texto)
  if okJ and type(dados) == 'table' and type(dados.pista) == 'table' then
    mini.pista = dados.pista
    mini.origem = 'arquivo do app'
    mini.desenhado = nil
    if type(dados.curvas) == 'table' then mini.rotulos = dados.curvas end
    if type(dados.imagem) == 'table' and type(dados.imagem.arquivo) == 'string' then
      mini.imagem = dados.imagem
      mini.imagem.caminho = PASTA .. '\\' .. dados.imagem.arquivo
    end
  end
end

local function baixarOMinimapa(versao)
  if not MINIMAPA or mini.baixando or relogio() < mini.proximaTentativa then return end
  mini.baixando = true
  pedirAoBackend(BACKEND .. '/api/radio/minimapa', function(err, r)
    mini.baixando = false
    local ok, dados = false, nil
    if not err and r and r.status == 200 then
      ok, dados = pcall(JSON.parse, r.body)
    end
    if not ok or type(dados) ~= 'table' then
      mini.proximaTentativa = relogio() + 5
      if not mini.avisouFalha then
        log('minimapa: o backend não entregou o minimapa (' .. tostring(err or (r and r.status)) .. '); tenta de novo a cada 5 s')
        mini.avisouFalha = true
      end
      return
    end
    mini.versao = versao
    if dados.disponivel == false or type(dados.pista) ~= 'table' then
      mini.motivo = tostring(dados.motivo or 'o backend não tem o minimapa')
      log('minimapa: ' .. mini.motivo)
      return
    end
    mini.pista = dados.pista
    mini.origem = 'backend'
    mini.referencia = type(dados.referencia) == 'table' and type(dados.referencia.pontos) == 'table'
      and dados.referencia or nil
    mini.curvas = type(dados.curvasDaAnalise) == 'table' and dados.curvasDaAnalise or {}
    if type(dados.curvas) == 'table' and #dados.curvas > 0 then mini.rotulos = dados.curvas end
    mini.motivo = mini.referencia == nil and 'o coach não tem a volta de referência' or nil
    mini.iFantasma, mini.iCarro = 1, nil
    mini.desenhado = nil
    local pontos = mini.referencia and #mini.referencia.pontos or 0
    log('minimapa: baixado (' .. tostring(versao) .. '); referência com ' .. pontos .. ' pontos; '
      .. #mini.curvas .. ' curva(s) da análise')
  end)
end

local function receber(err, resposta)
  estado.pedindo = false
  if err or not resposta or resposta.status ~= 200 then
    estado.fora = true
    if not estado.avisouFora then
      log('o backend não respondeu em ' .. BACKEND)
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
    local t = relogio()
    for _, m in ipairs(mensagens) do
      m.recebidaEm = t
      estado.fila[#estado.fila + 1] = m
    end
  end
  estado.instancia = dados.instancia
  estado.desde = tonumber(dados.ultimoId) or estado.desde
  -- O minimapa é baixado de novo quando a referência ou a análise mudam.
  local versao = tostring(dados.minimapaVersao or 'sem versão')
  if MINIMAPA and versao ~= mini.versao then
    baixarOMinimapa(versao)
  end
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
  pedirAoBackend(url, receber)
end

-- ── a voz: três caminhos, um depois do outro ────────────────────────────

local voz = { funciona = nil, tentativa = nil, ultimoBaixado = nil, jaTocou = false }

local function limparAVoz()
  if not PASTA_DA_VOZ then return end
  pcall(io.createDir, PASTA_DA_VOZ)
  local ok, nomes = pcall(io.scanDir, PASTA_DA_VOZ, '*.wav')
  if ok and type(nomes) == 'table' then
    for _, nome in ipairs(nomes) do
      pcall(io.deleteFile, PASTA_DA_VOZ .. '\\' .. nome)
    end
  end
end

local function lerOCaminhoGuardado()
  if not PASTA_DA_VOZ then return end
  local ok, texto = pcall(io.load, PASTA_DA_VOZ .. '\\caminho.txt')
  if not ok or type(texto) ~= 'string' then return end
  local nome = texto:match('^%s*(%a+)')
  for _, c in ipairs(CAMINHOS_DA_VOZ) do
    if c == nome then voz.funciona = c end
  end
end

local function guardarOCaminho(caminho)
  if voz.funciona == caminho then return end
  voz.funciona = caminho
  if PASTA_DA_VOZ then pcall(io.save, PASTA_DA_VOZ .. '\\caminho.txt', caminho) end
end

local function oPlayer()
  if not estado.player then
    local ok, player = pcall(ui.MediaPlayer, nil, { use3D = false, reverbResponse = false })
    if ok and player then estado.player = player end
  end
  return estado.player
end

local function tocarDe(fonte)
  local player = oPlayer()
  if not player then
    return false, 'o CSP não criou o player'
  end
  local ok, erro = pcall(function()
    player:setSource(fonte)
    player:setVolume(VOLUME_DO_RADIO)
    player:setAutoPlay(true)
    player:play()
  end)
  if not ok then
    return false, tostring(erro)
  end
  return true
end

-- O caminho que tocou da última vez vem primeiro; depois, os outros na ordem.
local function ordemDaVoz()
  local ordem = {}
  if voz.funciona then ordem[1] = voz.funciona end
  for _, c in ipairs(CAMINHOS_DA_VOZ) do
    if c ~= voz.funciona then ordem[#ordem + 1] = c end
  end
  return ordem
end

local function terminarSemVoz(a)
  log('voz: falhou: ' .. table.concat(a.falhas, '; ') .. ' (mensagem ' .. tostring(a.m.id) .. ')')
  voz.tentativa = nil
  pcall(function() estado.player:pause() end)
end

local proximoCaminho

local function falhar(a, motivo)
  a.falhas[#a.falhas + 1] = a.caminho .. ': ' .. motivo
  proximoCaminho(a)
end

proximoCaminho = function(a)
  if voz.tentativa ~= a then return end
  a.k = a.k + 1
  local caminho = a.ordem[a.k]
  if not caminho then
    terminarSemVoz(a)
    return
  end
  a.caminho = caminho
  a.inicio = relogio()
  a.fonte = nil
  a.baixando = false
  local m = a.m
  if caminho == 'url' then
    local ok, erro = tocarDe(BACKEND .. m.audio)
    if ok then a.fonte = BACKEND .. m.audio else falhar(a, erro) end
  elseif caminho == 'arquivo' then
    local arquivo = m.audioArquivo
    if type(arquivo) ~= 'string' or arquivo == '' then
      return falhar(a, 'o backend não mandou o caminho do arquivo')
    end
    local okE, existeOArquivo = pcall(io.fileExists, arquivo)
    if okE and existeOArquivo == false then
      return falhar(a, 'o app não enxerga ' .. arquivo)
    end
    local ok, erro = tocarDe(arquivo)
    if ok then a.fonte = arquivo else falhar(a, erro) end
  else
    if not PASTA_DA_VOZ then
      return falhar(a, 'sem a subpasta voz (a API do CSP não tem ' .. table.concat(FALTA_NA_PASTA, ', ') .. ')')
    end
    a.baixando = true
    pedirAoBackend(BACKEND .. m.audio, function(err, r)
      if voz.tentativa ~= a or a.caminho ~= 'baixado' then return end
      a.baixando = false
      if err or not r or r.status ~= 200 or type(r.body) ~= 'string' then
        return falhar(a, 'o download falhou (' .. tostring(err or (r and r.status)) .. ')')
      end
      local arquivo = PASTA_DA_VOZ .. '\\' .. tostring(m.id) .. '.wav'
      local okSalvar, salvou = pcall(io.save, arquivo, r.body)
      if not okSalvar or not salvou then
        return falhar(a, 'não gravou ' .. arquivo)
      end
      a.inicio = relogio()
      local ok, erro = tocarDe(arquivo)
      if not ok then
        return falhar(a, erro)
      end
      a.fonte = arquivo
      if voz.ultimoBaixado and voz.ultimoBaixado ~= arquivo then
        pcall(io.deleteFile, voz.ultimoBaixado)
      end
      voz.ultimoBaixado = arquivo
    end)
  end
end

local function falar(m)
  local antiga = voz.tentativa
  if antiga then
    antiga.falhas[#antiga.falhas + 1] = tostring(antiga.caminho) .. ': interrompida pela mensagem seguinte'
    terminarSemVoz(antiga)
  end
  if type(m.audio) ~= 'string' then
    log('voz: falhou: a mensagem ' .. tostring(m.id) .. ' veio sem áudio (a voz do Windows no backend)')
    return
  end
  local a = { m = m, ordem = ordemDaVoz(), k = 0, falhas = {},
              espera = voz.jaTocou and ESPERA_PARA_TOCAR_S or ESPERA_NA_PRIMEIRA_S }
  voz.tentativa = a
  proximoCaminho(a)
end

-- A cada quadro: tocou quando a posição do áudio anda (e não passa do tempo desde o
-- começo da tentativa, para não confundir com a posição da mensagem anterior).
local function acompanharAVoz(t)
  local a = voz.tentativa
  if not a then return end
  if a.fonte then
    local ok, posicao = pcall(function() return estado.player:currentTime() end)
    if ok and type(posicao) == 'number' and posicao > 0.05 and posicao < t - a.inicio + 0.5 then
      local antes = #a.falhas > 0 and (' (antes: ' .. table.concat(a.falhas, '; ') .. ')') or ''
      log('voz: ' .. a.caminho .. ' tocou' .. antes)
      guardarOCaminho(a.caminho)
      voz.jaTocou = true
      voz.tentativa = nil
      if estado.atual == a.m then
        estado.ateQuando = math.max(estado.ateQuando, t + (tonumber(a.m.duracaoS) or 3) + FOLGA_DEPOIS_DA_VOZ_S)
      end
      return
    end
  end
  if a.baixando then
    if t - a.inicio > ESPERA_DO_DOWNLOAD_S then
      a.baixando = false
      falhar(a, 'o download não terminou em ' .. ESPERA_DO_DOWNLOAD_S .. ' s')
    end
  elseif t - a.inicio > a.espera then
    falhar(a, 'não tocou em ' .. decimal(a.espera, 1) .. ' s')
  end
end

local function avancar(t)
  if estado.atual and t < estado.ateQuando then
    return
  end
  estado.atual = nil
  local proxima = table.remove(estado.fila, 1)
  while proxima and t - (proxima.recebidaEm or t) > MENSAGEM_VELHA_S do
    proxima = table.remove(estado.fila, 1)
  end
  if not proxima then
    return
  end
  estado.atual = proxima
  estado.inicio = t
  local minimo = proxima.origem == 'analise' and CARTAO_DA_ANALISE_S or CARTAO_MINIMO_S
  estado.ateQuando = t + math.max(minimo, (tonumber(proxima.duracaoS) or 3) + FOLGA_DEPOIS_DA_VOZ_S)
  falar(proxima)
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

local function caixa(texto, tamanhoDaFonte, p1, p2, cor)
  ui.dwriteDrawTextClipped(tostring(texto or ''), tamanhoDaFonte, p1, p2, ALINHAR_NO_INICIO, ALINHAR_NO_INICIO, true, cor)
end

local function desenharCartao(m, alfa, tamanho)
  local w = tamanho.x
  local linhas = type(m.linhas) == 'table' and #m.linhas > 0 and m.linhas or nil
  local h = 118
  if linhas then
    h = 104 + 38 * math.min(#linhas, 2) + 6
  end
  ui.drawRectFilled(vec2(0, 0), vec2(w, h), comAlfa(CORES.fundo, alfa), 10)
  ui.drawRectFilled(vec2(0, 0), vec2(6, h), comAlfa(CORES.vermelho, alfa), 3)
  ui.dwriteDrawText(TAG[m.origem] or 'RÁDIO', 13, vec2(20, 10), comAlfa(CORES.vermelho, alfa))
  ui.dwriteDrawText(corte(m.titulo, 52), 22, vec2(20, 28), comAlfa(CORES.texto, alfa))
  if linhas then
    -- A análise: o resumo em até duas linhas e uma linha por curva, com as diferenças.
    caixa(m.texto, 16, vec2(20, 58), vec2(w - 14, 100), comAlfa(CORES.texto, alfa))
    for i = 1, math.min(#linhas, 2) do
      local y = 104 + 38 * (i - 1)
      caixa(linhas[i], 13, vec2(20, y), vec2(w - 14, y + 36), comAlfa(CORES.apoio, alfa))
    end
    return
  end
  ui.dwriteDrawText(corte(m.texto, 66), 17, vec2(20, 60), comAlfa(CORES.texto, alfa))
  if type(m.detalhe) == 'string' and m.detalhe ~= '' then
    ui.dwriteDrawText(corte(m.detalhe, 90), 13, vec2(20, 88), comAlfa(CORES.apoio, alfa))
  end
end

local function desenharAviso(texto, tamanho)
  if ui.drawRectFilled ~= nil then
    ui.drawRectFilled(vec2(0, 0), vec2(tamanho.x, 56), CORES.fundo, 8)
  end
  if ui.dwriteDrawTextClipped ~= nil then
    caixa(texto, 13, vec2(14, 10), vec2(tamanho.x - 10, 52), CORES.apoio)
  elseif ui.dwriteDrawText ~= nil then
    ui.dwriteDrawText(corte(texto, 90), 13, vec2(14, 14), CORES.apoio)
  end
end

-- Chamada a cada quadro pela janela do rádio (manifest.ini, FUNCTION_MAIN).
function janela(dt)
  somaDosQuadros = somaDosQuadros + (tonumber(dt) or 0)
  local t = relogio()
  abertoEm = abertoEm or t
  local tamanho = ui.windowSize()
  if CALADO then
    -- O aviso fica os primeiros AVISO_S segundos depois de a janela abrir.
    if t - abertoEm < AVISO_S then
      desenharAviso('Rádio do engenheiro: esta versão do CSP não tem ' .. table.concat(FALTA, ', ') .. '.', tamanho)
    end
    return
  end
  avancar(t)
  acompanharAVoz(t)
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

-- ── o minimapa: a pista desenhada uma vez ───────────────────────────────

-- A mesma orientação do mapa do app (frontend/src/volta/projecao.ts): base(x, z) = (z, −x).
local function naTela(x, z)
  return vec2(mini.ox + mini.k * z, mini.oy - mini.k * x)
end

local function ajustarAEscala(W, H)
  local umin, umax, vmin, vmax = math.huge, -math.huge, math.huge, -math.huge
  for _, lado in ipairs({ mini.pista.esquerda, mini.pista.direita }) do
    for _, q in ipairs(lado) do
      local u, v = q[2], -q[1]
      umin, umax = math.min(umin, u), math.max(umax, u)
      vmin, vmax = math.min(vmin, v), math.max(vmax, v)
    end
  end
  local largura = W - 2 * MARGEM_DO_MINIMAPA
  local altura = H - 2 * MARGEM_DO_MINIMAPA - TOPO_DO_MINIMAPA
  local k = math.min(largura / math.max(umax - umin, 1), altura / math.max(vmax - vmin, 1))
  mini.k = k
  mini.ox = MARGEM_DO_MINIMAPA + (largura - k * (umax - umin)) / 2 - k * umin
  mini.oy = MARGEM_DO_MINIMAPA + TOPO_DO_MINIMAPA + (altura - k * (vmax - vmin)) / 2 - k * vmin
end

local function desenharAPista(W, H)
  if mini.canvas then
    pcall(function() mini.canvas:dispose() end)
    mini.canvas = nil
  end
  local ok, canvas = pcall(ui.ExtraCanvas, vec2(W, H))
  if not ok or not canvas then
    return
  end
  mini.canvas = canvas
  ajustarAEscala(W, H)
  local esquerda, direita = mini.pista.esquerda, mini.pista.direita
  local n = math.min(#esquerda, #direita)
  canvas:clear(rgbm(0, 0, 0, 0))
  canvas:update(function()
    ui.drawRectFilled(vec2(0, 0), vec2(W, H), CORES.painel, 10)
    -- O asfalto: a linha do meio, da largura média da pista; depois, as duas bordas.
    local largura = 0
    ui.pathClear()
    for i = 1, n do
      local e, d = esquerda[i], direita[i]
      largura = largura + math.sqrt((e[1] - d[1]) ^ 2 + (e[2] - d[2]) ^ 2)
      ui.pathLineTo(naTela((e[1] + d[1]) / 2, (e[2] + d[2]) / 2))
    end
    ui.pathStroke(CORES.pista, true, math.max(3, mini.k * largura / math.max(n, 1) + 1))
    for _, lado in ipairs({ esquerda, direita }) do
      ui.pathClear()
      for i = 1, n do
        ui.pathLineTo(naTela(lado[i][1], lado[i][2]))
      end
      ui.pathStroke(CORES.borda, true, 1)
    end
    -- A linha do s = 0 e as curvas da última análise.
    ui.drawLine(naTela(esquerda[1][1], esquerda[1][2]), naTela(direita[1][1], direita[1][2]), CORES.texto, 2)
    for _, c in ipairs(mini.curvas) do
      local q = naTela(tonumber(c.x) or 0, tonumber(c.z) or 0)
      ui.drawCircle(q, 7, CORES.perda, 16, 2)
      ui.dwriteDrawText(tostring(c.curva), 11, vec2(q.x + 9, q.y - 7), CORES.perda)
    end
  end)
  mini.desenhado = tostring(mini.versao) .. '|' .. tostring(mini.origem)
  mini.tamanho = W .. 'x' .. H
end

-- ── o minimapa: o fantasma e a diferença ────────────────────────────────

-- O cronômetro do jogo zera na linha do jogo, 1,463 m depois do s = 0 (pedido 33); o
-- tempo da referência conta desde o s = 0. O backend manda o tempo da referência
-- nesse ponto (`tempoNaLinhaDoJogoS`), e o app soma: tempo da referência = cronômetro
-- do jogo + tempoNaLinhaDoJogoS.
local function acompanharAVolta()
  local ok, carro = pcall(ac.getCar, 0)
  if not ok or not carro then return end
  local voltas = tonumber(carro.lapCount) or 0
  local tempo = tonumber(carro.lapTimeMs) or 0
  if mini.voltas ~= nil then
    if voltas > mini.voltas then
      mini.desdeALinha = true
      mini.iFantasma = 1
    elseif voltas < mini.voltas then
      mini.desdeALinha = false   -- a sessão recomeçou
      mini.diferenca = nil
    elseif mini.tempoAnterior and tempo + 5000 < mini.tempoAnterior then
      mini.desdeALinha = false   -- o cronômetro zerou no meio da volta (os boxes)
      mini.diferenca = nil
    end
  end
  mini.voltas = voltas
  mini.tempoAnterior = tempo
end

-- Onde o fantasma está: os pontos da referência têm o tempo desde o s = 0.
local function fantasmaEm(pontos, tRef)
  local n = #pontos
  if n < 2 then return nil end
  local i = mini.iFantasma
  if i < 1 or i >= n or pontos[i][3] > tRef then i = 1 end
  while i < n - 1 and pontos[i + 1][3] <= tRef do
    i = i + 1
  end
  mini.iFantasma = i
  local a, b = pontos[i], pontos[i + 1]
  local u = 0
  if b[3] > a[3] then u = math.max(0, math.min(1, (tRef - a[3]) / (b[3] - a[3]))) end
  return a[1] + (b[1] - a[1]) * u, a[2] + (b[2] - a[2]) * u
end

-- O tempo da referência no ponto dela mais perto do carro (projetado no segmento).
local function melhorEntre(pontos, x, z, de, ate)
  local melhor, tempo, indice = math.huge, nil, nil
  for i = de, ate do
    local p, q = pontos[i], pontos[i + 1]
    local dx, dz = q[1] - p[1], q[2] - p[2]
    local l2 = dx * dx + dz * dz
    local u = 0
    if l2 > 0 then u = math.max(0, math.min(1, ((x - p[1]) * dx + (z - p[2]) * dz) / l2)) end
    local ex, ez = p[1] + dx * u - x, p[2] + dz * u - z
    local d2 = ex * ex + ez * ez
    if d2 < melhor then
      melhor, tempo, indice = d2, p[3] + (q[3] - p[3]) * u, i
    end
  end
  return melhor, tempo, indice
end

local function tempoDaReferenciaPerto(pontos, x, z)
  local n = #pontos
  if n < 2 then return nil end
  local d2, tempo, indice = math.huge, nil, nil
  if mini.iCarro then
    d2, tempo, indice = melhorEntre(pontos, x, z, math.max(1, mini.iCarro - 8), math.min(n - 1, mini.iCarro + 25))
  end
  if d2 > 30 * 30 then
    d2, tempo, indice = melhorEntre(pontos, x, z, 1, n - 1)
  end
  mini.iCarro = indice
  if d2 > LONGE_DA_REFERENCIA_M * LONGE_DA_REFERENCIA_M then return nil end
  return tempo
end

local function desenharMarca(q, raio, miolo, borda, espessura)
  ui.drawCircleFilled(q, raio, miolo, 16)
  ui.drawCircle(q, raio, borda, 16, espessura)
end

-- O fantasma e a diferença, para as duas janelas de mapa. Devolve onde o fantasma está
-- (x, z), ou nada antes da primeira passagem pela linha ou sem a volta de referência.
local function oFantasma(carro)
  local ref = mini.referencia
  if not ref or not mini.desdeALinha then return nil end
  local tCarro = (tonumber(carro.lapTimeMs) or 0) / 1000 + (tonumber(ref.tempoNaLinhaDoJogoS) or 0)
  local fx, fz = fantasmaEm(ref.pontos, tCarro)
  -- A diferença ao vivo, calculada aqui: o tempo do carro menos o da referência no mesmo ponto.
  local tRef = tempoDaReferenciaPerto(ref.pontos, carro.position.x, carro.position.z)
  if tRef then
    local d = tCarro - tRef
    if math.abs(d) < DIFERENCA_MAXIMA_S then mini.diferenca = d end
  end
  return fx, fz
end

local function notaDoFantasma()
  if mini.referencia then
    if mini.desdeALinha then return nil end
    return 'o fantasma aparece depois da próxima passagem pela linha'
  end
  if estado.fora then return 'sem fantasma: backend fora do ar' end
  return 'sem fantasma: ' .. tostring(mini.motivo or 'lendo a volta de referência')
end

-- O texto de cima das duas janelas: a diferença (10 vezes por segundo, para ler sem
-- piscar) ou o aviso, que quebra a linha e cabe na largura da janela.
local function desenharODeCima(t, W, nota)
  if t - mini.mostradaEm >= 0.1 then
    mini.mostrada = mini.diferenca
    mini.mostradaEm = t
  end
  if nota then
    caixa(nota, 11, vec2(MARGEM_DO_MINIMAPA, 4), vec2(W - 8, TOPO_DO_MINIMAPA + 2), CORES.fraco)
  elseif mini.mostrada then
    local d = mini.mostrada
    local sinal = d >= 0 and '+' or '−'
    ui.dwriteDrawText(sinal .. decimal(math.abs(d), 2) .. ' s', 17, vec2(MARGEM_DO_MINIMAPA, 4),
      d > 0 and CORES.perda or CORES.ganho)
    local ref = mini.referencia
    local contra = ref and ref.tipo == 'minha_melhor' and 'para a sua melhor' or 'para a volta da IA'
    ui.dwriteDrawText(contra, 11, vec2(MARGEM_DO_MINIMAPA + 82, 10), CORES.apoio)
  end
end

-- Chamada a cada quadro pela janela do minimapa (manifest.ini, FUNCTION_MAIN).
function minimapa(dt)
  local t = relogio()
  mini.ultimoQuadro = t
  local tamanho = ui.windowSize()
  if CALADO or not MINIMAPA then
    local falta = CALADO and FALTA or FALTA_NO_MINIMAPA
    desenharAviso('Minimapa: esta versão do CSP não tem ' .. table.concat(falta, ', ') .. '.', tamanho)
    return
  end
  if not mini.pista then
    desenharAviso('Minimapa: sem a pista (nem do backend, nem a pista.json da pasta do app).', tamanho)
    return
  end
  local W, H = math.floor(tamanho.x), math.floor(tamanho.y)
  local agoraTamanho = W .. 'x' .. H
  if mini.tamanho ~= agoraTamanho then
    mini.mudouEm = mini.mudouEm or t
  else
    mini.mudouEm = nil
  end
  -- A pista é redesenhada só quando o minimapa muda ou a janela para de mudar de tamanho.
  if not mini.canvas or mini.desenhado ~= tostring(mini.versao) .. '|' .. tostring(mini.origem)
      or (mini.mudouEm and t - mini.mudouEm > 0.3) then
    desenharAPista(W, H)
    mini.mudouEm = nil
  end
  if mini.canvas then
    ui.drawImage(mini.canvas, vec2(0, 0), vec2(W, H))
  end

  local ok, carro = pcall(ac.getCar, 0)
  if not ok or not carro then return end
  local fx, fz = oFantasma(carro)
  if fx then
    desenharMarca(naTela(fx, fz), 5, CORES.fantasmaMiolo, CORES.fantasma, 2)
  end
  desenharMarca(naTela(carro.position.x, carro.position.z), 5.5, CORES.voce, CORES.vermelho, 2.5)
  desenharODeCima(t, W, notaDoFantasma())
  if estado.fora and mini.referencia then
    ui.dwriteDrawText('sem backend', 11, vec2(W - 74, H - 18), CORES.fraco)
  end
end

-- ── o mapa aproximado: a vista de perto da tela Volta ───────────────────

local perto = { zoom = ZOOM_INICIAL_M, angulo = nil, ultimoQuadro = -100 }
local rastro = { pontos = {}, voltas = nil }

-- O seu traçado da volta, lido do jogo 20 vezes por segundo: {x, z, pedal}. Começa de novo na linha.
local function gravarORastro()
  local ok, carro = pcall(ac.getCar, 0)
  if not ok or not carro then return end
  local voltas = tonumber(carro.lapCount) or 0
  if rastro.voltas ~= nil and voltas ~= rastro.voltas then
    rastro.pontos = {}
  end
  rastro.voltas = voltas
  local x, z = carro.position.x, carro.position.z
  local n = #rastro.pontos
  local ultimo = rastro.pontos[n]
  if ultimo and (x - ultimo[1]) ^ 2 + (z - ultimo[2]) ^ 2 < RASTRO_PASSO_M * RASTRO_PASSO_M then return end
  local pedal = 0
  if (tonumber(carro.brake) or 0) >= 0.15 then
    pedal = 2
  elseif (tonumber(carro.gas) or 0) >= 0.9 then
    pedal = 1
  end
  if n >= 5000 then table.remove(rastro.pontos, 1) end
  rastro.pontos[#rastro.pontos + 1] = { x, z, pedal }
end

-- Um traçado na tela, em trechos da mesma cor; os pontos fora da janela ficam de fora.
-- `ip` é a posição do pedal em cada ponto ({x, z, t, pedal} na referência, {x, z, pedal} no seu).
local function tracar(pontos, ate, ip, alfa, largura, tela, W, H)
  local aberto, cor = false, 0
  local ax, az = nil, nil
  for i = 1, math.min(ate, #pontos) do
    local p = pontos[i]
    local sx, sy = tela(p[1], p[2])
    local visivel = sx > -40 and sx < W + 40 and sy > -40 and sy < H + 40
    local pedal = p[ip] or 0
    local salto = ax ~= nil and (p[1] - ax) ^ 2 + (p[2] - az) ^ 2 > SALTO_M * SALTO_M
    if aberto and (not visivel or salto or pedal ~= cor) then
      if visivel and not salto then ui.pathLineTo(vec2(sx, sy)) end
      ui.pathStroke(comAlfa(CORES_DO_PEDAL[cor] or CORES_DO_PEDAL[0], alfa), false, largura)
      aberto = false
    end
    if visivel then
      if not aberto then
        ui.pathClear()
        aberto, cor = true, pedal
      end
      ui.pathLineTo(vec2(sx, sy))
    end
    ax, az = p[1], p[2]
  end
  if aberto then
    ui.pathStroke(comAlfa(CORES_DO_PEDAL[cor] or CORES_DO_PEDAL[0], alfa), false, largura)
  end
end

local function rotuloCentrado(texto, tamanhoDaFonte, sx, sy, cor)
  local largura = #texto * tamanhoDaFonte * 0.55
  if ui.measureDWriteText ~= nil then
    local ok, medida = pcall(ui.measureDWriteText, texto, tamanhoDaFonte)
    if ok and medida then largura = medida.x end
  end
  ui.dwriteDrawText(texto, tamanhoDaFonte, vec2(sx - largura / 2, sy - tamanhoDaFonte / 2), cor)
end

-- Chamada a cada quadro pela janela do mapa aproximado (manifest.ini, FUNCTION_MAIN).
function aproximado(dt)
  local t = relogio()
  perto.ultimoQuadro = t
  local tamanho = ui.windowSize()
  if CALADO or not APROXIMADO then
    local falta = CALADO and FALTA or (#FALTA_NO_MINIMAPA > 0 and FALTA_NO_MINIMAPA or FALTA_NO_APROXIMADO)
    desenharAviso('Mapa aproximado: esta versão do CSP não tem ' .. table.concat(falta, ', ') .. '.', tamanho)
    return
  end
  local ok, carro = pcall(ac.getCar, 0)
  if not ok or not carro then return end
  local W, H = tamanho.x, tamanho.y

  -- O zoom pela roda do mouse, com o ponteiro sobre a janela.
  if ui.windowHovered() then
    local roda = tonumber(ui.mouseWheel()) or 0
    if roda ~= 0 then
      perto.zoom = math.max(ZOOM_MINIMO_M, math.min(ZOOM_MAXIMO_M, perto.zoom * (roda > 0 and 1 / 1.15 or 1.15)))
    end
  end
  local fx, fz = oFantasma(carro)

  -- A câmera: o carro fixo na janela e a pista girando, como a tela Volta (base(x, z) = (z, −x)).
  -- A direção é a da volta de referência perto do carro (mais estável que a do carro numa
  -- escorregada) ou, sem ela, a do carro.
  local x, z = carro.position.x, carro.position.z
  local du, dv = nil, nil
  local ref = mini.referencia
  if ref and mini.iCarro then
    local a, b = ref.pontos[mini.iCarro], ref.pontos[math.min(#ref.pontos, mini.iCarro + 4)]
    if a and b then du, dv = b[2] - a[2], -(b[1] - a[1]) end
  end
  if not du or du * du + dv * dv < 1 then
    du, dv = carro.look.z, -carro.look.x
  end
  local alvo = -math.pi / 2 - math.atan2(dv, du)
  if perto.angulo == nil then
    perto.angulo = alvo
  else
    local giro = (alvo - perto.angulo + math.pi) % (2 * math.pi) - math.pi
    perto.angulo = perto.angulo + giro * math.min(1, (tonumber(dt) or 0.016) / GIRO_S)
  end
  local cs, sn = math.cos(perto.angulo), math.sin(perto.angulo)
  local k = math.min(W, H) / perto.zoom
  local cx, cy = W * 0.5, H * CENTRO_VERTICAL
  local bu0, bv0 = z, -x
  local function tela(px, pz)
    local eu, ev = pz - bu0, -px - bv0
    return cx + k * (eu * cs - ev * sn), cy + k * (eu * sn + ev * cs)
  end

  ui.drawRectFilled(vec2(0, 0), vec2(W, H), CORES.fundoDoMapa, 6)

  -- A pista detalhada: a imagem girada em volta do carro. Cada canto da janela volta para o
  -- mundo e daí para a imagem (coluna = (x − x0)·k; linha = (−z − y0)·k).
  local img = mini.imagem
  local pronta = false
  if img then
    local function uv(sx, sy)
      local ex, ey = (sx - cx) / k, (sy - cy) / k
      local bu, bv = bu0 + ex * cs + ey * sn, bv0 - ex * sn + ey * cs
      local mx, my = -bv, -bu          -- o mundo (x = −bv, z = bu) nas coordenadas do mapa (x, −z)
      return vec2((mx - img.x0) * img.pxPorMetro / img.largura, (my - img.y0) * img.pxPorMetro / img.altura)
    end
    ui.drawImageQuad(img.caminho, vec2(0, 0), vec2(W, 0), vec2(W, H), vec2(0, H), CORES.branco,
      uv(0, 0), uv(W, 0), uv(W, H), uv(0, H))
    local okP, p = pcall(ui.isImageReady, img.caminho)
    pronta = okP and p
  end
  if not pronta and mini.pista then
    -- Sem a imagem (ou enquanto ela carrega): as bordas do asfalto, como no minimapa.
    for _, lado in ipairs({ mini.pista.esquerda, mini.pista.direita }) do
      ui.pathClear()
      for _, q in ipairs(lado) do
        local sx, sy = tela(q[1], q[2])
        ui.pathLineTo(vec2(sx, sy))
      end
      ui.pathStroke(CORES.borda, true, 1.5)
    end
  end

  -- Os traçados: o do fantasma até onde ele está, mais apagado; o seu desde a linha.
  if ref and mini.desdeALinha then
    tracar(ref.pontos, mini.iFantasma + 1, 4, 0.6, 3.5, tela, W, H)
  end
  tracar(rastro.pontos, #rastro.pontos, 3, 1.0, 5, tela, W, H)

  -- O nome das curvas que estão na janela.
  for _, c in ipairs(mini.rotulos) do
    local sx, sy = tela(tonumber(c.x) or 0, tonumber(c.z) or 0)
    if sx > 12 and sx < W - 12 and sy > TOPO_DO_MINIMAPA + 8 and sy < H - 8 then
      rotuloCentrado(tostring(c.curva), 12, sx, sy, CORES.rotulo)
    end
  end

  -- O fantasma (ou uma seta na borda, se ele estiver fora da janela) e o carro.
  local rotuloDaRef = ref and ref.tipo == 'minha_melhor' and 'Sua melhor' or 'IA'
  if fx then
    local gx, gy = tela(fx, fz)
    if gx > 14 and gx < W - 14 and gy > 14 and gy < H - 14 then
      desenharMarca(vec2(gx, gy), 8, CORES.fantasmaMiolo, CORES.fantasma, 2.5)
      rotuloCentrado(rotuloDaRef, 12, gx, gy - 16, CORES.texto)
    else
      local mx, my = math.max(18, math.min(W - 18, gx)), math.max(18, math.min(H - 18, gy))
      local a = math.atan2(gy - cy, gx - cx)
      local ca, sa = math.cos(a), math.sin(a)
      local function girado(px, py) return vec2(mx + px * ca - py * sa, my + px * sa + py * ca) end
      ui.drawTriangleFilled(girado(8, 0), girado(-6, -6), girado(-6, 6), CORES.fantasma)
    end
  end
  desenharMarca(vec2(cx, cy), 8.5, CORES.voce, CORES.vermelho, 2.5)
  rotuloCentrado('Você · V' .. tostring((tonumber(carro.lapCount) or 0) + 1), 12, cx, cy + 18, CORES.texto)

  -- O texto de cima numa faixa escura: a pista passa por baixo dele.
  ui.drawRectFilled(vec2(0, 0), vec2(W, TOPO_DO_MINIMAPA + 2), CORES.faixaDoTexto, 6)
  desenharODeCima(t, W, notaDoFantasma())
  if estado.fora and ref then
    ui.dwriteDrawText('sem backend', 11, vec2(W - 74, H - 18), CORES.fraco)
  end
end

-- ── o custo no jogo: o FPS com os mapas ligados e desligados ────────────

local function novaContagem()
  return { soma = 0, n = 0, minimo = math.huge, maximo = 0, parado = 0,
           mini = { ligado = 0, desligado = 0 }, perto = { ligado = 0, desligado = 0 } }
end
local fps = novaContagem()

local function situacao(c)
  if c.desligado == 0 then return 'ligado' end
  if c.ligado == 0 then return 'desligado' end
  return 'ligado e desligado'
end

local function amostrarOFps()
  local ok, sim = pcall(ac.getSim)
  if not ok or not sim then return end
  if sim.isPaused or sim.isReplayActive then
    fps.parado = fps.parado + 1
  else
    local v = tonumber(sim.fps) or 0
    fps.soma = fps.soma + v
    fps.n = fps.n + 1
    fps.minimo = math.min(fps.minimo, v)
    fps.maximo = math.max(fps.maximo, v)
    local agora = relogio()
    for nome, ultimo in pairs({ mini = mini.ultimoQuadro, perto = perto.ultimoQuadro }) do
      local c = fps[nome]
      if agora - ultimo < 0.5 then c.ligado = c.ligado + 1 else c.desligado = c.desligado + 1 end
    end
  end
  if fps.n + fps.parado >= FPS_REGISTRO_S / FPS_AMOSTRA_S then
    if fps.n > 0 then
      log('fps: média ' .. decimal(fps.soma / fps.n, 1) .. ' (mín ' .. decimal(fps.minimo, 0) .. ', máx '
        .. decimal(fps.maximo, 0) .. ') em ' .. fps.n .. ' s; minimapa ' .. situacao(fps.mini)
        .. '; mapa aproximado ' .. situacao(fps.perto))
    end
    fps = novaContagem()
  end
end

-- ── ao abrir ────────────────────────────────────────────────────────────

if CALADO then
  log('a API do CSP não tem: ' .. table.concat(FALTA, ', ') .. '. O app fica calado.')
else
  log('ligado; pede as mensagens a ' .. BACKEND)
  if #FALTA_NO_MINIMAPA > 0 then
    log('minimapa desligado: a API do CSP não tem ' .. table.concat(FALTA_NO_MINIMAPA, ', '))
  elseif #FALTA_NO_APROXIMADO > 0 then
    log('mapa aproximado desligado: a API do CSP não tem ' .. table.concat(FALTA_NO_APROXIMADO, ', '))
  end
  if not PASTA_DA_VOZ then
    log('voz: sem o terceiro caminho (a pasta do app): ' .. (#FALTA_NA_PASTA > 0 and table.concat(FALTA_NA_PASTA, ', ') or 'sem a pasta'))
  end
  limparAVoz()
  lerOCaminhoGuardado()
  if voz.funciona then
    log('voz: começa pelo caminho que tocou da última vez: ' .. voz.funciona)
  end
  pcall(web.timeouts, 500, 500, 1000, 1500)
  -- O player é criado já ao abrir: na primeira vez, o CSP carrega o Media Foundation.
  oPlayer()
  pcall(function()
    ui.MediaPlayer.supportedAsync(function(suportado)
      log('voz: Media Foundation ' .. (suportado and 'disponível' or 'indisponível neste Windows'))
    end)
  end)
  setInterval(pedir, PERIODO_S)
  if MINIMAPA then
    lerAPistaDoApp()
    if APROXIMADO and not mini.imagem then
      log('mapa aproximado: sem a pista_detalhada.png na pasta do app; desenha só as bordas da pista')
    end
    setInterval(acompanharAVolta, 0.25)
    setInterval(gravarORastro, RASTRO_PERIODO_S)
    setInterval(amostrarOFps, FPS_AMOSTRA_S)
  end
end
