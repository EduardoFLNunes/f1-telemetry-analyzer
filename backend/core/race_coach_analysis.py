from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import math
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


COACHING_SOURCES = {"RACING_LINE_REFERENCE", "CURRENT_LAP", "UNKNOWN"}
CONFIDENCE_ORDER = {"HIGH": 3, "MEDIUM": 2, "LOW": 1, "INSUFFICIENT_DATA": 0}
SEVERITY_ORDER = {"HIGH": 4, "MEDIUM": 3, "LOW": 2, "INFO": 1}
TOP_INSIGHT_LIMIT = 6
MAX_INSIGHTS_PER_TYPE = 2
LOW_SPEED_DELTA_KMH = -4.0
HIGH_TRAJECTORY_DEVIATION_METERS = 5.0
MIN_LOSS_SECONDS = 0.03
MIN_GAIN_SECONDS = -0.05


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _safe_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number


def _round_or_none(value: Optional[float], digits: int = 4) -> Optional[float]:
    return round(value, digits) if value is not None and math.isfinite(value) else None


def _sector(value: Any) -> Optional[int]:
    number = _safe_int(value)
    return number if number in (1, 2, 3) else None


def _issue_from_segment(segment: Mapping[str, Any]) -> str:
    main_issue = str(segment.get("mainIssue") or "UNKNOWN")
    speed_delta = _safe_float(segment.get("speedDeltaKmh"))
    delta = _safe_float(segment.get("estimatedDeltaSeconds"))
    trajectory = _safe_float(segment.get("trajectoryDeviationMeters"))
    player_braking = segment.get("playerBraking") is True
    reference_braking = segment.get("racingLineBraking") is True
    player_accelerating = segment.get("playerAccelerating") is True
    reference_accelerating = segment.get("racingLineAccelerating") is True

    if main_issue == "INSUFFICIENT_DATA":
        return "INSUFFICIENT_DATA"
    if main_issue == "TRAJECTORY":
        if trajectory is not None and (delta or 0.0) > MIN_LOSS_SECONDS:
            return "TRAJECTORY_DEVIATION"
        return "UNKNOWN"
    if main_issue in {
        "BRAKING_TOO_EARLY",
        "BRAKING_TOO_LATE",
        "ACCELERATING_TOO_LATE",
        "LOW_CORNER_SPEED",
        "LOW_EXIT_SPEED",
    }:
        return main_issue

    if (
        player_braking
        and not reference_braking
        and (delta or 0.0) > MIN_LOSS_SECONDS
        and (speed_delta or 0.0) < -1.0
    ):
        return "BRAKING_TOO_EARLY"
    if (
        not player_braking
        and reference_braking
        and (delta or 0.0) > MIN_LOSS_SECONDS
        and (speed_delta or 0.0) > 3.0
    ):
        return "BRAKING_TOO_LATE"
    if (
        not player_accelerating
        and reference_accelerating
        and (delta or 0.0) > MIN_LOSS_SECONDS
        and (speed_delta or 0.0) <= -2.0
    ):
        return "ACCELERATING_TOO_LATE"
    if (
        trajectory is not None
        and trajectory >= HIGH_TRAJECTORY_DEVIATION_METERS
        and ((delta or 0.0) > MIN_LOSS_SECONDS or (speed_delta or 0.0) <= LOW_SPEED_DELTA_KMH)
    ):
        return "TRAJECTORY_DEVIATION"
    if (
        speed_delta is not None
        and speed_delta <= LOW_SPEED_DELTA_KMH
        and (delta or 0.0) > MIN_LOSS_SECONDS
        and not reference_accelerating
    ):
        return "LOW_CORNER_SPEED"
    if delta is not None and delta <= MIN_GAIN_SECONDS and speed_delta is not None and speed_delta >= 1.0:
        return "GOOD_GAIN"
    return "UNKNOWN"


def _confidence(segment: Mapping[str, Any], issue_type: str) -> str:
    if issue_type == "INSUFFICIENT_DATA":
        return "INSUFFICIENT_DATA"

    has_speed = _safe_float(segment.get("playerSpeedKmh")) is not None and _safe_float(segment.get("racingLineSpeedKmh")) is not None
    has_delta = _safe_float(segment.get("estimatedDeltaSeconds")) is not None
    has_progress = _safe_float(segment.get("splineStart")) is not None and _safe_float(segment.get("splineEnd")) is not None

    if issue_type == "TRAJECTORY_DEVIATION" and _safe_float(segment.get("trajectoryDeviationMeters")) is None:
        return "LOW"
    if has_speed and has_delta and has_progress:
        return "HIGH"
    if has_speed and has_progress:
        return "MEDIUM"
    if has_delta or has_progress:
        return "LOW"
    return "INSUFFICIENT_DATA"


