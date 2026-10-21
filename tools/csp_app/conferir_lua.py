"""Confere o app Lua sem o jogo e sem instalar nada (pedido 31, Parte E.3).

Nao ha interpretador de Lua neste computador. O que da para conferir:

1. **O lexico:** o `pygments` (ja no .venv) le o arquivo com o lexer de Lua; um
   token de erro e um erro de lexico (string sem fechar, caractere estranho).
2. **Os blocos:** cada `function`, `if`, `for`, `while` e `do` solto fecha com um
   `end`, e cada `repeat` com um `until`, na ordem.
3. **A API usada:** cada chamada `web.`, `ui.`, `ac.`, `JSON.`, `os.`, `io.` (pedido 35) e
   `setInterval` existe no `lib.lua` do SDK do CSP instalado (so leitura).

4. **A conferencia da API no proprio app:** nenhuma funcao da API conferida com
   `type(...) == 'function'`, porque no CSP varias sao nativas e dao 'cdata'.
5. **Os metodos (pedido 35):** cada `objeto:metodo(` existe como metodo de uma classe
   do `lib.lua` (`function _ui_MediaPlayer:setSource(`...), fora os da string do Lua.

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
for tipo, valor in tokens:
    if tipo in Keyword or (tipo in Name and valor in ("function",)):
        if valor in ("function", "if", "repeat"):
            pilha.append(valor)
        elif valor in ("for", "while"):
            pilha.append(valor)
        elif valor == "do":
            # `for ... do` e `while ... do` ja abriram o bloco; um `do` solto abre outro.
            if pilha and pilha[-1] in ("for", "while") and anterior != "do-usado":
                pilha[-1] = pilha[-1] + "-do"
            else:
                pilha.append("do")
        elif valor == "end":
            if not pilha or pilha[-1] == "repeat":
                problemas.append("`end` sem bloco aberto")
            else:
                pilha.pop()
        elif valor == "until":
            if not pilha or pilha[-1] != "repeat":
                problemas.append("`until` sem `repeat`")
            else:
                pilha.pop()
if pilha:
    problemas.append(f"blocos sem fechar: {pilha}")

# No CSP, varias funcoes da API sao nativas (FFI): o `type()` delas e 'cdata', e nao
# 'function'. Conferir `type(ui.x) == 'function'` calou o app no teste no jogo de 18/10.
for linha, texto in enumerate(codigo.splitlines(), 1):
    if re.search(r"type\(\s*(?:web|ui|ac|JSON|os|io)\.[A-Za-z_]+\s*\)\s*[~=]=\s*'function'", texto) or \
            re.search(r"type\(\s*setInterval\s*\)\s*[~=]=\s*'function'", texto):
        problemas.append(f"linha {linha}: `type(...) == 'function'` numa funcao da API (no CSP pode ser 'cdata')")

chamadas = sorted(set(re.findall(r"\b((?:web|ui|ac|JSON|os|io)\.[A-Za-z_]+|setInterval|rgbm|vec2)\b", codigo)))
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
print(f"API usada ({len(chamadas)}): {', '.join(chamadas)}")
print(f"metodos usados ({len(metodos)}): {', '.join(metodos)}")
if sdk:
    print(f"no SDK do CSP: {'todas existem' if not faltam else 'faltam ' + ', '.join(faltam)}")
    print(f"metodos no SDK do CSP: {'todos existem' if not metodos_faltam else 'faltam ' + ', '.join(metodos_faltam)}")
sys.exit(1 if erros or problemas or faltam or metodos_faltam else 0)
