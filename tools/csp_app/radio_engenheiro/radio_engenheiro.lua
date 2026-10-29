-- Rádio do engenheiro (pedido 31, ADR 0020; pedido 35, ADR 0021).
--
-- Quatro janelas, cada uma ligada e desligada na barra de apps do jogo (manifest.ini):
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
--     pedal, o carro, o fantasma, o nome das curvas e a diferença;
--   * o replay da curva (`replay`, pedido 36, Parte E): a curva citada pelo rádio, vista de
--     cima, com a sua linha e a da referência, os dois carros, as freadas, as mínimas, o
--     traçado e o tempo perdido. Na reta, junto com a fala; nos boxes, a última análise.
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
  contorno = rgbm(0.914, 0.929, 0.949, 0.6),  -- o contorno do asfalto no minimapa
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
  pista = nil,             -- {origem, contornos = {{{x, z}, ...}, ...}}: o contorno do asfalto tratado
  linhaDoS0 = nil,         -- a marca da linha do s = 0: {{x, z}, {x, z}}
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
  if okJ and type(dados) == 'table' and type(dados.pista) == 'table' and type(dados.pista.contornos) == 'table' then
    mini.pista = dados.pista
    mini.comprimento = tonumber(dados.comprimentoM) or mini.comprimento
    mini.linhaDoS0 = type(dados.linhaDoS0) == 'table' and dados.linhaDoS0 or nil
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
    if dados.disponivel == false or type(dados.pista) ~= 'table' or type(dados.pista.contornos) ~= 'table' then
      mini.motivo = tostring(dados.motivo or 'o backend não tem o minimapa')
      log('minimapa: ' .. mini.motivo)
      return
    end
    mini.pista = dados.pista
    mini.comprimento = tonumber(dados.comprimentoM) or mini.comprimento
    mini.linhaDoS0 = type(dados.linhaDoS0) == 'table' and dados.linhaDoS0 or mini.linhaDoS0
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

-- Pedido 36: o replay da curva começa junto com o cartão (definido mais abaixo, na seção do replay).
local comecarReplay

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
  if comecarReplay then comecarReplay(proxima, t) end
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

-- Pedido 36, Parte D.1: a parte da janela que está na tela. Uma janela posta na borda
-- da tela fica com um pedaço para fora, e o desenho que encaixava na janela inteira saía
-- cortado. As medidas usam a posição da janela e o tamanho da tela da interface do CSP
-- (as mesmas unidades, já com a escala da interface).
local function areaVisivel(W, H)
  local x0, y0, x1, y1 = 0, 0, W, H
  local okP, pos = pcall(ui.windowPos)
  local okU, estadoUi = pcall(ac.getUI)
  if okP and pos and okU and estadoUi and estadoUi.windowSize then
    local tela = estadoUi.windowSize
    x0, y0 = math.max(0, -pos.x), math.max(0, -pos.y)
    x1, y1 = math.min(W, tela.x - pos.x), math.min(H, tela.y - pos.y)
    if x1 - x0 < 80 or y1 - y0 < 80 then x0, y0, x1, y1 = 0, 0, W, H end
  end
  return math.floor(x0), math.floor(y0), math.floor(x1), math.floor(y1)
end

-- Uma vez por janela, as medidas no log do CSP, para conferir no jogo o que corta.
local medidasRegistradas = {}
local function registrarAsMedidas(nome, W, H)
  if medidasRegistradas[nome] then return end
  medidasRegistradas[nome] = true
  local okP, pos = pcall(ui.windowPos)
  local okU, estadoUi = pcall(ac.getUI)
  local okC, cursor = pcall(ui.getCursor)
  local function par(v) return v and (decimal(v.x, 0) .. ' x ' .. decimal(v.y, 0)) or '?' end
  local x0, y0, x1, y1 = areaVisivel(W, H)
  log(nome .. ': janela ' .. decimal(W, 0) .. ' x ' .. decimal(H, 0) .. ' em ' .. par(okP and pos)
    .. '; tela ' .. par(okU and estadoUi and estadoUi.windowSize) .. ', escala ' .. decimal(okU and estadoUi and estadoUi.uiScale or 1, 2)
    .. '; cursor ' .. par(okC and cursor) .. '; visível de ' .. x0 .. ',' .. y0 .. ' a ' .. x1 .. ',' .. y1)
end

-- Desenha `corpo` com o recorte na janela inteira: o recorte padrão do ImGui tira uma faixa
-- das bordas (metade do espaçamento interno), como o app Mumble do próprio CSP evita.
local function naJanelaInteira(W, H, corpo, ...)
  local recorte = ui.pushClipRect ~= nil and ui.popClipRect ~= nil
  if recorte then ui.pushClipRect(vec2(0, 0), vec2(W, H), false) end
  local ok, erro = pcall(corpo, ...)
  if recorte then ui.popClipRect() end
  if not ok then error(erro, 0) end
end

-- A mesma orientação do mapa do app (frontend/src/volta/projecao.ts): base(x, z) = (z, −x).
local function naTela(x, z)
  return vec2(mini.ox + mini.k * z, mini.oy - mini.k * x)
end

local function ajustarAEscala(W, H)
  local x0, y0, x1, y1 = areaVisivel(W, H)
  local umin, umax, vmin, vmax = math.huge, -math.huge, math.huge, -math.huge
  for _, contorno in ipairs(mini.pista.contornos) do
    for _, q in ipairs(contorno) do
      local u, v = q[2], -q[1]
      umin, umax = math.min(umin, u), math.max(umax, u)
      vmin, vmax = math.min(vmin, v), math.max(vmax, v)
    end
  end
  local largura = (x1 - x0) - 2 * MARGEM_DO_MINIMAPA
  local altura = (y1 - y0) - 2 * MARGEM_DO_MINIMAPA - TOPO_DO_MINIMAPA
  local k = math.min(largura / math.max(umax - umin, 1), altura / math.max(vmax - vmin, 1))
  mini.k = k
  mini.ox = x0 + MARGEM_DO_MINIMAPA + (largura - k * (umax - umin)) / 2 - k * umin
  mini.oy = y0 + MARGEM_DO_MINIMAPA + TOPO_DO_MINIMAPA + (altura - k * (vmax - vmin)) / 2 - k * vmin
  mini.visivel = { x0, y0, x1, y1 }
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
  canvas:clear(rgbm(0, 0, 0, 0))
  canvas:update(function()
    ui.drawRectFilled(vec2(0, 0), vec2(W, H), CORES.painel, 10)
    -- O contorno do asfalto tratado (o de fora, o do miolo, as áreas de escape e dos boxes).
    for _, contorno in ipairs(mini.pista.contornos) do
      ui.pathClear()
      for _, q in ipairs(contorno) do
        ui.pathLineTo(naTela(q[1], q[2]))
      end
      ui.pathStroke(CORES.contorno, true, 1.6)
    end
    -- A marca da linha do s = 0 e as curvas da última análise.
    local l = mini.linhaDoS0
    if l and l[1] and l[2] then
      ui.drawLine(naTela(l[1][1], l[1][2]), naTela(l[2][1], l[2][2]), CORES.texto, 2)
    end
    for _, c in ipairs(mini.curvas) do
      local q = naTela(tonumber(c.x) or 0, tonumber(c.z) or 0)
      ui.drawCircle(q, 7, CORES.perda, 16, 2)
      -- O nome do lado de dentro quando a marca está perto da borda direita.
      local nx = q.x + 9 + 26 > mini.visivel[3] and q.x - 9 - 26 or q.x + 9
      ui.dwriteDrawText(tostring(c.curva), 11, vec2(nx, q.y - 7), CORES.perda)
    end
  end)
  mini.desenhado = tostring(mini.versao) .. '|' .. tostring(mini.origem)
  mini.tamanho = W .. 'x' .. H .. '|' .. table.concat(mini.visivel, ',')
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
local function desenharODeCima(t, W, nota, x0, y0)
  x0, y0 = x0 or 0, y0 or 0
  if t - mini.mostradaEm >= 0.1 then
    mini.mostrada = mini.diferenca
    mini.mostradaEm = t
  end
  if nota then
    caixa(nota, 11, vec2(x0 + MARGEM_DO_MINIMAPA, y0 + 4), vec2(W - 8, y0 + TOPO_DO_MINIMAPA + 2), CORES.fraco)
  elseif mini.mostrada then
    local d = mini.mostrada
    local sinal = d >= 0 and '+' or '−'
    ui.dwriteDrawText(sinal .. decimal(math.abs(d), 2) .. ' s', 17, vec2(x0 + MARGEM_DO_MINIMAPA, y0 + 4),
      d > 0 and CORES.perda or CORES.ganho)
    local ref = mini.referencia
    local contra = ref and ref.tipo == 'minha_melhor' and 'para a sua melhor' or 'para a volta da IA'
    ui.dwriteDrawText(contra, 11, vec2(x0 + MARGEM_DO_MINIMAPA + 82, y0 + 10), CORES.apoio)
  end
