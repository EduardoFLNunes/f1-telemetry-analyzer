"""
Racing Line Prediction Model
Implements trajectory forecasting using sequence-to-sequence learning.
"""
import torch
import torch.nn as nn
from typing import Dict, Any, Optional
import numpy as np

class TrajectorySeq2Seq(nn.Module):
    """
    Encoder-Decoder architecture for racing line forecasting.
    Encodes current telemetry and decodes predicted future L-offsets.
    """
    def __init__(self, input_dim: int, hidden_dim: int = 256, output_len: int = 10):
        super().__init__()
        self.output_len = output_len
        self.encoder = nn.LSTM(input_dim, hidden_dim, batch_first=True)
        self.decoder = nn.Linear(hidden_dim, output_len) # Predict next N L-offsets

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x shape: (batch, seq_len, input_dim)
        _, (hn, _) = self.encoder(x)
        # hn shape: (num_layers, batch, hidden_dim)
        predictions = self.decoder(hn[-1])
        return predictions

class LinePredictionModel:
    """
    Wrapper for trajectory forecasting in the real-time pipeline.
    """
    def __init__(self):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = TrajectorySeq2Seq(input_dim=10).to(self.device)
        self.model.eval()

    @torch.no_grad()
    def predict_future_trajectory(self, sequence: np.ndarray) -> np.ndarray:
        """
        Inputs: (batch, seq_len, 10)
        Outputs: (batch, output_len) predicted L-offsets.
        """
        x = torch.from_numpy(sequence).float().to(self.device)
        if x.dim() == 2: x = x.unsqueeze(0)
        
        preds = self.model(x)
        return preds.cpu().numpy()