def _severity(issue_type: str, delta: Optional[float], trajectory: Optional[float]) -> str:
    if issue_type in {"GOOD_GAIN", "INSUFFICIENT_DATA"}:
        return "INFO"

    loss = max(0.0, delta or 0.0)
    if loss >= 0.15 or (trajectory is not None and trajectory >= 7.0 and loss >= 0.08):
        return "HIGH"
    if loss >= 0.07 or (trajectory is not None and trajectory >= 5.0 and loss >= 0.03):
        return "MEDIUM"
    return "LOW"


def _title(issue_type: str) -> str:
    return {
        "BRAKING_TOO_EARLY": "Frenagem antecipada",
        "BRAKING_TOO_LATE": "Frenagem tardia",
        "ACCELERATING_TOO_LATE": "Aceleracao tardia",
        "LOW_CORNER_SPEED": "Baixa velocidade de contorno",
        "LOW_EXIT_SPEED": "Saida de curva lenta",
        "TRAJECTORY_DEVIATION": "Desvio de trajetoria",
        "GOOD_GAIN": "Ganho relevante",
        "SECTOR_LOSS": "Perda no setor",
        "INSUFFICIENT_DATA": "Dados insuficientes",
    }.get(issue_type, "Diagnostico inconclusivo")


def _message(issue_type: str) -> str:
    return {
        "BRAKING_TOO_EARLY": "Voce parece iniciar a frenagem antes da referencia neste trecho.",
        "BRAKING_TOO_LATE": "Voce pode estar freando tarde demais e comprometendo a trajetoria.",
        "ACCELERATING_TOO_LATE": "Voce esta retomando aceleracao depois da referencia.",
        "LOW_CORNER_SPEED": "Voce perdeu tempo por carregar menos velocidade que a referencia.",
        "LOW_EXIT_SPEED": "Voce esta saindo abaixo da velocidade da volta de referencia.",
        "TRAJECTORY_DEVIATION": "Sua trajetoria esta distante da linha de referencia neste trecho.",
        "GOOD_GAIN": "Voce ganhou tempo neste trecho em relacao a referencia.",
        "SECTOR_LOSS": "Este setor concentra a maior perda estimada da volta atual.",
        "INSUFFICIENT_DATA": "Dados insuficientes para diagnostico confiavel neste trecho.",
    }.get(issue_type, "Os dados deste trecho ainda sao inconclusivos.")


def _recommendation(issue_type: str) -> str:
    return {
        "BRAKING_TOO_EARLY": "Teste atrasar levemente o ponto de frenagem, mantendo o carro estavel.",
        "BRAKING_TOO_LATE": "Priorize estabilizar o carro antes do apice da curva.",
        "ACCELERATING_TOO_LATE": "Prepare melhor a entrada para conseguir acelerar mais cedo na saida.",
        "LOW_CORNER_SPEED": "Tente manter mais velocidade no contorno, sem comprometer a saida.",
        "LOW_EXIT_SPEED": "Abra a direcao mais cedo e procure uma retomada progressiva de aceleracao.",
        "TRAJECTORY_DEVIATION": "Compare a entrada e a saida da curva com a Racing Line no mapa.",
        "GOOD_GAIN": "Use este trecho como referencia para repetir o padrao nas proximas voltas.",
        "SECTOR_LOSS": "Revise os microsetores destacados deste setor antes da proxima tentativa.",
        "INSUFFICIENT_DATA": "Complete mais uma volta valida para aumentar a confianca da analise.",
    }.get(issue_type, "Aguarde mais dados antes de alterar sua pilotagem.")


def _evidence(segment: Mapping[str, Any], issue_type: str) -> List[str]:
    evidence: List[str] = []
    speed_delta = _safe_float(segment.get("speedDeltaKmh"))
    delta = _safe_float(segment.get("estimatedDeltaSeconds"))
    trajectory = _safe_float(segment.get("trajectoryDeviationMeters"))
    sector = _sector(segment.get("sector"))
    segment_index = _safe_int(segment.get("segmentIndex"))

    if speed_delta is not None:
        direction = "abaixo" if speed_delta < 0 else "acima"
        evidence.append(f"Velocidade {abs(speed_delta):.1f} km/h {direction} da referencia")
    if delta is not None:
        if delta > 0:
            evidence.append(f"Perda estimada de {delta:.3f}s")
        elif delta < 0:
            evidence.append(f"Ganho estimado de {abs(delta):.3f}s")
    if trajectory is not None:
        evidence.append(f"Desvio medio de trajetoria {trajectory:.1f} m")
    if sector is not None and segment_index is not None:
        evidence.append(f"Setor {sector}, microsetor {segment_index}")
    if segment.get("playerBraking") is not None or segment.get("racingLineBraking") is not None:
        evidence.append(
            "Frenagem jogador/ref: "
            f"{'sim' if segment.get('playerBraking') else 'nao'}/"
            f"{'sim' if segment.get('racingLineBraking') else 'nao'}"
        )
    if issue_type == "INSUFFICIENT_DATA" and not evidence:
        evidence.append("Segmento sem velocidade, delta ou posicao suficientes")
    return evidence[:5]