end

-- Pedido 36, Parte D.2: a freada da IA na próxima curva, pela posição do carro na volta de
-- referência (o índice do ponto mais perto e o passo da grade).
local function proximaFreada(carro)
  local ref = mini.referencia
  if not ref or type(ref.freadas) ~= 'table' or #ref.freadas == 0 then return nil end
  tempoDaReferenciaPerto(ref.pontos, carro.position.x, carro.position.z)
  local L = tonumber(mini.comprimento) or 0
  if not mini.iCarro or L <= 0 then return nil end
  local s = (mini.iCarro - 1) * L / #ref.pontos
  local melhor, menor = nil, math.huge
  for _, f in ipairs(ref.freadas) do
    local d = ((tonumber(f.s) or 0) - s) % L
    if d < menor then melhor, menor = f, d end
  end
  return melhor
end

local desenharMinimapa

-- Chamada a cada quadro pela janela do minimapa (manifest.ini, FUNCTION_MAIN).
function minimapa(dt)
  local tamanho = ui.windowSize()
  naJanelaInteira(tamanho.x, tamanho.y, desenharMinimapa, dt)
end

desenharMinimapa = function(dt)
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
  registrarAsMedidas('minimapa', W, H)
  local agoraTamanho = W .. 'x' .. H .. '|' .. table.concat({ areaVisivel(W, H) }, ',')
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
  -- A freada da IA só na próxima curva: uma marca curta atravessando a pista, na cor do fantasma.
  local f = proximaFreada(carro)
  if f and f.pontos and f.pontos[1] and f.pontos[2] then
    local a, b = naTela(f.pontos[1][1], f.pontos[1][2]), naTela(f.pontos[2][1], f.pontos[2][2])
    local mx, my, dx, dy = (a.x + b.x) / 2, (a.y + b.y) / 2, b.x - a.x, b.y - a.y
    local n = math.sqrt(dx * dx + dy * dy)
    if n > 0.01 then
      dx, dy = dx / n * 7, dy / n * 7
      ui.drawLine(vec2(mx - dx, my - dy), vec2(mx + dx, my + dy), CORES.fantasma, 3)
    end
  end
  local fx, fz = oFantasma(carro)
  if fx then
    desenharMarca(naTela(fx, fz), 5, CORES.fantasmaMiolo, CORES.fantasma, 2)
  end
  desenharMarca(naTela(carro.position.x, carro.position.z), 5.5, CORES.voce, CORES.vermelho, 2.5)
  local v = mini.visivel or { 0, 0, W, H }
  desenharODeCima(t, v[3], notaDoFantasma(), v[1], v[2])
  if estado.fora and mini.referencia then
    ui.dwriteDrawText('sem backend', 11, vec2(v[3] - 74, v[4] - 18), CORES.fraco)
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

local desenharAproximado

-- Chamada a cada quadro pela janela do mapa aproximado (manifest.ini, FUNCTION_MAIN).
function aproximado(dt)
  local tamanho = ui.windowSize()
  naJanelaInteira(tamanho.x, tamanho.y, desenharAproximado, dt)
end

desenharAproximado = function(dt)
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
  registrarAsMedidas('mapa aproximado', W, H)
  local vx0, vy0, vx1, vy1 = areaVisivel(W, H)

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
  local k = math.min(vx1 - vx0, vy1 - vy0) / perto.zoom
  local cx, cy = (vx0 + vx1) * 0.5, vy0 + (vy1 - vy0) * CENTRO_VERTICAL
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
    -- Sem a imagem (ou enquanto ela carrega): o contorno do asfalto, como no minimapa.
    for _, contorno in ipairs(mini.pista.contornos) do
      ui.pathClear()
      for _, q in ipairs(contorno) do
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

  -- Pedido 36, Parte D.2: a freada da IA em todas as curvas da janela, uma linha atravessando o
  -- asfalto (um pouco além das bordas) com o rótulo. O seu traçado mostra onde você freou: o
  -- vermelho começa ali.
  if ref and type(ref.freadas) == 'table' then
    local rotuloDaFreada = ref.tipo == 'minha_melhor' and 'freada da sua melhor' or 'freada da IA'
    for _, f in ipairs(ref.freadas) do
      if f.pontos and f.pontos[1] and f.pontos[2] then
        local ax, ay = tela(f.pontos[1][1], f.pontos[1][2])
        local bx, by = tela(f.pontos[2][1], f.pontos[2][2])
        local mx, my = (ax + bx) / 2, (ay + by) / 2
        if mx > -40 and mx < W + 40 and my > -40 and my < H + 40 then
          local ex, ey = (bx - ax) * 0.15, (by - ay) * 0.15
          ui.drawLine(vec2(ax - ex, ay - ey), vec2(bx + ex, by + ey), CORES.fantasma, 2.5)
          local lx, ly = bx + ex, by + ey
          if ax - ex > lx then lx, ly = ax - ex, ay - ey end
          ui.dwriteDrawText(rotuloDaFreada, 11, vec2(lx + 4, ly - 7), CORES.fantasma)
        end
      end
    end
  end

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
  ui.drawRectFilled(vec2(vx0, vy0), vec2(vx1, vy0 + TOPO_DO_MINIMAPA + 2), CORES.faixaDoTexto, 6)
  desenharODeCima(t, vx1, notaDoFantasma(), vx0, vy0)
  if estado.fora and ref then
    ui.dwriteDrawText('sem backend', 11, vec2(vx1 - 74, vy1 - 18), CORES.fraco)
  end
