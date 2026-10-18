"""Confere o app Lua sem o jogo e sem instalar nada (pedido 31, Parte E.3).

Nao ha interpretador de Lua neste computador. O que da para conferir:

1. **O lexico:** o `pygments` (ja no .venv) le o arquivo com o lexer de Lua; um
   token de erro e um erro de lexico (string sem fechar, caractere estranho).
2. **Os blocos:** cada `function`, `if`, `for`, `while` e `do` solto fecha com um
   `end`, e cada `repeat` com um `until`, na ordem.
3. **A API usada:** cada chamada `web.`, `ui.`, `ac.`, `JSON.`, `os.` e
   `setInterval` existe no `lib.lua` do SDK do CSP instalado (so leitura).

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

chamadas = sorted(set(re.findall(r"\b((?:web|ui|ac|JSON|os)\.[A-Za-z_]+|setInterval|rgbm|vec2)\b", codigo)))
faltam = []
if sdk and sdk.exists():
    lib = sdk.read_text(encoding="utf-8", errors="replace")
    for c in chamadas:
        if c in ("os.preciseClock",) and "function os.preciseClock" in lib:
            continue
        padrao = rf"function {re.escape(c)}\(|^{re.escape(c)} = |^---@class {re.escape(c)}\b"
        if not re.search(padrao, lib, re.MULTILINE):
            faltam.append(c)

print(f"arquivo: {arquivo}")
print(f"tokens: {len(tokens)}; erros de lexico: {len(erros)} {erros[:5]}")
print(f"blocos: {'ok' if not problemas else problemas}")
print(f"API usada ({len(chamadas)}): {', '.join(chamadas)}")
if sdk:
    print(f"no SDK do CSP: {'todas existem' if not faltam else 'faltam ' + ', '.join(faltam)}")
sys.exit(1 if erros or problemas or faltam else 0)
