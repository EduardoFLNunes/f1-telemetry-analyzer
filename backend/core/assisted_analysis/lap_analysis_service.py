from .service import AssistedAnalysisService


class LapAnalysisService(AssistedAnalysisService):
    """Canonical Phase 14 post-lap analysis service."""


__all__ = ["LapAnalysisService", "AssistedAnalysisService"]