end

-- ── o replay da curva (pedido 36, Parte E) ──────────────────────────────

-- O que o engenheiro mostra quando fala de uma curva: a curva vista de cima, sobre a pista
-- tratada (a `pista_detalhada.png`), com as duas linhas ("você" e "IA (referência)"), os dois
-- carros andando cada um no seu próprio tempo a partir da mesma entrada, as duas freadas com
-- a distância, as duas mínimas com o valor, o traçado e o tempo perdido. Os dados vêm de
-- `/api/radio/replay/<id>`, uma vez por mensagem.
--
-- * Na reta: aparece junto com a fala de uma análise ou de uma frase do coach com causa,
--   toca cada curva citada e some quando a janela de rádio acaba (o `restaS` da mensagem,
--   calculado pelo backend na entrega). Nunca dentro das 14 curvas.
-- * Nos boxes ou com o jogo pausado: a última análise, em repetição e com a janela maior,
--   até você sair.
-- Pedido 43:
-- * na frase do coach, os números da voz (a freada, as mínimas e o tempo, onde o coach mediu)
--   e o trecho da fala, uma faixa clara na pista e nos visuais; sem o traçado (o coach não o mede);
-- * sob a animação, os visuais: a faixa do pedal, a diferença acumulada e a velocidade, pela
--   distância desde a entrada, com o cursor de cada carro. Só quando a rota traz os dados (o
--   backend do 0.5.0 não traz: a janela fica como antes). Quando a janela é pequena, sai primeiro
--   a velocidade, depois a diferença e por último o pedal; o replay fica com pelo menos 150 px;
-- * nos boxes ou com o jogo pausado, a grade da sessão (as últimas 8 voltas válidas), embaixo.
local REPLAY_PAUSA_NO_FIM_S = 1.2       -- o fim de cada curva fica parado um pouco
local REPLAY_MINIMO_S = 6               -- na reta, sem o `restaS` da mensagem (um backend antigo)
local REPLAY_AUMENTO_NOS_BOXES = 1.6    -- nos boxes, a janela cresce isto
local REPLAY_TOPO = 24
local REPLAY_MARGEM = 18
-- Pedido 43: as alturas dos visuais e o mínimo do replay (frontend/src/aoVivo/replay.ts, dividirAArea).
local ALTURA_DO_PEDAL, ALTURA_DA_DIFERENCA, ALTURA_DA_VELOCIDADE = 30, 60, 74
local REPLAY_MINIMO = 150
local COLUNA_DOS_NOMES = 34
local GRADE_VOLTAS = 8                 -- nos boxes, as últimas 8 voltas válidas
local GRADE_LEITURA_S = 5
local GRADE_PERDA_FORTE_S = 1.0
local COR_DO_TRECHO = rgbm(1, 1, 1, 0.16)

local rp = {
  dados = {},            -- [id da mensagem] = { curvas }
  ordem = {},            -- os ids guardados, do mais antigo ao mais novo (no máximo 6)
  atual = nil, inicio = 0, ateQuando = 0,
  ultimaAnalise = nil,
  noBox = false, inicioNoBox = 0,
  janela = nil, tamanhoOriginal = nil, avisouTamanho = false,
  ultimoQuadro = -100,
  grade = nil, gradeLidaEm = -100, gradeSemRota = false,   -- pedido 43: a grade da sessão
}

