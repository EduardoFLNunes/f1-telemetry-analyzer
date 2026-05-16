"""
Motorsport Foundation Model
Transformer-based latent representation learner for driver behavior.
"""
import torch
import torch.nn as nn
import numpy as np
from typing import Dict, Any, Optional

class TelemetryTransformer(nn.Module):
    """
    Core Transformer architecture for learning racing representations.
    Inputs are temporal sequences of normalized telemetry.
    """
    def __init__(self, input_dim: int, d_model: int = 128, nhead: int = 8, num_layers: int = 4):
        super().__init__()
        self.embedding = nn.Linear(input_dim, d_model)
        self.pos_encoder = nn.Parameter(torch.zeros(1, 1024, d_model)) # Max seq length
        
        encoder_layers = nn.TransformerEncoderLayer(d_model, nhead, dim_feedforward=512, batch_first=True)
        self.transformer = nn.TransformerEncoder(encoder_layers, num_layers)
        
        # Output heads
        self.driver_style_head = nn.Linear(d_model, 64) # Style embedding
        self.trajectory_head = nn.Linear(d_model, 2)    # Predicted next frame [L, speed]

    def forward(self, x: torch.Tensor) -> Dict[str, torch.Tensor]:
        # x shape: (batch, seq_len, input_dim)
        seq_len = x.size(1)
        x = self.embedding(x)
        x = x + self.pos_encoder[:, :seq_len, :]
        
        latent = self.transformer(x)
        
        # Pooling for global driver style (mean over time)
        global_latent = torch.mean(latent, dim=1)
        style_embedding = self.driver_style_head(global_latent)
        
        # Local prediction for last frame in sequence
        next_frame_pred = self.trajectory_head(latent[:, -1, :])
        
        return {
            "style_embedding": style_embedding,
            "next_frame_prediction": next_frame_pred,
            "latent": latent
        }

class MotorsportFoundationModel:
    """
    Orchestrator for loading and running the foundation model.
    """
    def __init__(self, checkpoint_path: Optional[str] = None):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = TelemetryTransformer(input_dim=10).to(self.device)
        self.model.eval()
        
        if checkpoint_path:
            self.model.load_state_dict(torch.load(checkpoint_path, map_location=self.device))

    @torch.no_grad()
    def encode_driver_style(self, sequence: np.ndarray) -> np.ndarray:
        """Generates a style embedding for a given telemetry sequence."""
        x = torch.from_numpy(sequence).float().to(self.device)
        if x.dim() == 2: x = x.unsqueeze(0) # add batch dim
        
        output = self.model(x)
        return output["style_embedding"].cpu().numpy()

    @torch.no_grad()
    def predict_next_state(self, sequence: np.ndarray) -> np.ndarray:
        """Predicts the car's state in the next temporal step."""
        x = torch.from_numpy(sequence).float().to(self.device)
        if x.dim() == 2: x = x.unsqueeze(0)
        
        output = self.model(x)
        return output["next_frame_prediction"].cpu().numpy()
