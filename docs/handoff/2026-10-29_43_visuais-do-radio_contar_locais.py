"""Pedido 43, Parte D.2: os limites do LuaJIT que o `conferir_lua.py` nao ve.

Nao ha interpretador de Lua neste computador. O LuaJIT recusa o arquivo inteiro com mais de 200
variaveis locais numa funcao ("too many local variables") e uma funcao com mais de 60 upvalues
("function has more than 60 upvalues"). Para o app, isso seria o silencio no jogo, sem aviso.

A conta usa os tokens do `pygments`, com escopos por bloco:
* as locais de cada funcao (o maximo ao mesmo tempo; as de um bloco que fechou saem da conta);
* os upvalues: os nomes usados numa funcao que sao locais de uma funcao de fora.

Uso: python contar_locais.py <arquivo.lua>
"""
import sys
from pathlib import Path

from pygments.lexers import LuaLexer
from pygments.token import Comment, Name, String, Text

toks = [(t, v) for t, v in LuaLexer().get_tokens(Path(sys.argv[1]).read_text(encoding="utf-8"))
        if t not in Text and t not in Comment and v.strip()]


class Funcao:
    def __init__(self, nome, pai):
        self.nome, self.pai = nome, pai
        self.blocos = [set()]
        self.ativas = self.maximo = 0
        self.upvalues = set()

    def declarar(self, nome):
        self.blocos[-1].add(nome)
        self.ativas = sum(len(b) for b in self.blocos)
        self.maximo = max(self.maximo, self.ativas)

    def tem(self, nome):
        return any(nome in b for b in self.blocos)


raiz = Funcao("(arquivo)", None)
atual = raiz
pilha = []          # "bloco" ou "funcao"
todas = [raiz]
i = 0


def valor(k):
    return toks[k][1] if k < len(toks) else ""


def abrir_funcao(nome, k):
    """Abre a funcao e declara os parametros; devolve o indice depois do `)`."""
    global atual
    f = Funcao(nome, atual)
    todas.append(f)
    atual = f
    pilha.append("funcao")
    while valor(k) != "(":
        k += 1
    k += 1
    while valor(k) != ")":
        if toks[k][0] in Name or valor(k) == "...":
            if valor(k) != "...":
                f.declarar(valor(k))
        k += 1
    return k + 1


while i < len(toks):
    tipo, v = toks[i]
    if tipo in String:
        i += 1
        continue
    if v == "local" and valor(i + 1) == "function":
        atual.declarar(valor(i + 2))
        i = abrir_funcao(valor(i + 2), i + 2)
        continue
    if v == "local":
        k = i + 1
        nomes = []
        while True:
            nomes.append(valor(k))
            k += 1
            if valor(k) == "<":   # atributos nao existem no LuaJIT, mas nao custa
                k += 3
            if valor(k) != ",":
                break
            k += 1
        for n in nomes:
            atual.declarar(n)
        i = k
        continue
    if v == "function":
        k = i + 1
        nome = ""
        while valor(k) != "(":
            nome += valor(k)
            k += 1
        i = abrir_funcao(nome or "(anonima)", k)
        continue
    if v == "for":
        # as variaveis do for valem no bloco dele
        atual.blocos.append(set())
        pilha.append("bloco")
        k = i + 1
        while valor(k) not in ("=", "in"):
            if toks[k][0] in Name:
                atual.declarar(valor(k))
            k += 1
        i = k
        continue
    if v in ("if", "while", "repeat"):
        atual.blocos.append(set())
        pilha.append("bloco")
    elif v == "do":
        # `do` de um `for` ou `while` nao abre outro bloco: eles ja abriram
        anterior = 0
        prof = 0
        k = i - 1
        while k >= 0:
            w = valor(k)
            if w in ("for", "while") and prof == 0:
                anterior = 1
                break
            if w in ("do", "then", "end", "repeat", "until", "function", "else", "elseif") or (w == "local"):
                break
            k -= 1
        if not anterior:
            atual.blocos.append(set())
            pilha.append("bloco")
    elif v in ("end", "until"):
        o_que = pilha.pop() if pilha else None
        if o_que == "funcao":
            atual = atual.pai
        elif o_que == "bloco" and len(atual.blocos) > 1:
            atual.blocos.pop()
            atual.ativas = sum(len(b) for b in atual.blocos)
    elif tipo in Name and valor(i - 1) not in (".", ":"):
        # um nome usado: e upvalue se e local de uma funcao de fora
        if not atual.tem(v):
            f = atual.pai
            while f is not None:
                if f.tem(v):
                    g = atual
                    while g is not f:
                        g.upvalues.add(v)
                        g = g.pai
                    break
                f = f.pai
    i += 1

print(f"locais no nivel de cima: {raiz.maximo} (limite 200)")
print("mais locais numa funcao:", [(f.nome, f.maximo) for f in sorted(todas[1:], key=lambda f: -f.maximo)[:3]])
print("mais upvalues numa funcao (limite 60):", [(f.nome, len(f.upvalues)) for f in sorted(todas[1:], key=lambda f: -len(f.upvalues))[:5]])
ok = raiz.maximo <= 200 and all(f.maximo <= 200 and len(f.upvalues) <= 60 for f in todas)
print("dentro dos limites" if ok else "PASSOU DE UM LIMITE")
sys.exit(0 if ok else 1)
