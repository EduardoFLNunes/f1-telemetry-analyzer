from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .assisted_analysis_models import (
    PHASE_APEX,
    PHASE_BRAKING,
    PHASE_ENTRY,
    PHASE_EXIT,
    PHASE_STRAIGHT_AFTER,
    CornerComparison,
    CornerMetrics,
    DrivingError,
    TechniqueFinding,
    VehicleDynamicsProfile,
)
from .driving_knowledge_base import DrivingKnowledgeBase
from .driving_technique_analyzer import DrivingTechniqueAnalyzer
from .utils import clamp


ERROR_LABELS = {
    concept.code: concept.label for concept in DrivingKnowledgeBase().all()
}


class DrivingErrorClassifier:
    def __init__(self, knowledge_base: Optional[DrivingKnowledgeBase] = None):
        self.knowledge_base = knowledge_base or DrivingKnowledgeBase()
        self.technique_analyzer = DrivingTechniqueAnalyzer()

    def classify(
        self,
        player: CornerMetrics,
        reference: CornerMetrics,
        comparison: CornerComparison,
        dynamics: Optional[VehicleDynamicsProfile] = None,
        reference_dynamics: Optional[VehicleDynamicsProfile] = None,
    ) -> List[DrivingError]:
        raw: List[Tuple[str, str, float, str, Dict[str, Any], Optional[str]]] = []
        self._append_reference_rules(raw, player, reference, comparison)

        technique_findings = self.technique_analyzer.analyze(
            player,
            reference,
            comparison,
            dynamics,
            reference_dynamics,
        )
        errors = [
            self._error_from_raw(code, phase, severity, description, evidence, behavior)
            for code, phase, severity, description, evidence, behavior in raw
            if severity >= 0.18
        ]
        errors.extend(self._error_from_finding(finding) for finding in technique_findings)
        errors = self._dedupe(errors)
        if not errors:
            return []

        severity_sum = sum(max(0.01, error.severity) for error in errors)
        total_gain = comparison.estimated_gain()
        for error in errors:
            error.estimated_gain_s = total_gain * max(0.01, error.severity) / severity_sum if total_gain > 0 else 0.0
            self.knowledge_base.enrich_error(error)
        return sorted(errors, key=lambda error: error.severity, reverse=True)

    def _append_reference_rules(
        self,
        raw: List[Tuple[str, str, float, str, Dict[str, Any], Optional[str]]],
        player: CornerMetrics,
        reference: CornerMetrics,
        comparison: CornerComparison,
    ):
        brake_delta = comparison.brake_start_delta_m
        if brake_delta is not None:
            if brake_delta < -12.0:
                raw.append((
                    "EARLY_BRAKING",
                    PHASE_BRAKING,
                    self._severity(abs(brake_delta), start=12.0, full=55.0),
                    f"Ponto de freio {abs(brake_delta):.0f} m antes da referencia.",
                    self._evidence("brakeStartDeltaM", brake_delta, player.brake_start_s, reference.brake_start_s),
                    "Frenagem comeca antes da zona otima e alonga a fase lenta.",
                ))
            elif brake_delta > 12.0:
                raw.append((
                    "LATE_BRAKING",
                    PHASE_BRAKING,
                    self._severity(abs(brake_delta), start=12.0, full=55.0),
                    f"Ponto de freio {brake_delta:.0f} m depois da referencia.",
                    self._evidence("brakeStartDeltaM", brake_delta, player.brake_start_s, reference.brake_start_s),
                    "Frenagem entra tarde e deixa pouca margem para rotacao.",
                ))

        entry_speed_delta = comparison.entry_speed_delta_kmh
        if entry_speed_delta is not None and entry_speed_delta > 7.0:
            late_brake_bonus = 0.15 if brake_delta is not None and brake_delta > 6.0 else 0.0
            raw.append((
                "ENTRY_OVERSPEED",
                PHASE_ENTRY,
                clamp(self._severity(entry_speed_delta, start=7.0, full=24.0) + late_brake_bonus, 0.0, 1.0),
                f"Entrada {entry_speed_delta:.1f} km/h acima da referencia.",
                self._evidence("entrySpeedDeltaKmh", entry_speed_delta, player.entry_speed_kmh, reference.entry_speed_kmh),
                "Excesso de velocidade na entrada aumenta raio e atrasa aplicacao de acelerador.",
            ))

        apex_delta = comparison.apex_delta_m
        if apex_delta is not None:
            if apex_delta < -10.0:
                raw.append((
                    "EARLY_APEX",
                    PHASE_APEX,
                    self._severity(abs(apex_delta), start=10.0, full=42.0),
                    f"Apex {abs(apex_delta):.0f} m antes da referencia.",
                    self._evidence("apexDeltaM", apex_delta, player.apex_s, reference.apex_s),
                    "A linha fecha cedo e compromete o raio de saida.",
                ))
            elif apex_delta > 10.0:
                raw.append((
                    "LATE_APEX",
                    PHASE_APEX,
                    self._severity(abs(apex_delta), start=10.0, full=42.0),
                    f"Apex {apex_delta:.0f} m depois da referencia.",
                    self._evidence("apexDeltaM", apex_delta, player.apex_s, reference.apex_s),
                    "Rotacao chega tarde e empurra o acelerador para depois.",
                ))

        throttle_delta = comparison.throttle_pickup_delta_m
        if throttle_delta is not None:
            if throttle_delta > 12.0:
                raw.append((
                    "LATE_THROTTLE",
                    PHASE_EXIT,
                    self._severity(throttle_delta, start=12.0, full=55.0),
                    f"Retomada de acelerador {throttle_delta:.0f} m depois da referencia.",
                    self._evidence("throttlePickupDeltaM", throttle_delta, player.throttle_pickup_s, reference.throttle_pickup_s),
                    "Fase neutra longa na saida subutiliza aderencia longitudinal.",
                ))
            elif throttle_delta < -10.0 and self._supports_early_throttle_issue(comparison):
                raw.append((
                    "EARLY_THROTTLE",
                    PHASE_EXIT,
                    self._severity(abs(throttle_delta), start=10.0, full=42.0),
                    f"Acelerador aplicado {abs(throttle_delta):.0f} m antes da referencia, com perda na saida.",
                    self._evidence("throttlePickupDeltaM", throttle_delta, player.throttle_pickup_s, reference.throttle_pickup_s),
                    "Torque chega antes do carro estar apontado para a saida.",
                ))

        coasting_delta = comparison.coasting_delta_m
        if coasting_delta is not None and coasting_delta > 14.0:
            raw.append((
                "EXCESS_COASTING",
                PHASE_BRAKING,
                self._severity(coasting_delta, start=14.0, full=75.0),
                f"Coasting {coasting_delta:.0f} m maior que a referencia.",
                self._evidence("coastingDeltaM", coasting_delta, player.coasting_distance_m, reference.coasting_distance_m),
                "Zona sem freio e sem acelerador deixa aderencia disponivel sem uso claro.",
            ))

        exit_speed_delta = comparison.exit_speed_delta_kmh
        if (
            exit_speed_delta is not None
            and exit_speed_delta < -5.0
            and comparison.segment_time_delta_s is not None
            and comparison.segment_time_delta_s > 0.04
        ):
            late_power_bonus = 0.18 if (
                comparison.throttle_pickup_delta_m is not None and comparison.throttle_pickup_delta_m > 8.0
            ) else 0.0
            raw.append((
                "POOR_EXIT",
                PHASE_STRAIGHT_AFTER,
                clamp(self._severity(abs(exit_speed_delta), start=5.0, full=24.0) + late_power_bonus, 0.0, 1.0),
                f"Saida {abs(exit_speed_delta):.1f} km/h abaixo da referencia e perda se estende pela reta.",
                {
                    "exitSpeedDeltaKmh": exit_speed_delta,
                    "segmentTimeDeltaS": comparison.segment_time_delta_s,
                    "throttlePickupDeltaM": comparison.throttle_pickup_delta_m,
                    "fullThrottleDeltaM": comparison.full_throttle_delta_m,
                    "playerExitSpeedKmh": player.exit_speed_kmh,
                    "referenceExitSpeedKmh": reference.exit_speed_kmh,
                },
                "Menos velocidade util ao final da curva compromete a reta posterior.",
            ))

        line_delta = comparison.line_deviation_delta_m
        phase, phase_delta = self._worst_line_phase(comparison)
        if (line_delta is not None and line_delta > 0.55) or (phase_delta is not None and phase_delta > 0.85):
            metric_delta = phase_delta if phase_delta is not None and phase_delta > 0.85 else line_delta
            raw.append((
                "TRAJECTORY_DEVIATION",
                phase or PHASE_APEX,
                self._severity(metric_delta or 0.0, start=0.55, full=2.4),
                f"Linha {metric_delta or 0.0:.2f} m mais distante da referencia.",
                self._evidence(
                    "lineDeviationDeltaM",
                    metric_delta,
                    player.phase_line_deviation_m.get(phase or PHASE_APEX),
                    reference.phase_line_deviation_m.get(phase or PHASE_APEX),
                ),
                "Trajetoria difere da referencia na fase de maior perda.",
            ))

    def _error_from_raw(
        self,
        code: str,
        phase: str,
        severity: float,
        description: str,
        evidence: Dict[str, Any],
        physical_behavior: Optional[str],
    ) -> DrivingError:
        error = DrivingError(
            code=code,
            label=ERROR_LABELS.get(code, code),
            phase=phase,
            severity=severity,
            estimated_gain_s=0.0,
            description=description,
            evidence=evidence,
            physical_behavior=physical_behavior,
        )
        return self.knowledge_base.enrich_error(error)

    def _error_from_finding(self, finding: TechniqueFinding) -> DrivingError:
        concept = self.knowledge_base.get(finding.code)
        label = concept.label if concept else ERROR_LABELS.get(finding.code, finding.code)
        description = finding.physical_behavior
        error = DrivingError(
            code=finding.code,
            label=label,
            phase=finding.phase,
            severity=finding.severity,
            estimated_gain_s=0.0,
            description=description,
            evidence=finding.evidence,
            physical_behavior=finding.physical_behavior,
        )
        return self.knowledge_base.enrich_error(error)

    @staticmethod
    def _dedupe(errors: List[DrivingError]) -> List[DrivingError]:
        by_code: Dict[str, DrivingError] = {}
        for error in errors:
            current = by_code.get(error.code)
            if current is None or error.severity > current.severity:
                by_code[error.code] = error
        return list(by_code.values())

    @staticmethod
    def _severity(value: float, start: float, full: float) -> float:
        if full <= start:
            return 0.0
        return clamp((float(value) - start) / (full - start), 0.0, 1.0)

    @staticmethod
    def _evidence(metric: str, delta: Optional[float], player: Optional[float], reference: Optional[float]) -> Dict[str, Any]:
        return {
            "metric": metric,
            "player": player,
            "reference": reference,
            "delta": delta,
        }

    @staticmethod
    def _supports_early_throttle_issue(comparison: CornerComparison) -> bool:
        exit_speed_loss = comparison.exit_speed_delta_kmh is not None and comparison.exit_speed_delta_kmh < -3.0
        line_loss = comparison.line_deviation_delta_m is not None and comparison.line_deviation_delta_m > 0.35
        time_loss = comparison.segment_time_delta_s is not None and comparison.segment_time_delta_s > 0.04
        return exit_speed_loss or line_loss or time_loss

    @staticmethod
    def _worst_line_phase(comparison: CornerComparison) -> Tuple[Optional[str], Optional[float]]:
        values = [
            (phase, value)
            for phase, value in comparison.phase_line_deviation_delta_m.items()
            if value is not None
        ]
        if not values:
            return None, None
        return max(values, key=lambda item: item[1])
