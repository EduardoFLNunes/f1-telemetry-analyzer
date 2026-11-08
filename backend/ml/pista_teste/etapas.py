"""As Partes C e E do pedido 47 (ADR 0029): os arquivos das linhas e o resultado do teste no jogo."""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import numpy as np

from .. import config
from . import ai_spline as A
from . import condicoes as C
from . import linha_nova as N
from . import registro as R

# ADR 0029, itens 5, 7 e 8.
COBERTURA_MINIMA = 0.95
SAIDA_DO_CORREDOR_MAX_M = 1.0
RODADA_ANGULO_GRAUS = 45.0
RODADA_VELOCIDADE_KMH = 30.0
BOX_DISTANCIA_M = 3.0
BOX_FORA_DO_CORREDOR_M = 1.0
REAMOSTRAGENS = 10_000
SEMENTE = 47
NAO_INFERIOR_S = 0.10
DERIVA_S = 0.15
MINIMO_DE_VALIDAS = 5
MINIMO_C0_FINAL = 3


def _json(path: Path, payload) -> None:
    from ..scripts.pista_teste import _padrao

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=1, ensure_ascii=False, default=_padrao), encoding="utf-8")


def pasta_das_linhas() -> Path:
    return C.raiz_saida() / "linhas"


# ------------------------------------------------------------------ parte C ---

def linhas(args) -> int:
    from ..data.store_v2 import git_commit
    from ..track.geometry import load_corridor_geometry

    caminho = C.fast_lane_original()
    raw = caminho.read_bytes()
    original = A.ler(raw)
    track = load_corridor_geometry()
    laterais = C.linhas(track, original.pos[:, [0, 2]].astype(float))
    saida = pasta_das_linhas()
    saida.mkdir(parents=True, exist_ok=True)
    manifesto = {"pedido": 47, "parte": "C", "commit": git_commit(), "comando": "python -m ml.scripts.pista_teste linhas",
                 "original": {"caminho": caminho, "sha256": A.sha256_bytes(raw), "bytes": len(raw)},
                 "geometry_id": track.geometry_id, "corridor_id": track.corridor_id, "condicoes": {}}
    splines = {"C0": original}
    for nome in C.CONDICOES:
        destino = saida / nome / "fast_lane.ai"
        destino.parent.mkdir(parents=True, exist_ok=True)
        if nome == "C0":
            dados = raw
            extra = {}
        else:
            ln = N.montar(original, track, laterais[nome])
            dados = A.escrever(ln.spline)
            splines[nome] = ln.spline
            extra = {"deslocamento_do_original_m": {"mediana": float(np.median(ln.deslocamento_m)),
                                                    "max": float(ln.deslocamento_m.max())}}
        destino.write_bytes(dados)
        relido = A.ler(destino)
        conferido = A.escrever(relido) == dados and relido.n == original.n
        manifesto["condicoes"][nome] = {"descricao": C.DESCRICAO[nome], "arquivo": destino, "bytes": len(dados),
                                        "sha256": A.sha256_arquivo(destino), "pontos": relido.n,
                                        "relido_igual": bool(conferido), **extra}
        if not conferido:
            raise SystemExit(f"PARADO: o arquivo de {nome} nao volta igual depois de relido.")
    _json(saida / "linhas.json", manifesto)
    if args.handoff:
        _json(Path(str(args.handoff) + "_linhas.json"), manifesto)
        figura(track, splines, Path(str(args.handoff) + "_linhas_na_pista.png"))
    for nome, item in manifesto["condicoes"].items():
        print(f"{nome}  {item['sha256']}  {item['bytes']} bytes")
    return 0


