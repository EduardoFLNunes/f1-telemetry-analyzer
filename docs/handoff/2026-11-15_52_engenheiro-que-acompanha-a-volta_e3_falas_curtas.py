"""Pedido 52, E.3: a duracao, com a voz do projeto (Microsoft Daniel, sem a vinheta), das falas candidatas das
opcoes (as formas curtas, as falas juntas, a lista na reta) a 1,4x (a de hoje) e a 1,7x.

Uso (na pasta backend): python <este arquivo> <saida.json>
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, ".")
from core.radio.audio import falar  # noqa: E402

FALAS = {
    # hoje (o molde curto da emenda de 16/11)
    "hoje_freie_placa": "Freie 10 metros depois da placa de 100.",
    "hoje_freie_zebra": "Freie 35 metros antes do começo da zebra à direita.",
    "hoje_vire_zebra": "Vire 5 metros depois do começo da zebra à direita.",
    "hoje_sem_tirar": "Sem tirar o pé.",
    # formas curtas (o marco e os metros, sem o verbo e sem "metros")
    "curta_placa": "Cem, mais dez.",
    "curta_placa_na": "No cinquenta.",
    "curta_zebra": "Zebra, menos cinco.",
    "curta_zebra_fim": "Fim da zebra.",
    "curta_freie_placa": "Freie no cem, mais dez.",
    "curta_vire_zebra": "Vire na zebra, mais cinco.",
    "curta_acelere_zebra": "Acelere no fim da zebra.",
    "curta_so_verbo": "Freie.",
    "curta_curva": "Curva sete.",
    # juntas (duas curvas proximas numa fala)
    "junta_7_8": "Sete e oito: freie na zebra, vire na zebra.",
    "junta_9_10": "Nove e dez: vire no fim da zebra, freie na zebra.",
    "junta_2_3": "Dois e tres: vire na zebra, acelere na zebra.",
    # a lista na reta (tres avisos seguidos)
    "lista_reta_oposta": "Quatro: cem, menos dez. Cinco: sem tirar o pé. Seis: vire na zebra.",
    "lista_reta_boxes": "Um: cem, mais dez. Dois: vire na zebra.",
}

pasta = Path(tempfile.mkdtemp(prefix="falas_e3_"))
saida = {}
for velocidade in (1.4, 1.7):
    for nome, texto in FALAS.items():
        dur = float(falar(texto, pasta / f"{nome}_{velocidade}.wav", velocidade=velocidade, vinheta_antes=False))
        saida.setdefault(nome, {"fala": texto})[str(velocidade)] = round(dur, 2)
        print(f"{velocidade}  {dur:5.2f} s  {texto}", flush=True)
Path(sys.argv[1]).write_text(json.dumps({"voz": "OneCore:Daniel, sem a vinheta", "falas": saida}, ensure_ascii=False, indent=1),
                             encoding="utf-8")
