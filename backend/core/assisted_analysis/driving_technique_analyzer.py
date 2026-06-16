from __future__ import annotations

from typing import Any, Dict, List, Optional

from .assisted_analysis_models import (
    PHASE_APEX,
    PHASE_BRAKING,
    PHASE_ENTRY,
    PHASE_EXIT,
    PHASE_STRAIGHT_AFTER,
    CornerComparison,
    CornerMetrics,
    PhaseDynamics,
    TechniqueFinding,
    VehicleDynamicsProfile,
)
from .utils import clamp


class DrivingTechniqueAnalyzer:
    def analyze(
        self,
        player: CornerMetrics,
        reference: CornerMetrics,
        comparison: CornerComparison,
        dynamics: Optional[VehicleDynamicsProfile],
        reference_dynamics: Optional[VehicleDynamicsProfile] = None,
    ) -> List[TechniqueFinding]:
        findings: List[TechniqueFinding] = []
        if not dynamics:
            return findings

        entry = self._phase(dynamics, PHASE_ENTRY)
        braking = self._phase(dynamics, PHASE_BRAKING)
        apex = self._phase(dynamics, PHASE_APEX)
        exit_phase = self._phase(dynamics, PHASE_EXIT)
        straight = self._phase(dynamics, PHASE_STRAIGHT_AFTER)
        ref_entry = self._phase(reference_dynamics, PHASE_ENTRY)
        ref_apex = self._phase(reference_dynamics, PHASE_APEX)
        ref_exit = self._phase(reference_dynamics, PHASE_EXIT)

        self._append_brake_technique(findings, player, reference, comparison, braking, apex)
        self._append_entry_technique(findings, comparison, entry, braking, ref_entry)
        self._append_mid_corner_technique(findings, comparison, apex, ref_apex)
        self._append_exit_technique(findings, comparison, exit_phase, straight, ref_exit)
        return [finding for finding in findings if finding.severity >= 0.18]

    def _append_brake_technique(
        self,
        findings: List[TechniqueFinding],
        player: CornerMetrics,
        reference: CornerMetrics,
        comparison: CornerComparison,
        braking: Optional[PhaseDynamics],
        apex: Optional[PhaseDynamics],
    ):
        release_delta = comparison.brake_release_delta_m
        if release_delta is not None and release_delta > 10.0:
            findings.append(self._finding(
                "BRAKE_HELD_TOO_LONG",
                PHASE_BRAKING,
                self._severity(release_delta, 10.0, 50.0),
                "Freio residual permanece ativo alem da referencia na entrada.",
                {
                    "brakeReleaseDeltaM": release_delta,
                    "playerBrakeReleaseS": player.brake_release_s,
                    "referenceBrakeReleaseS": reference.brake_release_s,
                    "minSpeedDeltaKmh": comparison.min_speed_delta_kmh,
                },
            ))

        if release_delta is not None and release_delta < -12.0 and self._low_rotation(apex):
            findings.append(self._finding(
                "EARLY_BRAKE_RELEASE",
                PHASE_BRAKING,
                self._severity(abs(release_delta), 12.0, 52.0),
                "Freio some cedo demais e o carro perde carga dianteira antes de rotacionar.",
                {
                    "brakeReleaseDeltaM": release_delta,
                    "apexMeanAbsYawRate": apex.mean_abs_yaw_rate if apex else None,
                    "minSpeedDeltaKmh": comparison.min_speed_delta_kmh,
                },
            ))

        release_rate = self._value(braking, "brake_release_rate")
        if release_rate is not None and release_rate > 2.2:
            stability = self._value(braking, "stability_score")
            findings.append(self._finding(
                "ABRUPT_BRAKE_RELEASE",
                PHASE_BRAKING,
                clamp(self._severity(release_rate, 2.2, 6.0) + (0.15 if stability is not None and stability < 0.72 else 0.0), 0.0, 1.0),
                "A pressao de freio cai em rampa muito curta, movimentando a plataforma do carro.",
                {
                    "brakeReleaseRate": release_rate,
                    "stabilityScore": stability,
                    "maxYawRate": self._value(braking, "max_yaw_rate"),
                },
            ))

        if self._value(apex, "brake_release_rate") is not None and self._value(apex, "brake_release_rate") > 1.0:
            steering = self._value(apex, "mean_abs_steering")
            friction = self._value(apex, "friction_usage_peak")
            if steering is not None and steering > 0.22:
                findings.append(self._finding(
                    "BRAKE_REAPPLIED_WITH_STEERING",
                    PHASE_APEX,
                    clamp(self._severity(steering, 0.22, 0.7) + self._severity(friction or 0.0, 1.0, 1.6) * 0.35, 0.0, 1.0),
                    "Ha freio reaparecendo quando o carro ainda esta com volante significativo.",
                    {
                        "apexBrakeReleaseRate": self._value(apex, "brake_release_rate"),
                        "meanAbsSteering": steering,
                        "frictionUsagePeak": friction,
                    },
                ))

    def _append_entry_technique(
        self,
        findings: List[TechniqueFinding],
        comparison: CornerComparison,
        entry: Optional[PhaseDynamics],
        braking: Optional[PhaseDynamics],
        ref_entry: Optional[PhaseDynamics],
    ):
        if comparison.entry_speed_delta_kmh is not None and comparison.entry_speed_delta_kmh < -6.0:
            findings.append(self._finding(
                "SLOW_ENTRY",
                PHASE_ENTRY,
                self._severity(abs(comparison.entry_speed_delta_kmh), 6.0, 22.0),
                "Velocidade de entrada abaixo da referencia com perda de tempo local.",
                {
                    "entrySpeedDeltaKmh": comparison.entry_speed_delta_kmh,
                    "segmentTimeDeltaS": comparison.segment_time_delta_s,
                },
            ))

        steering_rate = self._value(entry, "max_steering_rate") or self._value(braking, "max_steering_rate")
        yaw_rate = self._value(entry, "max_yaw_rate") or self._value(braking, "max_yaw_rate")
        ref_steering_rate = self._value(ref_entry, "max_steering_rate")
        line = self._value(entry, "reference_line_deviation_m")
        if steering_rate is not None and steering_rate > max(3.2, (ref_steering_rate or 0.0) * 1.45):
            findings.append(self._finding(
                "AGGRESSIVE_ENTRY",
                PHASE_ENTRY,
                clamp(self._severity(steering_rate, 3.2, 8.0) + self._severity(line or 0.0, 0.8, 3.5) * 0.2, 0.0, 1.0),
                "Volante aplicado rapido demais na entrada, antes do carro estabilizar carga lateral.",
                {
                    "maxSteeringRate": steering_rate,
                    "referenceMaxSteeringRate": ref_steering_rate,
                    "maxYawRate": yaw_rate,
                    "referenceLineDeviationM": line,
                },
            ))

        steering = self._value(braking, "mean_abs_steering") or self._value(entry, "mean_abs_steering")
        mean_yaw = self._value(braking, "mean_abs_yaw_rate") or self._value(entry, "mean_abs_yaw_rate")
        if steering is not None and steering > 0.28 and (mean_yaw is None or mean_yaw < 0.42) and (line or 0.0) > 0.55:
            findings.append(self._finding(
                "ENTRY_UNDERSTEER",
                PHASE_ENTRY,
                clamp(self._severity(steering, 0.28, 0.8) + self._severity(line or 0.0, 0.55, 2.5) * 0.35, 0.0, 1.0),
                "Volante alto com baixa resposta de yaw indica frente saturada na entrada.",
                {
                    "meanAbsSteering": steering,
                    "meanAbsYawRate": mean_yaw,
                    "referenceLineDeviationM": line,
                },
            ))

        stability = self._value(entry, "stability_score") or self._value(braking, "stability_score")
        if yaw_rate is not None and yaw_rate > 1.25 and stability is not None and stability < 0.72:
            findings.append(self._finding(
                "ENTRY_OVERSTEER",
                PHASE_ENTRY,
                clamp(self._severity(yaw_rate, 1.25, 2.4) + self._severity(1.0 - stability, 0.28, 0.7), 0.0, 1.0),
                "Yaw alto e estabilidade baixa sugerem traseira rotacionando demais na entrada.",
                {
                    "maxYawRate": yaw_rate,
                    "stabilityScore": stability,
                    "maxSteeringRate": steering_rate,
                },
            ))

    def _append_mid_corner_technique(
        self,
        findings: List[TechniqueFinding],
        comparison: CornerComparison,
        apex: Optional[PhaseDynamics],
        ref_apex: Optional[PhaseDynamics],
    ):
        steering = self._value(apex, "mean_abs_steering")
        yaw = self._value(apex, "mean_abs_yaw_rate")
        ref_yaw = self._value(ref_apex, "mean_abs_yaw_rate")
        line = self._value(apex, "reference_line_deviation_m")
        if steering is not None and steering > 0.30 and (yaw is None or yaw < 0.45) and (line or 0.0) > 0.55:
            findings.append(self._finding(
                "MID_CORNER_UNDERSTEER",
                PHASE_APEX,
                clamp(self._severity(steering, 0.30, 0.85) + self._severity(line or 0.0, 0.55, 2.5) * 0.35, 0.0, 1.0),
                "No miolo, o carro pede volante mas nao fecha o raio na mesma proporcao.",
                {
                    "meanAbsSteering": steering,
                    "meanAbsYawRate": yaw,
                    "referenceLineDeviationM": line,
                    "apexDeltaM": comparison.apex_delta_m,
                },
            ))

        if yaw is not None and ref_yaw is not None and yaw < ref_yaw * 0.72 and (comparison.throttle_pickup_delta_m or 0.0) > 8.0:
            findings.append(self._finding(
                "LOW_ROTATION",
                PHASE_APEX,
                clamp(self._severity(ref_yaw - yaw, 0.12, 0.55) + self._severity(comparison.throttle_pickup_delta_m or 0.0, 8.0, 45.0) * 0.3, 0.0, 1.0),
                "YawRate abaixo da referencia atrasa o momento de apontar e acelerar.",
                {
                    "meanAbsYawRate": yaw,
                    "referenceMeanAbsYawRate": ref_yaw,
                    "throttlePickupDeltaM": comparison.throttle_pickup_delta_m,
                },
            ))

    def _append_exit_technique(
        self,
        findings: List[TechniqueFinding],
        comparison: CornerComparison,
        exit_phase: Optional[PhaseDynamics],
        straight: Optional[PhaseDynamics],
        ref_exit: Optional[PhaseDynamics],
    ):
        throttle_rate = self._value(exit_phase, "throttle_application_rate")
        ref_throttle_rate = self._value(ref_exit, "throttle_application_rate")
        stability = self._value(exit_phase, "stability_score")
        yaw = self._value(exit_phase, "max_yaw_rate")
        steering_rate = self._value(exit_phase, "max_steering_rate")

        if throttle_rate is not None and throttle_rate > max(2.5, (ref_throttle_rate or 0.0) * 1.5):
            findings.append(self._finding(
                "AGGRESSIVE_THROTTLE",
                PHASE_EXIT,
                clamp(self._severity(throttle_rate, 2.5, 7.5) + (0.2 if stability is not None and stability < 0.75 else 0.0), 0.0, 1.0),
                "A rampa de acelerador e mais agressiva que a aderencia de saida parece permitir.",
                {
                    "throttleApplicationRate": throttle_rate,
                    "referenceThrottleApplicationRate": ref_throttle_rate,
                    "stabilityScore": stability,
                    "frictionUsagePeak": self._value(exit_phase, "friction_usage_peak"),
                },
            ))

        if yaw is not None and yaw > 1.15 and throttle_rate is not None and throttle_rate > 1.2 and stability is not None and stability < 0.74:
            findings.append(self._finding(
                "EXIT_OVERSTEER",
                PHASE_EXIT,
                clamp(self._severity(yaw, 1.15, 2.4) + self._severity(1.0 - stability, 0.26, 0.75), 0.0, 1.0),
                "A traseira fica ativa na retomada, com yaw alto durante aplicacao de torque.",
                {
                    "maxYawRate": yaw,
                    "throttleApplicationRate": throttle_rate,
                    "stabilityScore": stability,
                    "maxSteeringRate": steering_rate,
                },
            ))

        straight_stability = self._value(straight, "stability_score")
        if stability is not None and stability < 0.62 and steering_rate is not None and steering_rate > 2.5:
            findings.append(self._finding(
                "UNSTABLE_EXIT",
                PHASE_EXIT,
                self._severity(1.0 - stability, 0.38, 0.85),
                "Saida com baixa estabilidade e correcoes de volante antes da reta posterior.",
                {
                    "exitStabilityScore": stability,
                    "straightStabilityScore": straight_stability,
                    "maxSteeringRate": steering_rate,
                    "exitSpeedDeltaKmh": comparison.exit_speed_delta_kmh,
                },
            ))

        if steering_rate is not None and steering_rate > 3.8 and (stability is None or stability < 0.8):
            findings.append(self._finding(
                "EXCESS_STEERING_CORRECTION",
                PHASE_EXIT,
                clamp(self._severity(steering_rate, 3.8, 9.0) + (0.15 if stability is not None and stability < 0.7 else 0.0), 0.0, 1.0),
                "Correcoes de volante na saida indicam plataforma instavel ou torque aplicado cedo demais.",
                {
                    "maxSteeringRate": steering_rate,
                    "stabilityScore": stability,
                    "maxYawRate": yaw,
                },
            ))

    @staticmethod
    def _phase(profile: Optional[VehicleDynamicsProfile], phase: str) -> Optional[PhaseDynamics]:
        if not profile:
            return None
        return profile.phases.get(phase)

    @staticmethod
    def _value(phase: Optional[PhaseDynamics], name: str) -> Optional[float]:
        if phase is None:
            return None
        value = getattr(phase, name, None)
        return float(value) if value is not None else None

    @staticmethod
    def _low_rotation(apex: Optional[PhaseDynamics]) -> bool:
        yaw = DrivingTechniqueAnalyzer._value(apex, "mean_abs_yaw_rate")
        return yaw is not None and yaw < 0.38

    @staticmethod
    def _severity(value: float, start: float, full: float) -> float:
        if full <= start:
            return 0.0
        return clamp((float(value) - start) / (full - start), 0.0, 1.0)

    @staticmethod
    def _finding(code: str, phase: str, severity: float, physical_behavior: str, evidence: Dict[str, Any]) -> TechniqueFinding:
        return TechniqueFinding(
            code=code,
            phase=phase,
            severity=severity,
            evidence=evidence,
            physical_behavior=physical_behavior,
        )
