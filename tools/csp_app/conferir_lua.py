"""Confere o app Lua sem o jogo e sem instalar nada (pedido 31, Parte E.3).

Nao ha interpretador de Lua neste computador. O que da para conferir:

1. **O lexico:** o `pygments` (ja no .venv) le o arquivo com o lexer de Lua; um
   token de erro e um erro de lexico (string sem fechar, caractere estranho).
2. **Os blocos:** cada `function`, `if`, `for`, `while` e `do` solto fecha com um
   `end`, e cada `repeat` com um `until`, na ordem.
3. **A API usada:** cada chamada `web.`, `ui.`, `ac.`, `JSON.`, `os.`, `io.` (pedido 35), `render.` e
   `physics.` (pedido 52) e
   `setInterval` existe no `lib.lua` do SDK do CSP instalado (so leitura).

4. **A conferencia da API no proprio app:** nenhuma funcao da API conferida com
   `type(...) == 'function'`, porque no CSP varias sao nativas e dao 'cdata'.
5. **Os metodos (pedido 35):** cada `objeto:metodo(` existe como metodo de uma classe
   do `lib.lua` (`function _ui_MediaPlayer:setSource(`...), fora os da string do Lua.
6. **As variaveis locais da funcao principal (pedido 52, 22/11):** o Lua aceita no maximo 200 ativas ao mesmo
   tempo na funcao principal do arquivo; com 201, o CSP nao carrega o app ("main function has more than 200 local
   variables"), e nenhuma janela abre. Contam os `local` do nivel de cima e, no ponto mais cheio, os de dentro de um
   `if`, `do`, `while` ou `for` fora de qualquer funcao (o `for` com as tres variaveis escondidas do Lua). Acima de
   190, e um problema (a folga para o proximo pedido).

Nao e uma analise completa da gramatica: uma expressao malformada dentro de um
bloco bem fechado passaria. O teste de verdade e no jogo (Parte F).

Uso: python conferir_lua.py <arquivo.lua> [<lib.lua do SDK>]
"""
import re
import sys
from pathlib import Path

from pygments.lexers import LuaLexer
from pygments.token import Error, Keyword, Name

arquivo = Path(sys.argv[1])
sdk = Path(sys.argv[2]) if len(sys.argv) > 2 else None
codigo = arquivo.read_text(encoding="utf-8")
tokens = list(LuaLexer().get_tokens(codigo))

erros = [valor for tipo, valor in tokens if tipo in Error]
pilha = []
problemas = []
anterior = None
LOCAIS_MAXIMO, LOCAIS_FOLGA = 200, 190
locais_no_topo = 0              # os `local` do nivel de cima
locais_por_bloco = []           # os de cada bloco aberto fora de funcao (na ordem da `pilha`)
locais_maximo = 0               # o ponto mais cheio da funcao principal
contando_locais = None          # "inicio"/"nome"/"virgula": lendo os nomes de um `local` ou de um `for`
contando_no_for = False


def fora_de_funcao():
    return "function" not in pilha


for tipo, valor in tokens:
    # pedido 52 (22/11): os nomes de cada `local` (e de cada `for`) da funcao principal
    if contando_locais is not None and valor.strip():
        novo = 0
        if contando_locais == "inicio" and valor == "function" and not contando_no_for:
            novo, contando_locais = 1, None
        elif contando_locais in ("inicio", "virgula") and tipo in Name:
            novo, contando_locais = 1, "nome"
        elif contando_locais == "nome" and valor == ",":
            contando_locais = "virgula"
        else:
            contando_locais = None
        if novo:
            if contando_no_for:
                locais_por_bloco[-1] += novo
            elif not pilha:
                locais_no_topo += novo
            else:
                locais_por_bloco[-1] += novo
            locais_maximo = max(locais_maximo, locais_no_topo + sum(locais_por_bloco))
    if tipo in Keyword and valor == "local" and fora_de_funcao():
        contando_locais, contando_no_for = "inicio", False
    if tipo in Keyword or (tipo in Name and valor in ("function",)):
        if valor in ("function", "if", "repeat"):
            pilha.append(valor)
            locais_por_bloco.append(0)
        elif valor in ("for", "while"):
            pilha.append(valor)
            locais_por_bloco.append(3 if valor == "for" else 0)    # o `for`: as tres variaveis escondidas
            if valor == "for" and fora_de_funcao():
                contando_locais, contando_no_for = "inicio", True
        elif valor == "do":
            # `for ... do` e `while ... do` ja abriram o bloco; um `do` solto abre outro.
            if pilha and pilha[-1] in ("for", "while") and anterior != "do-usado":
                pilha[-1] = pilha[-1] + "-do"
            else:
                pilha.append("do")
                locais_por_bloco.append(0)
        elif valor == "end":
            if not pilha or pilha[-1] == "repeat":
                problemas.append("`end` sem bloco aberto")
            else:
                pilha.pop()
                locais_por_bloco.pop()
        elif valor == "until":
            if not pilha or pilha[-1] != "repeat":
                problemas.append("`until` sem `repeat`")
            else:
                pilha.pop()
                locais_por_bloco.pop()
