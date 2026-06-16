from __future__ import annotations

from typing import Any, Dict, List

from .assisted_analysis_models import DrivingError


PHASE_LABELS = {
    "entry": "entrada",
    "braking_zone": "zona de frenagem",
    "apex": "apex",
    "exit": "saida",
    "straight_after": "reta posterior",
}


class FeedbackGenerator:
    def corner_feedback(self, corner_name: str, errors: List[DrivingError], loss_s: float) -> str:
        if not errors:
            if loss_s > 0.04:
                return f"{corner_name}: ha perda de {loss_s:.3f}s, mas sem assinatura tecnica forte nos canais disponiveis."
            return f"{corner_name}: execucao proxima da referencia."

        primary = errors[0]
        phase = PHASE_LABELS.get(primary.phase, primary.phase)
        gain = sum(error.estimated_gain_s for error in errors)
        concept = f" Conceito: {primary.concept}." if primary.concept else ""
        behavior = f" Comportamento observado: {primary.physical_behavior}." if primary.physical_behavior else ""
        advice = primary.feedback or primary.description
        suffix = f" Ganho estimado: {gain:.3f}s." if gain > 0 else ""
        return f"{corner_name}: {primary.label} na {phase}.{concept}{behavior} {advice}{suffix}"

    def headline(self, top_losses: List[Dict[str, Any]], total_gain: float) -> str:
        if not top_losses:
            return "Volta sem perdas tecnicas relevantes contra a referencia disponivel."
        primary = top_losses[0]
        corner = primary.get("name") or f"T{primary.get('cornerId')}"
        error = primary.get("primaryError") or "perda tecnica"
        concept = primary.get("concept")
        concept_text = f" ({concept})" if concept else ""
        return f"Maior oportunidade em {corner}: {error}{concept_text}. Ganho total estimado {total_gain:.3f}s."

    def data_quality(self, player_samples: int, reference_samples: int, optional_channels: Dict[str, bool], warnings: List[str]) -> Dict[str, Any]:
        channel_score = sum(1 for present in optional_channels.values() if present) / max(len(optional_channels), 1)
        sample_score = min(1.0, min(player_samples, reference_samples) / 220.0)
        warning_penalty = min(0.35, len(warnings) * 0.08)
        confidence = max(0.2, min(1.0, 0.45 + sample_score * 0.35 + channel_score * 0.20 - warning_penalty))
        return {
            "confidence": confidence,
            "playerSampleCount": player_samples,
            "referenceSampleCount": reference_samples,
            "optionalChannels": optional_channels,
            "warnings": warnings,
        }