local function guardarReplay(id, curvas)
  rp.dados[id] = curvas
  rp.ordem[#rp.ordem + 1] = id
  while #rp.ordem > 6 do
    local velho = table.remove(rp.ordem, 1)
    if velho ~= rp.ultimaAnalise then rp.dados[velho] = nil end
  end
end

-- Chamada quando uma mensagem com replay vira o cartão atual (`avancar`).
comecarReplay = function(m, t)
  if type(m.replay) ~= 'table' or type(m.replay.url) ~= 'string' then return end
  local id = m.id
  rp.atual, rp.inicio = id, t
  rp.ateQuando = t + (tonumber(m.restaS) or REPLAY_MINIMO_S)
  if m.origem == 'analise' then rp.ultimaAnalise = id end
  if rp.dados[id] then return end
  pedirAoBackend(BACKEND .. m.replay.url, function(err, r)
    if err or not r or r.status ~= 200 then
      log('replay: o backend não entregou o replay da mensagem ' .. tostring(id) .. ' (' .. tostring(err or (r and r.status)) .. ')')
      return
    end
    local ok, dados = pcall(JSON.parse, r.body)
    if ok and type(dados) == 'table' and type(dados.curvas) == 'table' and #dados.curvas > 0 then
      guardarReplay(id, dados.curvas)
    end
  end)
end

-- A câmera da curva, a mesma da tela Ao vivo (frontend/src/aoVivo/replay.ts): a entrada para
-- cima, na orientação do mapa do app (base(x, z) = (z, −x)), encaixada na área.
local function cameraDaCurva(c, x0, y0, W, H)
  local ref = c.linhas.referencia
  local a, b = ref[1], ref[math.min(#ref, 11)]
  local du, dv = b[2] - a[2], -(b[1] - a[1])
  local ang = -math.pi / 2 - math.atan2(dv, du)
  local cs, sn = math.cos(ang), math.sin(ang)
  local function girar(x, z)
    local u, v = z, -x
    return u * cs - v * sn, u * sn + v * cs
  end
  local gx0, gx1, gy0, gy1 = math.huge, -math.huge, math.huge, -math.huge
  for _, linha in ipairs({ c.linhas.voce, ref }) do
    for _, p in ipairs(linha) do
      local gx, gy = girar(p[1], p[2])
      gx0, gx1 = math.min(gx0, gx), math.max(gx1, gx)
      gy0, gy1 = math.min(gy0, gy), math.max(gy1, gy)
    end
  end
  local k = math.min((W - 2 * REPLAY_MARGEM) / math.max(gx1 - gx0, 1),
                     (H - 2 * REPLAY_MARGEM - REPLAY_TOPO) / math.max(gy1 - gy0, 1))
  local ax, ay = x0 + W / 2, y0 + REPLAY_TOPO + (H - REPLAY_TOPO) / 2
  local rcx, rcy = (gx0 + gx1) / 2, (gy0 + gy1) / 2
  local cam = { k = k, ax = ax, ay = ay, rcx = rcx, rcy = rcy, cs = cs, sn = sn }
  function cam.tela(x, z)
    local gx, gy = girar(x, z)
    return ax + k * (gx - rcx), ay + k * (gy - rcy)
  end
  -- O inverso, para a imagem da pista: da tela ao mundo e dele às coordenadas do mapa (x, −z).
  function cam.mapa(sx, sy)
    local gx, gy = (sx - ax) / k + rcx, (sy - ay) / k + rcy
    local u, v = gx * cs + gy * sn, -gx * sn + gy * cs
    local x, z = -v, u
    return x, -z
  end
  return cam
end

-- Onde o carro está no tempo `t` (cada um no seu tempo; o fim da linha depois dela).
local function posicaoNoTempo(linha, t)
  local n = #linha
  if n == 0 then return 0, 0 end
  if t <= linha[1][3] then return linha[1][1], linha[1][2] end
  if t >= linha[n][3] then return linha[n][1], linha[n][2] end
  local a, b = 1, n
  while b - a > 1 do
    local m = math.floor((a + b) / 2)
    if linha[m][3] <= t then a = m else b = m end
  end
  local p, q = linha[a], linha[b]
  local u = q[3] > p[3] and (t - p[3]) / (q[3] - p[3]) or 0
  return p[1] + (q[1] - p[1]) * u, p[2] + (q[2] - p[2]) * u
end

local function larguraDoRotulo(texto)
  local largura = #texto * 6
  if ui.measureDWriteText ~= nil then
    local ok, medida = pcall(ui.measureDWriteText, texto, 11)
    if ok and medida then largura = medida.x end
  end
  return largura + 6
end

-- Os rótulos do replay não cobrem um ao outro, nem os carros e as marcas, nem saem da janela:
-- cada um tenta, em ordem, os lugares em volta do seu ponto (o preferido primeiro), encostado e
-- depois cada vez mais longe (com um fio até o ponto); se nenhum estiver livre, fica no
-- preferido, empurrado para dentro da janela.
local LUGARES_DO_ROTULO = { 'direita', 'esquerda', 'abaixo', 'acima', 'direitaAcima', 'esquerdaAbaixo',
                            'direitaAbaixo', 'esquerdaAcima' }
local ALTURA_DO_ROTULO = 15
local AFASTAMENTOS_DO_ROTULO = { 0, 14, 28, 44, 60 }
local DIRECAO_DO_ROTULO = { direita = { 1, 0 }, esquerda = { -1, 0 }, abaixo = { 0, 1 }, acima = { 0, -1 },
                            direitaAcima = { 0.7, -0.7 }, esquerdaAbaixo = { -0.7, 0.7 },
                            direitaAbaixo = { 0.7, 0.7 }, esquerdaAcima = { -0.7, -0.7 } }

local function novoQuadroDeRotulos(x0, y0, W, H)
  return { area = { x0 + 2, y0 + REPLAY_TOPO + 2, x0 + W - 2, y0 + H - 2 }, ocupados = {} }
end

local function ocupar(q, x, y, raio)
  q.ocupados[#q.ocupados + 1] = { x - raio, y - raio, x + raio, y + raio }
end

local function cantoDoRotulo(lugar, x, y, w, h)
  if lugar == 'direita' then return x + 8, y - h / 2 end
  if lugar == 'esquerda' then return x - 8 - w, y - h / 2 end
  if lugar == 'abaixo' then return x - w / 2, y + 8 end
  if lugar == 'acima' then return x - w / 2, y - 8 - h end
  if lugar == 'direitaAcima' then return x + 6, y - 6 - h end
  if lugar == 'esquerdaAbaixo' then return x - 6 - w, y + 6 end
  if lugar == 'direitaAbaixo' then return x + 6, y + 6 end
  return x - 6 - w, y - 6 - h
end

local function rotulo(q, texto, x, y, cor, preferido)
  local w, h = larguraDoRotulo(texto), ALTURA_DO_ROTULO
  local a = q.area
  local function livre(bx, by)
    if bx < a[1] or by < a[2] or bx + w > a[3] or by + h > a[4] then return false end
    for _, r in ipairs(q.ocupados) do
      if bx < r[3] and r[1] < bx + w and by < r[4] and r[2] < by + h then return false end
    end
    return true
  end
  local bx, by, longe
  for _, d in ipairs(AFASTAMENTOS_DO_ROTULO) do
    for i = 0, #LUGARES_DO_ROTULO do
      local lugar = i == 0 and preferido or LUGARES_DO_ROTULO[i]
      local dir = DIRECAO_DO_ROTULO[lugar]
      local cx, cy = cantoDoRotulo(lugar, x + dir[1] * d, y + dir[2] * d, w, h)
      if livre(cx, cy) then bx, by, longe = cx, cy, d > 0 break end
    end
    if bx then break end
  end
  if not bx then
    bx, by = cantoDoRotulo(preferido, x, y, w, h)
    bx = math.min(math.max(bx, a[1]), a[3] - w)
    by = math.min(math.max(by, a[2]), a[4] - h)
  end
  q.ocupados[#q.ocupados + 1] = { bx, by, bx + w, by + h }
  if longe then
    ui.drawLine(vec2(x, y), vec2(math.min(math.max(x, bx), bx + w), math.min(math.max(y, by), by + h)), cor, 1)
  end
  ui.drawRectFilled(vec2(bx, by), vec2(bx + w, by + h), CORES.fantasmaMiolo, 3)
  ui.dwriteDrawText(texto, 11, vec2(bx + 3, by + 1), cor)
end

-- Pedido 43: os índices da linha dentro do trecho da fala, ou nada.
local function indicesDoTrecho(c)
  if type(c.voz) ~= 'table' or not tonumber(c.passoM) then return nil end
  local n = #c.linhas.referencia
  local a = math.max(1, math.floor((tonumber(c.voz.inicioM) or 0) / c.passoM + 0.5) + 1)
  local b = math.min(n, math.floor((tonumber(c.voz.fimM) or 0) / c.passoM + 0.5) + 1)
  if b > a then return a, b end
  return nil
end

-- O alto: "C12, esquerda · volta 2 · perde 0,64 s no trecho da fala" (o tempo da voz), ou a perda na curva.
local function textoDoAlto(c)
  local volta = c.volta and (' · volta ' .. tostring(c.volta)) or ''
  local inicio = tostring(c.curva) .. ', ' .. tostring(c.lado) .. volta
  if type(c.voz) == 'table' then
    local p = tonumber(c.voz.perdaS)
    if not p then return inicio end
    return inicio .. ' · ' .. (p >= 0 and 'perde ' or 'ganha ') .. decimal(math.abs(p), 2) .. ' s no trecho da fala'
  end
  local perda = tonumber(c.perdaS) or 0
  return inicio .. ' · ' .. (perda >= 0 and 'perde ' or 'ganha ') .. decimal(math.abs(perda), 2) .. ' s nesta curva'
end

local function desenharACurva(c, t, x0, y0, W, H)
  local cam = cameraDaCurva(c, x0, y0, W, H)
  ui.drawRectFilled(vec2(x0, y0), vec2(x0 + W, y0 + H), CORES.fundoDoMapa, 6)
  local img = mini.imagem
  if img then
    local function uv(sx, sy)
      local mx, my = cam.mapa(sx, sy)
      return vec2((mx - img.x0) * img.pxPorMetro / img.largura, (my - img.y0) * img.pxPorMetro / img.altura)
    end
    ui.drawImageQuad(img.caminho, vec2(x0, y0), vec2(x0 + W, y0), vec2(x0 + W, y0 + H), vec2(x0, y0 + H), CORES.branco,
      uv(x0, y0), uv(x0 + W, y0), uv(x0 + W, y0 + H), uv(x0, y0 + H))
  end
  local function linha(pontos, cor)
    ui.pathClear()
    for _, p in ipairs(pontos) do
      local sx, sy = cam.tela(p[1], p[2])
      ui.pathLineTo(vec2(sx, sy))
    end
    ui.pathStroke(cor, false, 2.5)
  end
  -- Pedido 43: o trecho da fala, uma faixa clara sobre a pista (o microssetor que a voz mediu).
  local ta, tb = indicesDoTrecho(c)
  if ta then
    ui.pathClear()
    for i = ta, tb do
      local p = c.linhas.referencia[i]
      local sx, sy = cam.tela(p[1], p[2])
      ui.pathLineTo(vec2(sx, sy))
    end
    ui.pathStroke(COR_DO_TRECHO, false, 16)
  end
  linha(c.linhas.referencia, CORES.fantasma)
  linha(c.linhas.voce, CORES.vermelho)
  -- Os pontos que os rótulos não cobrem: os dois carros, as freadas, as mínimas e o traçado.
  local q = novoQuadroDeRotulos(x0, y0, W, H)
  local rx, rz = posicaoNoTempo(c.linhas.referencia, t)
  local vx, vz = posicaoNoTempo(c.linhas.voce, t)
  local rsx, rsy = cam.tela(rx, rz)
  local vsx, vsy = cam.tela(vx, vz)
  ocupar(q, rsx, rsy, 9)
  ocupar(q, vsx, vsy, 9)
  -- Pedido 43: na frase do coach, a rota pode vir sem as mínimas e sem o traçado.
  local mv = type(c.minimas) == 'table' and c.minimas.voce or nil
  local mr = type(c.minimas) == 'table' and c.minimas.referencia or nil
  local mvx, mvy, mrx, mry
  if mv and mr then
    mvx, mvy = cam.tela(mv.x, mv.z)
    mrx, mry = cam.tela(mr.x, mr.z)
    ocupar(q, mvx, mvy, 5)
    ocupar(q, mrx, mry, 5)
  end
  local tem_tracado = type(c.tracado) == 'table'
  local tvx, tvy, trx, try
  if tem_tracado then
    local tv, tr = c.tracado.voce, c.tracado.referencia
    tvx, tvy = cam.tela(tv[1], tv[2])
    trx, try = cam.tela(tr[1], tr[2])
    ocupar(q, tvx, tvy, 5)
    ocupar(q, trx, try, 5)
  end
  if ta then
    local meio = c.linhas.referencia[math.floor((ta + tb) / 2)]
    local sx, sy = cam.tela(meio[1], meio[2])
    rotulo(q, 'trecho da fala', sx, sy, CORES.texto, 'esquerda')
  end
  -- As freadas: um traço em cada linha e a distância entre elas.
  local contra = c.referencia == 'minha_melhor' and 'da sua melhor' or 'da IA'
  local function traco(m, cor)
    if type(m) ~= 'table' then return nil end
    local sx, sy = cam.tela(tonumber(m.x) or 0, tonumber(m.z) or 0)
    ui.drawLine(vec2(sx - 7, sy), vec2(sx + 7, sy), cor, 3)
    ocupar(q, sx, sy, 7)
    return sx, sy
  end
  local freadas = type(c.freadas) == 'table' and c.freadas or {}
  local fx, fy = traco(freadas.voce, CORES.vermelho)
  traco(freadas.referencia, CORES.fantasma)
  local d = tonumber(freadas.distanciaM)
  if fx and d then
    local m = math.floor(math.abs(d) + 0.5)
    local texto = m < 1 and ('você freia no mesmo ponto ' .. contra:gsub('^da ', 'que a '))
      or ('você freia ' .. m .. ' m ' .. (d < 0 and 'antes ' or 'depois ') .. contra)
    rotulo(q, texto, fx, fy, CORES.vermelho, 'direita')
  end
  -- O traçado: uma seta entre as duas linhas, no ponto da mínima da referência (só na análise).
  local amarelo = CORES_DO_PEDAL[0]
  if tem_tracado then
    if math.sqrt((tvx - trx) ^ 2 + (tvy - try) ^ 2) > 2 then
      ui.drawLine(vec2(trx, try), vec2(tvx, tvy), amarelo, 1.5)
      local a = math.atan2(tvy - try, tvx - trx)
      ui.drawTriangleFilled(vec2(tvx, tvy), vec2(tvx - 7 * math.cos(a - 0.5), tvy - 7 * math.sin(a - 0.5)),
        vec2(tvx - 7 * math.cos(a + 0.5), tvy - 7 * math.sin(a + 0.5)), amarelo)
    end
    rotulo(q, 'você passa ' .. decimal(tonumber(c.tracado.distanciaM) or 0, 1) .. ' m mais à ' .. tostring(c.tracado.lado),
      (tvx + trx) / 2, (tvy + try) / 2, amarelo, 'abaixo')
  end
  -- As mínimas, no ponto de cada uma.
  if mv and mr then
    ui.drawCircleFilled(vec2(mvx, mvy), 3.5, CORES.vermelho, 12)
    ui.drawCircleFilled(vec2(mrx, mry), 3.5, CORES.fantasma, 12)
    rotulo(q, 'mínima ' .. math.floor(mv.kmh + 0.5) .. ' km/h', mvx, mvy, CORES.vermelho, 'esquerda')
    rotulo(q, 'mínima ' .. math.floor(mr.kmh + 0.5) .. ' km/h', mrx, mry, CORES.fantasma, 'direita')
  end
  -- Os dois carros, cada um no seu tempo.
  desenharMarca(vec2(rsx, rsy), 6.5, CORES.fantasmaMiolo, CORES.fantasma, 2.5)
  desenharMarca(vec2(vsx, vsy), 6.5, CORES.voce, CORES.vermelho, 2.5)
  rotulo(q, tostring(c.rotuloDaReferencia or 'IA (referência)'), rsx, rsy, CORES.fantasma, 'direitaAcima')
  rotulo(q, 'você', vsx, vsy, CORES.texto, 'esquerdaAbaixo')
  -- O alto: a curva, a volta e o tempo perdido (na frase do coach, o da voz).
  ui.drawRectFilled(vec2(x0, y0), vec2(x0 + W, y0 + REPLAY_TOPO), CORES.faixaDoTexto, 6)
  ui.dwriteDrawText(textoDoAlto(c), 12, vec2(x0 + 10, y0 + 5), CORES.texto)
end

-- ── os visuais (pedido 43, Parte C) ────────────────────────────────────
-- As mesmas contas da tela Ao vivo (frontend/src/aoVivo/replay.ts e ReplayDaCurva.tsx).

local function temVisuais(c)
  local v = c.velocidades
  return tonumber(c.passoM) ~= nil and type(v) == 'table' and type(v.voce) == 'table' and type(v.referencia) == 'table'
    and #v.voce == #c.linhas.voce and #v.referencia == #c.linhas.referencia
end

-- Onde o carro está no tempo `t`, em metros desde a entrada (o cursor dos visuais).
local function distanciaNoTempo(linha, t, passo)
  local n = #linha
  if n == 0 or t <= linha[1][3] then return 0 end
  if t >= linha[n][3] then return (n - 1) * passo end
  local a, b = 1, n
  while b - a > 1 do
    local m = math.floor((a + b) / 2)
    if linha[m][3] <= t then a = m else b = m end
  end
  local u = linha[b][3] > linha[a][3] and (t - linha[a][3]) / (linha[b][3] - linha[a][3]) or 0
  return (a - 1 + u) * passo
end

-- A divisão da área: o replay fica com pelo menos REPLAY_MINIMO; na ordem de importância, entram
-- o pedal, a diferença e a velocidade, enquanto couberem. De cima para baixo: o replay, o pedal,
-- a diferença e a velocidade.
local function dividirAJanela(x0, y0, W, H, comVisuais)
  local d = { replay = { x0, y0, W, H } }
  if not comVisuais then return d end
  local resto = H
  local alturas = { pedal = ALTURA_DO_PEDAL, diferenca = ALTURA_DA_DIFERENCA, velocidade = ALTURA_DA_VELOCIDADE }
  local entram = {}
  for _, nome in ipairs({ 'pedal', 'diferenca', 'velocidade' }) do
    if resto - alturas[nome] < REPLAY_MINIMO then break end
    resto = resto - alturas[nome]
    entram[nome] = true
  end
  d.replay = { x0, y0, W, resto }
  local y = y0 + resto
  for _, nome in ipairs({ 'pedal', 'diferenca', 'velocidade' }) do
    if entram[nome] then
      d[nome] = { x0, y, W, alturas[nome] }
      y = y + alturas[nome]
    end
  end
  return d
end

-- O fundo de um visual, a faixa do trecho da fala, o título; devolve a escala de x (metros -> tela).
local function moldura(c, a, titulo)
  local x, y, w, h = a[1], a[2], a[3], a[4]
  ui.drawRectFilled(vec2(x, y), vec2(x + w, y + h - 2), CORES.fundoDoMapa, 0)
  local x0 = x + COLUNA_DOS_NOMES
  local largura = w - COLUNA_DOS_NOMES - 8
  local total = math.max((#c.linhas.voce - 1) * c.passoM, 1)
  local function emX(dm) return x0 + largura * dm / total end
  if type(c.voz) == 'table' then
    ui.drawRectFilled(vec2(emX(tonumber(c.voz.inicioM) or 0), y), vec2(emX(tonumber(c.voz.fimM) or 0), y + h - 2), COR_DO_TRECHO, 0)
  end
  if titulo ~= '' then ui.dwriteDrawText(titulo, 10, vec2(x0 + 2, y + 2), CORES.fraco) end
  return emX
end

local function cursores(c, t, a, emX)
  for _, par in ipairs({ { c.linhas.referencia, CORES.fantasma }, { c.linhas.voce, CORES.vermelho } }) do
    local xx = emX(distanciaNoTempo(par[1], t, c.passoM))
    ui.drawLine(vec2(xx, a[2]), vec2(xx, a[2] + a[4] - 2), par[2], 1.5)
  end
end

-- C.3: as duas faixas do pedal, pelas cores do traçado pintado pelo pedal (o mapa aproximado).
local function desenharOPedal(c, t, a)
  local emX = moldura(c, a, '')
  local function faixa(linha, y, nome, cor)
    local n = #linha
    local i = 1
    while i <= n do
      local pedal = linha[i][4] or 0
      local j = i
      while j < n and (linha[j + 1][4] or 0) == pedal do j = j + 1 end
      local de = math.max(0, (i - 1.5) * c.passoM)
      local ate = math.min((n - 1) * c.passoM, (j - 0.5) * c.passoM)
      ui.drawRectFilled(vec2(emX(de), y), vec2(math.max(emX(ate), emX(de) + 1), y + 10), CORES_DO_PEDAL[pedal] or CORES_DO_PEDAL[0], 0)
      i = j + 1
    end
    ui.dwriteDrawText(nome, 10, vec2(a[1] + 4, y - 1), cor)
  end
  faixa(c.linhas.voce, a[2] + 3, 'você', CORES.vermelho)
  faixa(c.linhas.referencia, a[2] + 15, c.referencia == 'minha_melhor' and 'sua' or 'IA', CORES.fantasma)
  cursores(c, t, a, emX)
end

-- C.2: a diferença acumulada (o seu tempo menos o da referência, desde a mesma entrada), com
-- as separações na freada, na mínima e na saída.
local function desenharADiferenca(c, t, a)
  local emX = moldura(c, a, 'diferença acumulada (s): sobe quando você perde')
  local v, r = c.linhas.voce, c.linhas.referencia
  local n = #v
  local dif, maior = {}, 0.05
  for i = 1, n do
    dif[i] = v[i][3] - (r[i] or r[#r])[3]
    maior = math.max(maior, math.abs(dif[i]))
  end
  local topo = a[2] + 16
  local meio = topo + (a[4] - 20) / 2
  local function emY(x) return meio - ((a[4] - 22) / 2) * (x / maior) end
  ui.drawLine(vec2(emX(0), meio), vec2(emX((n - 1) * c.passoM), meio), CORES.borda, 1)
  local perda, ganho = comAlfa(CORES.perda, 0.35), comAlfa(CORES.ganho, 0.35)
  for i = 1, n - 1 do
    local xa, xb = emX((i - 1) * c.passoM), emX(i * c.passoM)
    local ya, yb = emY(dif[i]), emY(dif[i + 1])
    if dif[i] >= 0 and dif[i + 1] >= 0 then
      ui.drawQuadFilled(vec2(xa, meio), vec2(xa, ya), vec2(xb, yb), vec2(xb, meio), perda)
    elseif dif[i] <= 0 and dif[i + 1] <= 0 then
      ui.drawQuadFilled(vec2(xa, meio), vec2(xb, meio), vec2(xb, yb), vec2(xa, ya), ganho)
    end
  end
  ui.pathClear()
  for i = 1, n do ui.pathLineTo(vec2(emX((i - 1) * c.passoM), emY(dif[i]))) end
  ui.pathStroke(CORES.vermelho, false, 1.5)
  local s = type(c.secoes) == 'table' and c.secoes or {}
  for _, par in ipairs({ { s.freadaM, 'freada' }, { s.minimaM, 'mínima' }, { s.saidaM, 'saída' } }) do
    local dm = tonumber(par[1])
    if dm then
      local xx = emX(dm)
      for yy = topo, a[2] + a[4] - 4, 6 do
        ui.drawLine(vec2(xx, yy), vec2(xx, math.min(yy + 3, a[2] + a[4] - 2)), CORES.contorno, 1)
      end
      ui.dwriteDrawText(par[2], 10, vec2(xx - larguraDoRotulo(par[2]) / 2 + 3, a[2] + a[4] - 14), CORES.apoio)
    end
  end
  cursores(c, t, a, emX)
end

-- C.1: as duas velocidades pela distância, com as freadas e as mínimas marcadas.
local function desenharAVelocidade(c, t, a)
  local emX = moldura(c, a, 'velocidade (km/h) pela distância (m)')
  local vel = c.velocidades
  local v0, v1 = math.huge, -math.huge
  for _, serie in ipairs({ vel.voce, vel.referencia }) do
    for _, x in ipairs(serie) do v0, v1 = math.min(v0, x), math.max(v1, x) end
  end
  local function emY(x) return a[2] + a[4] - 6 - (a[4] - 24) * (x - v0) / math.max(v1 - v0, 1) end
  for _, par in ipairs({ { vel.referencia, CORES.fantasma }, { vel.voce, CORES.vermelho } }) do
    ui.pathClear()
    for i, x in ipairs(par[1]) do ui.pathLineTo(vec2(emX((i - 1) * c.passoM), emY(x))) end
    ui.pathStroke(par[2], false, 1.5)
  end
  local function naSerie(serie, dm)
    return serie[math.min(#serie, math.max(1, math.floor(dm / c.passoM + 0.5) + 1))]
  end
  local freadas = type(c.freadas) == 'table' and c.freadas or {}
  for _, par in ipairs({ { freadas.voce, vel.voce, CORES.vermelho }, { freadas.referencia, vel.referencia, CORES.fantasma } }) do
    local m = par[1]
    if type(m) == 'table' and tonumber(m.dM) then
      local xx, yy = emX(m.dM), emY(naSerie(par[2], m.dM))
      ui.drawLine(vec2(xx, yy - 6), vec2(xx, yy + 6), par[3], 3)
    end
  end
  if type(c.minimas) == 'table' then
    for _, par in ipairs({ { c.minimas.voce, vel.voce, CORES.vermelho }, { c.minimas.referencia, vel.referencia, CORES.fantasma } }) do
      local m = par[1]
      if type(m) == 'table' and tonumber(m.dM) then
        ui.drawCircleFilled(vec2(emX(m.dM), emY(naSerie(par[2], m.dM))), 3.5, par[3], 12)
      end
    end
  end
  cursores(c, t, a, emX)
end

-- ── a grade da sessão (pedido 43, C.4), nos boxes ───────────────────────

local function lerAGrade(t)
  if rp.gradeSemRota or t - rp.gradeLidaEm < GRADE_LEITURA_S then return end
  rp.gradeLidaEm = t
  pedirAoBackend(BACKEND .. '/api/radio/grade', function(err, r)
    if err or not r then return end
    if r.status == 404 then
      -- o backend do 0.5.0 não tem a rota: sem a grade, e sem pedir de novo
      rp.gradeSemRota = true
      log('replay: o backend não tem a grade da sessão (/api/radio/grade); a janela fica sem ela')
      return
    end
    if r.status ~= 200 then return end
    local ok, dados = pcall(JSON.parse, r.body)
    if ok and type(dados) == 'table' and type(dados.voltas) == 'table' and type(dados.curvas) == 'table' then
      rp.grade = dados
    end
  end)
end

-- A altura que a grade ocupa (0 sem a grade): o título, o cabeçalho, as voltas e as de fora.
local function alturaDaGrade()
  local g = rp.grade
  if not g or #g.voltas == 0 then return 0 end
  local fora = type(g.fora) == 'table' and math.min(#g.fora, 2) or 0
  return 18 + 15 + 15 * math.min(#g.voltas, GRADE_VOLTAS) + 13 * fora + 6
end

local function desenharAGrade(x0, y0, W, H)
  local g = rp.grade
  ui.drawRectFilled(vec2(x0, y0), vec2(x0 + W, y0 + H), CORES.fundoDoMapa, 6)
  ui.dwriteDrawText('Grade da sessão: a perda em cada curva (laranja perde, azul ganha; contorno: citada)', 10,
    vec2(x0 + 6, y0 + 3), CORES.apoio)
  local nc = #g.curvas
  local cw = (W - 40 - 6) / math.max(nc, 1)
  local fonte = math.min(10, cw / 3.6)
  local y = y0 + 18
  for k, nome in ipairs(g.curvas) do
    ui.dwriteDrawText(tostring(nome), fonte, vec2(x0 + 40 + (k - 1) * cw + 2, y), CORES.fraco)
  end
  y = y + 15
  local citadas = {}
  for _, c in ipairs(type(g.citadas) == 'table' and g.citadas or {}) do
    citadas[tostring(c.volta) .. ':' .. tostring(c.curva)] = true
  end
  local primeira = math.max(1, #g.voltas - GRADE_VOLTAS + 1)
  for i = primeira, #g.voltas do
    local v = g.voltas[i]
    ui.dwriteDrawText('volta ' .. tostring(v.volta), fonte, vec2(x0 + 4, y + 1), CORES.texto)
    for k = 1, nc do
      local p = tonumber(v.perdas[k])
      local a = vec2(x0 + 40 + (k - 1) * cw + 1, y)
      local b = vec2(x0 + 40 + k * cw - 1, y + 13)
      if p then
        local forca = 0.15 + 0.75 * math.min(1, math.abs(p) / GRADE_PERDA_FORTE_S)
        ui.drawRectFilled(a, b, comAlfa(p >= 0 and CORES.perda or CORES.ganho, forca), 2)
        local texto = (p < 0 and '−' or '') .. decimal(math.abs(p), 2) .. ' s'
        ui.dwriteDrawText(texto, fonte, vec2(a.x + 2, y + 1), math.abs(p) > 0.6 and CORES.fundo or CORES.texto)
      end
      if citadas[tostring(v.volta) .. ':' .. tostring(g.curvas[k])] then
        ui.drawRect(a, b, CORES.vermelho, 2, nil, 2)
      end
    end
    y = y + 15
  end
  if type(g.fora) == 'table' then
    for i = 1, math.min(#g.fora, 2) do
      local f = g.fora[#g.fora - i + 1]
      ui.dwriteDrawText('fora: volta ' .. tostring(f.volta) .. ', ' .. tostring(f.motivo), 10, vec2(x0 + 6, y), CORES.fraco)
      y = y + 13
    end
  end
end

-- Nos boxes, a janela cresce (e volta ao tamanho de antes na saída). A janela é achada pelo título.
local function aumentarNosBoxes(aumentar)
  if ac.accessAppWindow == nil or ac.getAppWindows == nil then return end
  if not rp.janela then
    local ok, janelas = pcall(ac.getAppWindows)
    if ok and type(janelas) == 'table' then
      for _, j in ipairs(janelas) do
        if type(j.title) == 'string' and j.title:find('Replay da curva', 1, true) then
          local okA, acesso = pcall(ac.accessAppWindow, j.name)
          if okA and acesso then rp.janela = acesso end
        end
      end
    end
    if not rp.janela then
      if not rp.avisouTamanho then
        log('replay: não achei a janela para aumentar nos boxes; o replay fica no tamanho dela')
        rp.avisouTamanho = true
      end
      return
    end
  end
  pcall(function()
    if aumentar then
      rp.tamanhoOriginal = rp.janela:size()
      rp.janela:resize(rp.tamanhoOriginal * REPLAY_AUMENTO_NOS_BOXES)
    elseif rp.tamanhoOriginal then
      rp.janela:resize(rp.tamanhoOriginal)
      rp.tamanhoOriginal = nil
    end
  end)
end

local desenharOReplay

-- Chamada a cada quadro pela janela do replay (manifest.ini, FUNCTION_MAIN).
function replay(dt)
  local tamanho = ui.windowSize()
  naJanelaInteira(tamanho.x, tamanho.y, desenharOReplay, dt)
end

desenharOReplay = function(dt)
  local t = relogio()
  rp.ultimoQuadro = t
  local tamanho = ui.windowSize()
  if CALADO or not APROXIMADO then
    local falta = CALADO and FALTA or (#FALTA_NO_MINIMAPA > 0 and FALTA_NO_MINIMAPA or FALTA_NO_APROXIMADO)
    desenharAviso('Replay da curva: esta versão do CSP não tem ' .. table.concat(falta, ', ') .. '.', tamanho)
    return
  end
  local W, H = tamanho.x, tamanho.y
  registrarAsMedidas('replay', W, H)
  local okC, carro = pcall(ac.getCar, 0)
  local okS, sim = pcall(ac.getSim)
  local noBox = (okC and carro and (carro.isInPitlane or carro.isInPit)) or (okS and sim and sim.isPaused) or false
  if noBox ~= rp.noBox then
    rp.noBox = noBox
    rp.inicioNoBox = t
    aumentarNosBoxes(noBox)
  end
  local curvas, inicio, repetir = nil, 0, false
  if noBox and rp.ultimaAnalise and rp.dados[rp.ultimaAnalise] then
    curvas, inicio, repetir = rp.dados[rp.ultimaAnalise], rp.inicioNoBox, true
  elseif rp.atual and t < rp.ateQuando and rp.dados[rp.atual] then
    curvas, inicio = rp.dados[rp.atual], rp.inicio
  end
  if not curvas then return end
  -- Cada curva citada, uma depois da outra (e de novo, nos boxes).
  local total = 0
  for _, c in ipairs(curvas) do total = total + (tonumber(c.duracaoS) or 0) + REPLAY_PAUSA_NO_FIM_S end
  local tc = t - inicio
  if repetir and total > 0 then tc = tc % total end
  local i = 1
  while i < #curvas and tc > (tonumber(curvas[i].duracaoS) or 0) + REPLAY_PAUSA_NO_FIM_S do
    tc = tc - (tonumber(curvas[i].duracaoS) or 0) - REPLAY_PAUSA_NO_FIM_S
    i = i + 1
  end
  local c = curvas[i]
  local x0, y0, x1, y1 = areaVisivel(W, H)
  local tempo = math.min(tc, tonumber(c.duracaoS) or 0)
  -- Pedido 43: nos boxes, a grade da sessão embaixo (se o replay ainda ficar com o mínimo).
  local altGrade = 0
  if noBox then
    lerAGrade(t)
    altGrade = alturaDaGrade()
    if (y1 - y0) - altGrade < REPLAY_MINIMO then altGrade = 0 end
  end
  local d = dividirAJanela(x0, y0, x1 - x0, y1 - y0 - altGrade, temVisuais(c))
  local r = d.replay
  desenharACurva(c, tempo, r[1], r[2], r[3], r[4])
  if d.pedal then desenharOPedal(c, tempo, d.pedal) end
  if d.diferenca then desenharADiferenca(c, tempo, d.diferenca) end
  if d.velocidade then desenharAVelocidade(c, tempo, d.velocidade) end
  if altGrade > 0 then desenharAGrade(x0, y1 - altGrade, x1 - x0, altGrade) end
  if noBox then
    ui.dwriteDrawText('nos boxes: a última análise, em repetição', 11, vec2(r[1] + 10, r[2] + r[4] - 18), CORES.apoio)
  end
end

-- ── o custo no jogo: o FPS com os mapas ligados e desligados ────────────

local function novaContagem()
  return { soma = 0, n = 0, minimo = math.huge, maximo = 0, parado = 0,
           mini = { ligado = 0, desligado = 0 }, perto = { ligado = 0, desligado = 0 },
           rep = { ligado = 0, desligado = 0 } }
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
    for nome, ultimo in pairs({ mini = mini.ultimoQuadro, perto = perto.ultimoQuadro, rep = rp.ultimoQuadro }) do
      local c = fps[nome]
      if agora - ultimo < 0.5 then c.ligado = c.ligado + 1 else c.desligado = c.desligado + 1 end
    end
  end
  if fps.n + fps.parado >= FPS_REGISTRO_S / FPS_AMOSTRA_S then
    if fps.n > 0 then
      log('fps: média ' .. decimal(fps.soma / fps.n, 1) .. ' (mín ' .. decimal(fps.minimo, 0) .. ', máx '
        .. decimal(fps.maximo, 0) .. ') em ' .. fps.n .. ' s; minimapa ' .. situacao(fps.mini)
        .. '; mapa aproximado ' .. situacao(fps.perto) .. '; replay ' .. situacao(fps.rep))
    end
    fps = novaContagem()
  end
end

-- ── as janelas fora da tela ─────────────────────────────────────────────

-- Teste de 24/10: o jogo trocou do monitor de 2.560 para o de 1.920 px, e o mapa aproximado abriu
-- na posição salva (x = 2.188), fora da tela. Uma janela assim nunca é desenhada, e o mouse não a
-- alcança. A cada 2 s, uma janela ligada do app com menos de 40 px dentro da tela volta para
-- dentro, encostada na borda mais perto. Uma janela que passa um pouco da borda fica onde está.
local MINIMO_NA_TELA = 40

local function trazerAsJanelasParaATela()
  if ac.getAppWindows == nil or ac.accessAppWindow == nil then return end
  local okU, estadoUi = pcall(ac.getUI)
  if not okU or not estadoUi or not estadoUi.windowSize then return end
  local tw, th = estadoUi.windowSize.x, estadoUi.windowSize.y
  local ok, janelas = pcall(ac.getAppWindows)
  if not ok or type(janelas) ~= 'table' then return end
  for _, j in ipairs(janelas) do
    if j.visible and type(j.title) == 'string' and j.title:find('Sistema de Telemetria e Otimização de Trajetórias', 1, true)
        and j.position and j.size then
      local p, s = j.position, j.size
      local dentroX = math.min(p.x + s.x, tw) - math.max(p.x, 0)
      local dentroY = math.min(p.y + s.y, th) - math.max(p.y, 0)
      if dentroX < MINIMO_NA_TELA or dentroY < MINIMO_NA_TELA then
        local okA, acesso = pcall(ac.accessAppWindow, j.name)
        if okA and acesso then
          local nx = math.min(math.max(p.x, 0), math.max(tw - s.x, 0))
          local ny = math.min(math.max(p.y, 0), math.max(th - s.y, 0))
          local okM = pcall(function() acesso:move(vec2(nx, ny)) end)
          log(j.title:match('^[^·]+'):gsub('%s+$', '') .. ': estava fora da tela, em ' .. decimal(p.x, 0) .. ' x '
            .. decimal(p.y, 0) .. ' (tela ' .. decimal(tw, 0) .. ' x ' .. decimal(th, 0) .. '); '
            .. (okM and ('trazida para ' .. decimal(nx, 0) .. ' x ' .. decimal(ny, 0)) or 'não consegui mover'))
        end
      end
    end
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
  setInterval(function() pcall(trazerAsJanelasParaATela) end, 2)
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
