"""
Driver Behavior Embedding Network
Learns latent driver characteristics and style profiles.
"""
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
import logging

logger = logging.getLogger(__name__)

class DriverBehaviorModel:
    """
    Quantifies driver style into behavioral embeddings.
    Allows for similarity search and style clustering.
    """
    def __init__(self, embedding_dim: int = 16):
        self.embedding_dim = embedding_dim
        self.scaler = StandardScaler()
        self.pca = PCA(n_components=embedding_dim)
        self.is_trained = False

    def generate_behavioral_fingerprint(self, lap_features: Dict[str, float]) -> np.ndarray:
        """
        Converts high-level metrics into a compact behavioral vector.
        """
        # Feature list from Phase 3:
        # ["braking_aggressiveness", "throttle_smoothness", "trail_braking_score", 
        #  "traction_efficiency", "steering_stability", "racing_line_offset_avg"]
        
        vals = np.array(list(lap_features.values())).reshape(1, -1)
        
        if not self.is_trained:
            # Fallback: just return normalized raw features
            return vals / (np.linalg.norm(vals) + 1e-6)
            
        normalized = self.scaler.transform(vals)
        embedding = self.pca.transform(normalized)
        return embedding

    def compute_similarity(self, v1: np.ndarray, v2: np.ndarray) -> float:
        """Cosine similarity between two behavioral embeddings."""
        dot = np.dot(v1.flatten(), v2.flatten())
        norm = np.linalg.norm(v1) * np.linalg.norm(v2)
        return float(dot / (norm + 1e-8))

    def classify_style(self, embedding: np.ndarray) -> List[str]:
        """Categorizes driver based on embedding position."""
        # Simple quadrant-based classification for now
        # In production, this would use a K-Means cluster centroid lookup
        labels = []
        # Placeholder logic
        if embedding[0][0] > 0.5: labels.append("Aggressive")
        else: labels.append("Smooth")
        
        return labels