if pilha:
    problemas.append(f"blocos sem fechar: {pilha}")
locais_maximo = max(locais_maximo, locais_no_topo)
if locais_maximo > LOCAIS_FOLGA:
    problemas.append(f"{locais_maximo} variaveis locais ativas na funcao principal: o Lua aceita {LOCAIS_MAXIMO}, "
                     f"e a folga e {LOCAIS_FOLGA}")

# No CSP, varias funcoes da API sao nativas (FFI): o `type()` delas e 'cdata', e nao
# 'function'. Conferir `type(ui.x) == 'function'` calou o app no teste no jogo de 18/10.
for linha, texto in enumerate(codigo.splitlines(), 1):
    if re.search(r"type\(\s*(?:web|ui|ac|JSON|os|io)\.[A-Za-z_]+\s*\)\s*[~=]=\s*'function'", texto) or \
            re.search(r"type\(\s*setInterval\s*\)\s*[~=]=\s*'function'", texto):
        problemas.append(f"linha {linha}: `type(...) == 'function'` numa funcao da API (no CSP pode ser 'cdata')")

# Pedido 52: tambem `render.` e `physics.` (a marca na pista) e o `vec3`.
chamadas = sorted(set(re.findall(r"\b((?:web|ui|ac|JSON|os|io|render|physics)\.[A-Za-z_]+|setInterval|rgbm|vec2|vec3)\b",
                                 codigo)))
faltam = []
if sdk and sdk.exists():
    lib = sdk.read_text(encoding="utf-8", errors="replace")
    for c in chamadas:
        if c in ("os.preciseClock",) and "function os.preciseClock" in lib:
            continue
        padrao = rf"function {re.escape(c)}\(|^{re.escape(c)} = |^---@class {re.escape(c)}\b"
        if not re.search(padrao, lib, re.MULTILINE):
            faltam.append(c)

# Os metodos chamados com `:` (o player, o canvas); os da string do Lua ficam de fora.
DA_STRING = {"byte", "find", "format", "gmatch", "gsub", "len", "lower", "match", "rep", "reverse", "sub", "upper"}
metodos = sorted(set(re.findall(r"[A-Za-z_\]\)]:([A-Za-z_]+)\(", codigo)) - DA_STRING)
metodos_faltam = []
if sdk and sdk.exists():
    for m in metodos:
        if not re.search(rf"^function _[A-Za-z_]+:{re.escape(m)}\(", lib, re.MULTILINE):
            metodos_faltam.append(m)

print(f"arquivo: {arquivo}")
print(f"tokens: {len(tokens)}; erros de lexico: {len(erros)} {erros[:5]}")
print(f"blocos: {'ok' if not problemas else problemas}")
print(f"variaveis locais na funcao principal: {locais_no_topo} no nivel de cima, {locais_maximo} no ponto mais cheio "
      f"(o Lua aceita {LOCAIS_MAXIMO}; folga ate {LOCAIS_FOLGA})")
print(f"API usada ({len(chamadas)}): {', '.join(chamadas)}")
print(f"metodos usados ({len(metodos)}): {', '.join(metodos)}")
if sdk:
    print(f"no SDK do CSP: {'todas existem' if not faltam else 'faltam ' + ', '.join(faltam)}")
    print(f"metodos no SDK do CSP: {'todos existem' if not metodos_faltam else 'faltam ' + ', '.join(metodos_faltam)}")
sys.exit(1 if erros or problemas or faltam or metodos_faltam else 0)
