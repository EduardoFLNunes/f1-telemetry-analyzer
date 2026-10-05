"""Achatamento de uma amostra gravada para colunas planas.

O formato do disco tem duas camadas: um envelope (`type`, `timestamp`, `track`,
`sessionTime`, `sample`) e, dentro de `sample`, um bloco `carPhysics` com a
fisica agrupada por assunto (`motion`, `controls`, `tyres`, `environment`...).

Os pedais, o volante, a marcha e o RPM estao em lugares diferentes conforme a
versao do gravador -- no topo da amostra, em `carPhysics.controls`, ou nos dois
(ver `core.telemetry.channels`). Ler so um dos lugares devolve `None` para as
outras sessoes sem erro nenhum: a versao anterior deste modulo lia so
`carPhysics.controls`, e as sessoes de maio e junho caiam no gate de canais
ausentes com os pedais gravados no topo. A regra agora e a mesma do runtime.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Mapping, Optional

from core.projection.lateral_offset import to_left_positive
from core.telemetry.channels import ai_controlled, driver_inputs


def number(value: Any) -> Optional[float]:
    """Float finito, ou None. `None` vira None e nao 0.0 -- a diferenca entre
    'o jogo nao informou' e 'o valor e zero' e a diferenca entre uma lacuna e
    uma volta que comecou parada."""
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _seconds(value: Any) -> Optional[float]:
    """Tempo em segundos, venha ele em segundos ou milissegundos.

    O gravador escreve `lap_time` em segundos e `timestamp` em milissegundos
    desde a epoca; o envelope usa segundos. O corte em 10.000 separa os dois
    sem ambiguidade: nenhuma volta dura 10.000 s e nenhum timestamp de epoca em
    segundos e menor que isso.
    """
    result = number(value)
    if result is None:
        return None
    return result / 1000.0 if result > 10_000.0 else result


def _epoch_seconds(value: Any) -> Optional[float]:
    result = number(value)
    if result is None:
        return None
    return result / 1000.0 if result > 100_000_000_000.0 else result


def _first(mapping: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in mapping and mapping[key] is not None:
            return mapping[key]
    return None


def _mean(values: Any) -> Optional[float]:
    if not isinstance(values, (list, tuple)) or not values:
        return None
    numbers = [n for n in (number(v) for v in values) if n is not None]
    return sum(numbers) / len(numbers) if numbers else None


# Pedido 18 (ADR 0017, M0): uma coluna por roda, na ordem do jogo.
WHEELS = ("fl", "fr", "rl", "rr")


def _wheel(values: Any, index: int) -> Optional[float]:
    if not isinstance(values, (list, tuple)) or len(values) <= index:
        return None
    return number(values[index])


def physical_channels(physics: Mapping[str, Any], controls: Mapping[str, Any]) -> Dict[str, Any]:
    """Os canais fisicos da M0: por roda, o volante bruto e o movimento no referencial do carro.

    Gravacao que nao tem o campo da None, e a coluna fica vazia na volta.
    """
    def block(name: str) -> Mapping[str, Any]:
        value = physics.get(name)
        return value if isinstance(value, Mapping) else {}

    tyres, brakes, motion = block("tyres"), block("brakes"), block("motion")
    local = motion.get("localVelocity") if isinstance(motion.get("localVelocity"), Mapping) else {}
    angular = motion.get("localAngularVelocity") if isinstance(motion.get("localAngularVelocity"), Mapping) else {}
    row: Dict[str, Any] = {}
    for prefix, source in (("tyre_core_temp", tyres.get("tyreCoreTemperature")),
                           ("wheel_load", tyres.get("wheelLoad")),
                           ("wheel_slip", tyres.get("wheelSlip")),
                           ("tyre_pressure", tyres.get("tyrePressure")),
                           ("brake_temp", brakes.get("brakeTemp"))):
        for index, wheel in enumerate(WHEELS):
            row[f"{prefix}_{wheel}"] = _wheel(source, index)
    # O volante como foi gravado: a limpeza corta `steering` em +-1,5, esta nao.
    row["steer_angle"] = controls.get("steering")
    row["yaw_rate"] = number(angular.get("y"))
    row["velocity_long"] = number(local.get("z"))
    row["velocity_lat"] = number(local.get("x"))
    return row


def flatten(envelope: Mapping[str, Any]) -> Dict[str, Any]:
    """Uma linha do `player.jsonl` -> um dicionario plano de colunas."""
    sample = envelope.get("sample")
    if not isinstance(sample, Mapping):
        sample = envelope

    physics = sample.get("carPhysics") if isinstance(sample.get("carPhysics"), Mapping) else {}
    motion = physics.get("motion") if isinstance(physics.get("motion"), Mapping) else {}
    controls = driver_inputs(sample)
    tyres = physics.get("tyres") if isinstance(physics.get("tyres"), Mapping) else {}
    state = physics.get("carState") if isinstance(physics.get("carState"), Mapping) else {}
    ambient = physics.get("environment") if isinstance(physics.get("environment"), Mapping) else {}

    # A aceleracao vem em dois lugares com nomes diferentes para os mesmos eixos:
    # `carPhysics.motion.accG` (lateral/longitudinal/vertical) e `accel_g`
    # (x/y/z, onde x e lateral e z e longitudinal).
    acc = motion.get("accG") if isinstance(motion.get("accG"), Mapping) else {}
    legacy_acc = sample.get("accel_g") if isinstance(sample.get("accel_g"), Mapping) else {}

    speed_kmh = number(_first(sample, "speedKmh")) or number(motion.get("speedKmh"))
    if speed_kmh is None:
        speed_ms = number(sample.get("speed"))
        speed_kmh = speed_ms * 3.6 if speed_ms is not None else None

    row: Dict[str, Any] = {
        "timestamp_s": _epoch_seconds(_first(sample, "timestamp") or envelope.get("timestamp")),
        "session_time_s": number(_first(sample, "sessionTime") or envelope.get("sessionTime")),
        "lap_number": number(_first(sample, "lap", "lap_number")),
        "lap_time_s": _seconds(_first(sample, "lap_time", "lapTime", "currentLapTime")),
        # Posicao no world X/Z do jogo. `sample.z` existe mas e o -Z do mapa da
        # interface, nao a coordenada do mundo; `world_z` e a boa.
        "x": number(_first(sample, "world_x")),
        "y": number(_first(sample, "world_y")),
        "z": number(_first(sample, "world_z")),
        "heading": number(sample.get("heading")),
        "speed_kmh": speed_kmh,
        "throttle": controls["throttle"],
        "brake": controls["brake"],
        "clutch": controls["clutch"],
        "steering": controls["steering"],
        "gear": controls["gear"],
        "rpm": controls["rpm"],
        "lateral_g": number(acc.get("lateral")) if acc else number(legacy_acc.get("x")),
        "longitudinal_g": number(acc.get("longitudinal")) if acc else number(legacy_acc.get("z")),
        "vertical_g": number(acc.get("vertical")) if acc else number(legacy_acc.get("y")),
        # Contexto que muda o que uma volta significa: pneu, combustivel e piso.
        "wheel_slip": _mean(tyres.get("wheelSlip")),
        "tyre_core_temp": _mean(tyres.get("tyreCoreTemperature")),
        "tyre_wear": _mean(tyres.get("tyreWear")),
        "grip_index": _mean(tyres.get("estimatedGripIndex")),
        "fuel": number(state.get("fuel")),
        "surface_grip": number(ambient.get("surfaceGrip")),
        "road_temp": number(ambient.get("roadTemp")),
        "off_track": bool(ambient.get("offTrack")) if ambient else None,
        "tyres_out": number(ambient.get("tyresOut")),
        # Quem pilotava (ADR 0014): True/False quando o gravador registrou,
        # None nas gravacoes anteriores ao campo.
        "ai_controlled": ai_controlled(sample),
        # O `s` do gravador entra so como conferencia. O pipeline recalcula o
        # seu proprio: 6 sessoes gravaram `null` aqui, e as que gravaram algo o
        # fizeram contra versoes diferentes da geometria.
        "s_recorded": number(_first(sample, "distanceAlongTrack")),
        # O runtime grava o offset positivo a direita; aqui ele ja entra na
        # convencao do `ml` (positivo a esquerda), para poder ser comparado com
        # `lateral` sem ninguem lembrar de trocar o sinal.
        "lateral_recorded": to_left_positive(
            number(_first(sample, "lateralOffset", "lateral_offset"))
        ),
    }
    row.update(physical_channels(physics, controls))
    return row


SAMPLE_COLUMNS = tuple(
    flatten({"sample": {}}).keys()
)