def figura(track, splines: Dict[str, A.AiSpline], destino: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from ..track.corners import detect_corners

    cores = {"C0": "#222222", "C1": "#1f77b4", "C2": "#2ca02c", "C3": "#d62728", "C4": "#ff7f0e"}
    esq = track.points + track.normal * track.width_left[:, None]
    dir_ = track.points - track.normal * track.width_right[:, None]
    c10 = detect_corners(track)[9]
    trechos = [("toda a pista", None),
               (f"C10 e o microssetor 36 (s de {2600:.0f} a {c10.end_s:.0f} m)", (2560.0, c10.end_s + 20)),
               ("a saída da linha de chegada (microssetores 0 e 1, s de 0 a 144 m)", (-40.0, 170.0))]
    fig, axes = plt.subplots(1, 3, figsize=(18, 6.5), gridspec_kw={"width_ratios": [1.3, 1, 1]})
    for ax, (titulo, faixa) in zip(axes, trechos):
        ax.plot(esq[:, 0], esq[:, 1], color="#999999", lw=0.8)
        ax.plot(dir_[:, 0], dir_[:, 1], color="#999999", lw=0.8)
        for nome, sp in splines.items():
            xz = sp.pos[:, [0, 2]].astype(float)
            ax.plot(np.r_[xz[:, 0], xz[0, 0]], np.r_[xz[:, 1], xz[0, 1]], color=cores[nome], lw=1.0 if faixa is None else 1.6,
                    label=f"{nome}: {C.DESCRICAO[nome][:48]}")
        if faixa is not None:
            s0, s1 = faixa
            sel = np.mod(np.arange(int(s0 // track.step), int(s1 // track.step) + 1), track.size)
            pts = np.vstack([esq[sel], dir_[sel]])
            pad = 8.0
            ax.set_xlim(pts[:, 0].min() - pad, pts[:, 0].max() + pad)
            ax.set_ylim(pts[:, 1].min() - pad, pts[:, 1].max() + pad)
        ax.set_aspect("equal")
        ax.set_title(titulo, fontsize=10)
        ax.set_xlabel("X (m)")
        ax.set_ylabel("Z (m)")
        ax.grid(alpha=0.25)
    axes[0].legend(fontsize=7, loc="lower left")
    fig.suptitle("Interlagos [teste]: as 5 linhas da IA (pedido 47), com as bordas do corredor do pedido 44 em cinza")
    fig.tight_layout()
    fig.savefig(destino, dpi=120)
    plt.close(fig)


# ------------------------------------------------------- parte E: medidas ---

def angulo_com_a_pista(track, aligned) -> np.ndarray:
    """Angulo (graus) entre a direcao do movimento (X/Z) e a tangente da pista no ponto projetado."""
    x = aligned["x"].to_numpy(float)
    z = aligned["z"].to_numpy(float)
    if len(x) < 3:
        return np.zeros(len(x))
    v = np.column_stack([np.gradient(x), np.gradient(z)])
    norma = np.linalg.norm(v, axis=1)
    u = v / np.where(norma > 1e-9, norma, 1.0)[:, None]
    t = track.tangent[track.index_of(aligned["s"].to_numpy(float))]
    cos = np.clip(np.sum(u * t, axis=1), -1.0, 1.0)
    ang = np.degrees(np.arccos(cos))
    return np.where(norma > 1e-9, ang, 0.0)


def saida_por_amostra(track, aligned) -> np.ndarray:
    from ..track.trajectory import corridor_violation

    low, high = track.corridor()
    idx = track.index_of(aligned["s"].to_numpy(float))
    lat = aligned["lateral"].to_numpy(float)
    return np.maximum(np.maximum(low[idx] - lat, lat - high[idx]), 0.0)


def validade(track, sectors, raw_frame, aligned, alignment, grid, pit_lane_xz: Optional[np.ndarray]) -> Dict[str, object]:
    """ADR 0029, item 5: a volta e valida? Com o motivo de cada falha."""
    from ..data.ai_detector import pit_lap
    from ..track.trajectory import corridor_violation

    motivos: List[str] = []
    medidas: Dict[str, float] = {"cobertura": float(alignment.coverage)}
    if alignment.coverage < COBERTURA_MINIMA:
        motivos.append(f"incompleta (cobertura {alignment.coverage:.3f})")
    lat = grid["lateral"].to_numpy(float)
    saida = float(np.nanmax(corridor_violation(track, np.nan_to_num(lat)))) if np.isfinite(lat).any() else np.inf
    medidas["saida_do_corredor_m"] = saida
    if not saida <= SAIDA_DO_CORREDOR_MAX_M:
        motivos.append(f"fora do corredor ({saida:.2f} m)")
    off = raw_frame["off_track"] if "off_track" in raw_frame else None
    if off is not None and off.fillna(False).astype(bool).any():
        motivos.append("offTrack do jogo")
    ang = angulo_com_a_pista(track, aligned)
    vel = aligned["speed_kmh"].to_numpy(float) if "speed_kmh" in aligned else np.zeros(len(ang))
    rapido = vel > RODADA_VELOCIDADE_KMH
    medidas["maior_angulo_graus"] = float(np.max(ang[rapido])) if rapido.any() else 0.0
    if rapido.any() and np.max(ang[rapido]) > RODADA_ANGULO_GRAUS:
        motivos.append(f"rodada ({medidas['maior_angulo_graus']:.0f} graus)")
    box = bool(pit_lap(grid, sectors))
    if pit_lane_xz is not None and len(aligned):
        pts = aligned[["x", "z"]].to_numpy(float)
        _, _, d = N._projetar_na_polilinha(pts, pit_lane_xz)
        box = box or bool(np.any((d <= BOX_DISTANCIA_M) & (saida_por_amostra(track, aligned) > BOX_FORA_DO_CORREDOR_M)))
    if box:
        motivos.append("boxes")
    ai = raw_frame["ai_controlled"] if "ai_controlled" in raw_frame else None
    if ai is None or not ai.fillna(False).astype(bool).all():
        motivos.append("a IA nao dirigiu a volta inteira (isAIControlled)")
    return {"valida": not motivos, "motivos": motivos, **medidas}


def tempos_por_microssetor(grid, track, sectors, lap_time_s: float) -> np.ndarray:
    elapsed = grid["elapsed_s"].to_numpy(float)
    ok = np.isfinite(elapsed)
    bordas = np.interp(sectors.edges_s[:-1], track.s[ok], elapsed[ok])
    bordas = np.r_[bordas, lap_time_s]
    return np.diff(bordas)


# --------------------------------------------------- parte E: estatistica ---

def bootstrap_diferenca(a: Sequence[float], b: Sequence[float], reamostragens: int = REAMOSTRAGENS,
                        semente: int = SEMENTE) -> Dict[str, float]:
    """Mediana(a) - mediana(b), com o intervalo de 95% por bootstrap (um gerador novo por comparacao)."""
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    rng = np.random.default_rng(semente)
    ia = rng.integers(0, len(a), size=(reamostragens, len(a)))
    ib = rng.integers(0, len(b), size=(reamostragens, len(b)))
    difs = np.median(a[ia], axis=1) - np.median(b[ib], axis=1)
    return {"diferenca_s": float(np.median(a) - np.median(b)), "ic95_inferior_s": float(np.percentile(difs, 2.5)),
            "ic95_superior_s": float(np.percentile(difs, 97.5))}


def veredito(dif: Optional[Dict[str, float]], validas: int, contam_existentes: int, deriva: bool = False) -> str:
    """ADR 0029, itens 7 e 8."""
    if validas < MINIMO_DE_VALIDAS:
        if contam_existentes < R.VOLTAS_QUE_CONTAM["C1"]:
            return "incompleta (conferir o motivo nas anotacoes)"
        return "nao dirigivel pela IA"
    if dif is None:
        return "nao conclusivo"
    if deriva:
        return "nao conclusivo (deriva)"
    lo, hi = dif["ic95_inferior_s"], dif["ic95_superior_s"]
    if hi < 0:
        return "mais rapida que a linha da IA"
    if hi <= NAO_INFERIOR_S:
        return "tao rapida quanto (nao inferior)"
    if lo > NAO_INFERIOR_S:
        return "mais lenta"
    return "nao conclusivo"


def tempo_mmss(segundos: float) -> str:
    if segundos is None or not np.isfinite(segundos):
        return "-"
    m = int(segundos // 60)
    s = segundos - 60 * m
    return f"{m}:{s:06.3f}".replace(".", ",")


# ------------------------------------------- parte E.1: a troca pegou? ---

def conferir_troca(pontos: Dict[str, List[np.ndarray]], linhas_xz: Dict[str, np.ndarray]) -> Dict[str, dict]:
    """ADR 0029, item 9: a mediana das distancias das posicoes gravadas a linha da condicao e a linha original.

    `pontos`: {condicao: [posicoes X/Z de cada volta que conta]}. A troca pegou quando a mediana ate a
    linha da condicao e menor que ate a original (no C0 e no C0 final, a linha e a propria original).
    """
    out = {}
    for cond, lista in pontos.items():
        lista = [p for p in lista if len(p)]
        if not lista:
            continue
        base = "C0" if cond == R.C0_FINAL else cond
        pts = np.vstack(lista)
        d_linha = float(np.median(N._projetar_na_polilinha(pts, linhas_xz[base])[2]))
        d_orig = float(np.median(N._projetar_na_polilinha(pts, linhas_xz["C0"])[2]))
        out[cond] = {"voltas": len(lista), "mediana_ate_a_linha_da_condicao_m": d_linha,
                     "mediana_ate_a_linha_original_m": d_orig,
                     "troca_pegou": True if base == "C0" else bool(d_linha < d_orig)}
    return out


def conferencia(args) -> int:
    """So a conferencia da troca (E.1), entre as sessoes no jogo. **Nao calcula nem mostra nenhum tempo.**

    Cada volta passa por `clean_lap` e `align_lap` (as posicoes e a cobertura); os papeis (saida, primeira
    lancada, as que contam) sao os do ADR 0029. Sai `data/pista_teste/conferencia_<rotulo>.json`.
    """
    from ..data.recordings import iter_laps, list_all_sessions
    from ..data.store_v2 import git_commit
    from ..preprocessing.alignment import align_lap
    from ..preprocessing.cleaning import clean_lap
    from ..track.geometry import load_corridor_geometry

    saida = C.raiz_saida()
    if not (saida / "registro.csv").exists():
        raise SystemExit(f"PARADO: sem {saida / 'registro.csv'}.")
    manifesto = json.loads((pasta_das_linhas() / "linhas.json").read_text(encoding="utf-8"))
    esperado = {k: v["sha256"] for k, v in manifesto["condicoes"].items()}
    sha_original_agora = A.sha256_arquivo(C.fast_lane_original())
    trocas = R.ler(saida / "registro.csv")
    track = load_corridor_geometry()
    linhas_xz = {k: A.ler(pasta_das_linhas() / k / "fast_lane.ai").pos[:, [0, 2]].astype(float) for k in C.CONDICOES}
    sessoes = list_all_sessions(track_prefixes=(C.PISTA_COPIA,), incluir_pistas_de_teste=True)
    inicios = {s.session_id: _inicio(s) for s in sessoes}
    atrib = R.atribuir({k: v for k, v in inicios.items() if v is not None}, trocas, esperado)
    por_sessao = {a.sessao: a for a in atrib}

    por_condicao: Dict[str, List[dict]] = {}
    for sessao in sessoes:
        a = por_sessao.get(sessao.session_id)
        if a is None or not a.condicao:
            continue
        laps = list(iter_laps(sessao))
        for i, lap in enumerate(laps):
            cleaned, _ = clean_lap(lap.frame)
            aligned, alignment = align_lap(cleaned, track)
            ai = lap.frame["ai_controlled"] if "ai_controlled" in lap.frame else None
            ordem = float(lap.frame["timestamp_s"].iloc[0]) if "timestamp_s" in lap.frame else float(i)
            por_condicao.setdefault(a.condicao, []).append({
                "sessao": sessao.session_id, "sequencia": lap.sequence, "ordem": ordem, "primeira": i == 0,
                "interrompida": i == len(laps) - 1 and alignment.coverage < COBERTURA_MINIMA,
                "cobertura": float(alignment.coverage),
                "ia_dirigiu": bool(ai is not None and ai.fillna(False).astype(bool).all()),
                "xz": aligned[["x", "z"]].to_numpy(float) if len(aligned) else np.zeros((0, 2))})
    papeis_por_condicao = {}
    for cond, lista in por_condicao.items():
        objs = [R.VoltaNaCondicao(v["sessao"], v["sequencia"], v["ordem"], v["primeira"], v["interrompida"]) for v in lista]
        R.papeis(cond, objs)
        papel = {(o.sessao, o.sequencia): o.papel for o in objs}
        for v in lista:
            v["papel"] = papel[(v["sessao"], v["sequencia"])]
        papeis_por_condicao[cond] = {p: sum(v["papel"] == p for v in lista) for p in
                                     ("saida", "primeira lancada", "conta", "alem das que contam", "interrompida")}
        papeis_por_condicao[cond]["que_contam_com_a_ia_dirigindo"] = sum(v["papel"] == "conta" and v["ia_dirigiu"] for v in lista)
    troca = conferir_troca({c: [v["xz"] for v in lista if v["papel"] == "conta"] for c, lista in por_condicao.items()},
                           linhas_xz)
    payload = {"pedido": 47, "parte": "E.1 entre as sessoes (sem tempos)", "commit": git_commit(),
               "comando": f"python -m ml.scripts.pista_teste conferencia --rotulo {args.rotulo}",
               "original_intacto": manifesto["original"]["sha256"] == sha_original_agora,
               "trocas_no_registro": [{"hora": t.hora.isoformat(), "condicao": t.condicao, "sha256": t.sha256} for t in trocas],
               "atribuicao": [{"sessao": a.sessao, "inicio": a.inicio.isoformat(), "condicao": a.condicao, "motivo": a.motivo}
                              for a in atrib],
               "voltas_por_papel": papeis_por_condicao, "a_ia_seguiu_a_linha": troca}
    _json(saida / f"conferencia_{args.rotulo}.json", payload)
    if args.handoff:
        _json(Path(str(args.handoff) + f"_conferencia_{args.rotulo}.json"), payload)
    print("original intacto:", payload["original_intacto"])
    for a in payload["atribuicao"]:
        print(f"gravacao {a['sessao']}: {a['condicao'] or 'sem condicao (' + a['motivo'] + ')'}")
    for cond, r in troca.items():
        print(f"{cond:9s} voltas que contam {r['voltas']}  ate a linha da condicao {r['mediana_ate_a_linha_da_condicao_m']:.2f} m"
              f"  ate a original {r['mediana_ate_a_linha_original_m']:.2f} m  troca pegou: {r['troca_pegou']}"
              f"  (IA dirigindo em {papeis_por_condicao[cond]['que_contam_com_a_ia_dirigindo']})")
    return 0


# ------------------------------------------------------- parte E: resultado ---

def _inicio(session) -> Optional[datetime]:
    meta = session.metadata() if hasattr(session, "metadata") else {}
    texto = meta.get("startedAt")
    return datetime.fromisoformat(texto) if texto else None


def resultado(args) -> int:
    from ..data.recordings import iter_laps, list_all_sessions
    from ..data.store_v2 import game_lap_time, git_commit
    from ..preprocessing.alignment import align_lap
    from ..preprocessing.cleaning import clean_lap
    from ..preprocessing.resampling import lap_time_from_grid, resample_lap
    from ..track.geometry import load_corridor_geometry
    from ..track.microsectors import build_microsectors

    saida = C.raiz_saida()
    if not (saida / "registro.csv").exists():
        raise SystemExit(f"PARADO: sem {saida / 'registro.csv'}: o teste no jogo ainda nao aconteceu.")
    manifesto = json.loads((pasta_das_linhas() / "linhas.json").read_text(encoding="utf-8"))
    esperado = {k: v["sha256"] for k, v in manifesto["condicoes"].items()}
    original = C.fast_lane_original()
    sha_original_agora = A.sha256_arquivo(original)
    trocas = R.ler(saida / "registro.csv")
    track = load_corridor_geometry()
    sectors = build_microsectors(track)
    copia_ai = C.pasta_do_jogo() / "content" / "tracks" / C.PISTA_COPIA / C.LAYOUT / "ai"
    pit = A.ler(original.with_name("pit_lane.ai")) if original.with_name("pit_lane.ai").exists() else None
    pit_xz = pit.pos[:, [0, 2]].astype(float) if pit is not None else None
    linhas_xz = {k: A.ler(pasta_das_linhas() / k / "fast_lane.ai").pos[:, [0, 2]].astype(float) for k in C.CONDICOES}

    sessoes = list_all_sessions(track_prefixes=(C.PISTA_COPIA,), incluir_pistas_de_teste=True)
    inicios = {s.session_id: _inicio(s) for s in sessoes}
    sem_inicio = [k for k, v in inicios.items() if v is None]
    atrib = R.atribuir({k: v for k, v in inicios.items() if v is not None}, trocas, esperado)
    por_sessao = {a.sessao: a for a in atrib}

    voltas: List[dict] = []
    for sessao in sessoes:
        a = por_sessao.get(sessao.session_id)
        laps = list(iter_laps(sessao))
        for i, lap in enumerate(laps):
            cleaned, _ = clean_lap(lap.frame)
            aligned, alignment = align_lap(cleaned, track)
            grid = resample_lap(aligned, track, line_clock=True)
            seguinte = laps[i + 1] if i + 1 < len(laps) else None
            tempo = lap_time_from_grid(grid)
            item = {"sessao": sessao.session_id, "sequencia": lap.sequence, "volta_do_jogo": lap.lap_number,
                    "condicao": a.condicao if a else None, "motivo_sem_condicao": (a.motivo if a else "sem inicio"),
                    "tempo_s": float(tempo), "tempo_jogo_s": game_lap_time(lap, seguinte, track),
                    "inicio_s": (float(lap.frame["timestamp_s"].iloc[0]) if "timestamp_s" in lap.frame
                                 else inicios[sessao.session_id].timestamp() + i),
                    "primeira_da_gravacao": i == 0,
                    "interrompida": i == len(laps) - 1 and alignment.coverage < COBERTURA_MINIMA}
            item.update(validade(track, sectors, lap.frame, aligned, alignment, grid, pit_xz))
            if item["valida"] and np.isfinite(tempo):
                item["microssetores_s"] = tempos_por_microssetor(grid, track, sectors, float(tempo)).tolist()
            pts = aligned[["x", "z"]].to_numpy(float) if len(aligned) else np.zeros((0, 2))
            item["xz"] = pts
            voltas.append(item)

    # Os papeis (saida, primeira lancada, conta...) por condicao, na ordem do tempo.
    por_condicao: Dict[str, List[dict]] = {}
    for v in voltas:
        if v["condicao"]:
            por_condicao.setdefault(v["condicao"], []).append(v)
    for cond, lista in por_condicao.items():
        objs = [R.VoltaNaCondicao(v["sessao"], v["sequencia"], v["inicio_s"], v["primeira_da_gravacao"], v["interrompida"])
                for v in lista]
        R.papeis(cond, objs)
        papel = {(o.sessao, o.sequencia): o.papel for o in objs}
        for v in lista:
            v["papel"] = papel[(v["sessao"], v["sequencia"])]

    # E.1: a IA seguiu a linha da condicao?
    conferencia = conferir_troca({cond: [v["xz"] for v in lista if v.get("papel") == "conta"]
                                  for cond, lista in por_condicao.items()}, linhas_xz)

    def validas(cond):
        return [v for v in por_condicao.get(cond, []) if v.get("papel") == "conta" and v["valida"]]

    def tempos(cond):
        return np.array([v["tempo_s"] for v in validas(cond)], float)

    resumo = {}
    for cond in ("C0", "C1", "C2", "C3", "C4", R.C0_FINAL):
        t = tempos(cond)
        contam = [v for v in por_condicao.get(cond, []) if v.get("papel") == "conta"]
        resumo[cond] = {"voltas_que_contam": len(contam), "validas": int(len(t)),
                        "mediana_s": float(np.median(t)) if len(t) else None,
                        "mediana": tempo_mmss(float(np.median(t))) if len(t) else "-",
                        "desvio_s": float(np.std(t, ddof=1)) if len(t) > 1 else None,
                        "iqr_s": float(np.subtract(*np.percentile(t, [75, 25]))) if len(t) > 1 else None,
                        "min": tempo_mmss(float(t.min())) if len(t) else "-", "max": tempo_mmss(float(t.max())) if len(t) else "-"}

    deriva = None
    if resumo["C0"]["validas"] and resumo[R.C0_FINAL]["validas"] >= MINIMO_C0_FINAL:
        deriva = abs(resumo[R.C0_FINAL]["mediana_s"] - resumo["C0"]["mediana_s"])
    com_deriva = deriva is not None and deriva > DERIVA_S

    comparacoes, vereditos = {}, {}
    for cond, ref in (("C3", "C0"), ("C4", "C0"), ("C1", "C0"), ("C2", "C0"), ("C3", "C1"), ("C4", "C1")):
        a, b = tempos(cond), tempos(ref)
        comparacoes[f"{cond} contra {ref}"] = bootstrap_diferenca(a, b) if len(a) and len(b) else None
    for cond in ("C3", "C4"):
        ok = conferencia.get(cond, {}).get("troca_pegou", False)
        if not ok:
            vereditos[cond] = "fora do veredito: a troca nao pegou (E.1)" if cond in conferencia else "sem voltas"
            continue
        vereditos[cond] = veredito(comparacoes[f"{cond} contra C0"], resumo[cond]["validas"],
                                   resumo[cond]["voltas_que_contam"], com_deriva)

    # E.5: por microssetor, C3 contra C0, ao lado do medidor.
    medidor = json.loads((saida / "medidor.json").read_text(encoding="utf-8"))
    micro = {}
    for cond in ("C3", "C4"):
        ma = [v["microssetores_s"] for v in validas(cond) if "microssetores_s" in v]
        mb = [v["microssetores_s"] for v in validas("C0") if "microssetores_s" in v]
        if ma and mb:
            dif = np.median(np.array(ma), axis=0) - np.median(np.array(mb), axis=0)
            micro[cond] = {"jogo_s": dif.tolist(), "medidor_s": medidor["tempos"][cond]["por_microssetor_contra_c0_s"],
                           "destaque": {str(i): {"jogo_s": float(dif[i]),
                                                 "medidor_s": float(medidor["tempos"][cond]["por_microssetor_contra_c0_s"][i])}
                                        for i in (36, 0, 1)}}
    ordem_jogo = sorted([c for c in C.CONDICOES if resumo[c]["mediana_s"] is not None], key=lambda c: resumo[c]["mediana_s"])

    payload = {
        "pedido": 47, "parte": "E", "commit": git_commit(), "comando": "python -m ml.scripts.pista_teste resultado",
        "conferencia_do_teste": {
            "gravacoes_da_copia": [s.session_id for s in sessoes], "gravacoes_sem_inicio": sem_inicio,
            "trocas_no_registro": [{"hora": t.hora.isoformat(), "condicao": t.condicao, "sha256": t.sha256} for t in trocas],
            "sha256_original_antes": manifesto["original"]["sha256"], "sha256_original_agora": sha_original_agora,
            "original_intacto": manifesto["original"]["sha256"] == sha_original_agora,
            "copia_ai_existe": copia_ai.exists()},
        "atribuicao": [{"sessao": a.sessao, "inicio": a.inicio.isoformat(), "condicao": a.condicao, "motivo": a.motivo} for a in atrib],
        "a_ia_seguiu_a_linha": conferencia,
        "voltas": [{k: v for k, v in item.items() if k not in ("xz", "microssetores_s")} for item in voltas],
        "resumo": resumo, "deriva_s": deriva, "com_deriva": com_deriva,
        "comparacoes": comparacoes, "vereditos": vereditos, "por_microssetor": micro,
        "ordem": {"jogo": ordem_jogo, "medidor": medidor["ordem_do_medidor"]},
    }
    _json(saida / "resultado.json", payload)
    if args.handoff:
        _json(Path(str(args.handoff) + "_resultado.json"), payload)
    for cond, r in resumo.items():
        print(f"{cond:9s} validas {r['validas']}/{r['voltas_que_contam']}  mediana {r['mediana']}")
    print(json.dumps(vereditos, indent=1, ensure_ascii=False))
    return 0