def generate_segment_insight(segment: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    issue_type = _issue_from_segment(segment)
    confidence = _confidence(segment, issue_type)
    if issue_type == "UNKNOWN":
        return None
    if confidence == "INSUFFICIENT_DATA" and issue_type != "INSUFFICIENT_DATA":
        return None

    delta = _safe_float(segment.get("estimatedDeltaSeconds"))
    trajectory = _safe_float(segment.get("trajectoryDeviationMeters"))
    severity = _severity(issue_type, delta, trajectory)
    sector = _sector(segment.get("sector"))
    segment_index = _safe_int(segment.get("segmentIndex"))
    spline_start = _safe_float(segment.get("splineStart"))
    spline_end = _safe_float(segment.get("splineEnd"))

    return {
        "id": f"{issue_type.lower()}:{sector or 'x'}:{segment_index if segment_index is not None else 'x'}",
        "type": issue_type,
        "severity": severity,
        "confidence": confidence,
        "sector": sector,
        "segmentIndex": segment_index,
        "splineStart": _round_or_none(spline_start, 6),
        "splineEnd": _round_or_none(spline_end, 6),
        "estimatedDeltaSeconds": _round_or_none(delta, 4),
        "speedDeltaKmh": _round_or_none(_safe_float(segment.get("speedDeltaKmh")), 3),
        "trajectoryDeviationMeters": _round_or_none(trajectory, 3),
        "title": _title(issue_type),
        "message": _message(issue_type),
        "evidence": _evidence(segment, issue_type),
        "recommendation": _recommendation(issue_type),
        "source": "RACING_LINE_REFERENCE",
    }


def _group_key(insight: Mapping[str, Any]) -> Tuple[Any, Any]:
    return insight.get("type"), insight.get("sector")


def _merge_group(group: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    if len(group) == 1:
        return group[0]

    first = group[0]
    last = group[-1]
    deltas = [_safe_float(item.get("estimatedDeltaSeconds")) for item in group]
    speed_deltas = [_safe_float(item.get("speedDeltaKmh")) for item in group]
    trajectories = [_safe_float(item.get("trajectoryDeviationMeters")) for item in group]
    valid_deltas = [value for value in deltas if value is not None]
    valid_speed_deltas = [value for value in speed_deltas if value is not None]
    valid_trajectories = [value for value in trajectories if value is not None]
    start_segment = first.get("segmentIndex")
    end_segment = last.get("segmentIndex")

    merged = dict(first)
    merged["id"] = f"{str(first.get('type')).lower()}:{first.get('sector')}:seg{start_segment}-{end_segment}"
    merged["segmentIndex"] = start_segment
    merged["splineStart"] = first.get("splineStart")
    merged["splineEnd"] = last.get("splineEnd")
    merged["estimatedDeltaSeconds"] = _round_or_none(sum(valid_deltas), 4) if valid_deltas else None
    merged["speedDeltaKmh"] = _round_or_none(sum(valid_speed_deltas) / len(valid_speed_deltas), 3) if valid_speed_deltas else None
    merged["trajectoryDeviationMeters"] = _round_or_none(max(valid_trajectories), 3) if valid_trajectories else None
    merged["severity"] = _severity(str(first.get("type")), _safe_float(merged.get("estimatedDeltaSeconds")), _safe_float(merged.get("trajectoryDeviationMeters")))
    merged["confidence"] = min((item.get("confidence") for item in group), key=lambda value: CONFIDENCE_ORDER.get(str(value), 0))
    merged["evidence"] = [
        f"Microsetores consecutivos {start_segment}-{end_segment}",
        *first.get("evidence", [])[:4],
    ]
    return merged


def group_consecutive_insights(insights: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    ordered = sorted(
        insights,
        key=lambda item: (
            item.get("sector") or 99,
            item.get("segmentIndex") if item.get("segmentIndex") is not None else 9999,
            str(item.get("type")),
        ),
    )
    groups: List[List[Dict[str, Any]]] = []
    current: List[Dict[str, Any]] = []
    for insight in ordered:
        previous = current[-1] if current else None
        consecutive = (
            previous is not None
            and _group_key(previous) == _group_key(insight)
            and _safe_int(insight.get("segmentIndex")) is not None
            and _safe_int(previous.get("segmentIndex")) is not None
            and (_safe_int(insight.get("segmentIndex")) or 0) == (_safe_int(previous.get("segmentIndex")) or 0) + 1
        )
        if consecutive:
            current.append(insight)
            continue
        if current:
            groups.append(current)
        current = [insight]
    if current:
        groups.append(current)

    return [_merge_group(group) for group in groups]


def _rank_score(insight: Mapping[str, Any]) -> float:
    delta = _safe_float(insight.get("estimatedDeltaSeconds"))
    loss = max(0.0, delta or 0.0)
    gain_bonus = 0.25 if insight.get("type") == "GOOD_GAIN" else 0.0
    severity = SEVERITY_ORDER.get(str(insight.get("severity")), 0)
    confidence = CONFIDENCE_ORDER.get(str(insight.get("confidence")), 0)
    return loss * 100.0 + severity * 5.0 + confidence + gain_bonus


def rank_coaching_insights(insights: Sequence[Dict[str, Any]], limit: int = TOP_INSIGHT_LIMIT) -> List[Dict[str, Any]]:
    ranked = sorted(insights, key=_rank_score, reverse=True)
    result: List[Dict[str, Any]] = []
    type_counts: Counter[str] = Counter()
    for insight in ranked:
        issue_type = str(insight.get("type") or "UNKNOWN")
        if type_counts[issue_type] >= MAX_INSIGHTS_PER_TYPE:
            continue
        result.append(insight)
        type_counts[issue_type] += 1
        if len(result) >= limit:
            break
    return result


def _map_issue(issue: Optional[str]) -> Optional[str]:
    if not issue:
        return None
    if issue == "TRAJECTORY":
        return "TRAJECTORY_DEVIATION"
    if issue == "GOOD":
        return "GOOD_GAIN"
    if issue in {
        "BRAKING_TOO_EARLY",
        "BRAKING_TOO_LATE",
        "ACCELERATING_TOO_LATE",
        "LOW_CORNER_SPEED",
        "LOW_EXIT_SPEED",
        "INSUFFICIENT_DATA",
        "UNKNOWN",
    }:
        return issue
    return "UNKNOWN"


def build_sector_coaching_summary(segments: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    result = []
    for sector in (1, 2, 3):
        sector_segments = [segment for segment in segments if _sector(segment.get("sector")) == sector]
        deltas = [
            value
            for segment in sector_segments
            if (value := _safe_float(segment.get("estimatedDeltaSeconds"))) is not None
        ]
        issue_counts = Counter(
            issue
            for segment in sector_segments
            if (issue := _map_issue(str(segment.get("mainIssue") or ""))) not in {None, "UNKNOWN", "INSUFFICIENT_DATA", "GOOD_GAIN"}
        )
        sector_delta = sum(deltas) if deltas else None
        main_issue = issue_counts.most_common(1)[0][0] if issue_counts else ("SECTOR_LOSS" if (sector_delta or 0.0) > MIN_LOSS_SECONDS else None)
        if main_issue:
            message = _message(main_issue)
        elif sector_delta is not None and sector_delta < -0.03:
            main_issue = "GOOD_GAIN"
            message = "Voce ganhou tempo neste setor em relacao a referencia."
        else:
            message = "Sem perda relevante neste setor."
        result.append(
            {
                "sector": sector,
                "estimatedDeltaSeconds": _round_or_none(sector_delta, 4),
                "mainIssue": main_issue,
                "message": message,
            }
        )
    return result


def _insufficient_report(
    racing_line_payload: Mapping[str, Any],
    *,
    micro_sectors: int,
    performance_mode: Optional[str],
) -> Dict[str, Any]:
    debug = racing_line_payload.get("debug") if isinstance(racing_line_payload.get("debug"), Mapping) else {}
    lap_selection = debug.get("lapSelection") if isinstance(debug.get("lapSelection"), Mapping) else {}
    return {
        "status": "INSUFFICIENT_DATA",
        "track": racing_line_payload.get("track"),
        "generatedAt": _now_iso(),
        "referenceLapNumber": None,
        "currentLapNumber": lap_selection.get("currentLap"),
        "microSectorCount": micro_sectors,
        "summary": {
            "mainIssue": None,
            "worstSector": None,
            "estimatedTotalLossSeconds": None,
            "totalInsights": 0,
            "highSeverityCount": 0,
        },
        "topInsights": [],
        "sectorInsights": [
            {"sector": sector, "estimatedDeltaSeconds": None, "mainIssue": "INSUFFICIENT_DATA", "message": "Dados insuficientes para diagnostico confiavel."}
            for sector in (1, 2, 3)
        ],
        "debug": {
            "racingLineStatus": str(racing_line_payload.get("status") or "UNKNOWN"),
            "comparisonSegments": 0,
            "validSegments": 0,
            "rejectedSegments": 0,
            "insufficientDataSegments": 0,
            "generatedInsights": 0,
            "performanceMode": performance_mode,
            "reason": debug.get("reason"),
        },
    }


def build_coaching_report(
    racing_line_payload: Mapping[str, Any],
    micro_sectors: int = 50,
    performance_mode: Optional[str] = None,
) -> Dict[str, Any]:
    racing_line = racing_line_payload.get("racingLine")
    comparison = racing_line_payload.get("comparison")
    if (
        racing_line_payload.get("status") != "READY"
        or not isinstance(racing_line, Mapping)
        or not isinstance(comparison, Mapping)
    ):
        return _insufficient_report(
            racing_line_payload,
            micro_sectors=micro_sectors,
            performance_mode=performance_mode,
        )

    segments = list(comparison.get("segments") or [])
    raw_insights = [
        insight
        for segment in segments
        if isinstance(segment, Mapping)
        if (insight := generate_segment_insight(segment)) is not None
    ]
    grouped = group_consecutive_insights(raw_insights)
    ranked = rank_coaching_insights(grouped)
    sector_insights = build_sector_coaching_summary([segment for segment in segments if isinstance(segment, Mapping)])

    loss_values = [
        value
        for segment in segments
        if isinstance(segment, Mapping)
        if (value := _safe_float(segment.get("estimatedDeltaSeconds"))) is not None and value > 0
    ]
    total_loss = sum(loss_values) if loss_values else None
    high_severity_count = sum(1 for insight in ranked if insight.get("severity") == "HIGH")
    main_issue = ranked[0]["type"] if ranked else None
    worst_sector = None
    loss_by_sector: Dict[int, float] = {}
    for sector in (1, 2, 3):
        loss_by_sector[sector] = sum(
            max(0.0, _safe_float(segment.get("estimatedDeltaSeconds")) or 0.0)
            for segment in segments
            if isinstance(segment, Mapping) and _sector(segment.get("sector")) == sector
        )
    if any(value > 0 for value in loss_by_sector.values()):
        worst_sector = max(loss_by_sector, key=lambda sector: loss_by_sector[sector])

    comparison_debug = comparison.get("debug") if isinstance(comparison.get("debug"), Mapping) else {}
    lap_selection = racing_line_payload.get("debug", {}).get("lapSelection") if isinstance(racing_line_payload.get("debug"), Mapping) else {}
    insufficient_segments = sum(
        1
        for segment in segments
        if isinstance(segment, Mapping)
        and (
            str(segment.get("mainIssue") or "") == "INSUFFICIENT_DATA"
            or _confidence(segment, _issue_from_segment(segment)) == "INSUFFICIENT_DATA"
        )
    )

    return {
        "status": "READY",
        "track": racing_line_payload.get("track") or racing_line.get("track"),
        "generatedAt": _now_iso(),
        "referenceLapNumber": racing_line.get("referenceLapNumber"),
        "currentLapNumber": lap_selection.get("currentLap") if isinstance(lap_selection, Mapping) else None,
        "microSectorCount": int(racing_line.get("microSectorCount") or micro_sectors),
        "summary": {
            "mainIssue": main_issue,
            "worstSector": worst_sector,
            "estimatedTotalLossSeconds": _round_or_none(total_loss, 4),
            "totalInsights": len(ranked),
            "highSeverityCount": high_severity_count,
        },
        "topInsights": ranked,
        "sectorInsights": sector_insights,
        "debug": {
            "racingLineStatus": str(racing_line_payload.get("status") or "UNKNOWN"),
            "comparisonSegments": len(segments),
            "validSegments": int(comparison_debug.get("validComparisonSegments") or 0),
            "rejectedSegments": int(comparison_debug.get("rejectedComparisonSegments") or 0),
            "insufficientDataSegments": insufficient_segments,
            "generatedInsights": len(ranked),
            "performanceMode": performance_mode,
        },
    }
