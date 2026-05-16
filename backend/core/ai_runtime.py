"""
Unified AI Inference Runtime for F1 Telemetry Analyzer
Manages model loading, device management, and high-performance inference using ONNX Runtime.
"""
import onnxruntime as ort
import numpy as np
import logging
import time
from pathlib import Path
from typing import Dict, Any, Optional, List, Union

logger = logging.getLogger(__name__)

class AIRuntime:
    """
    Orchestrates ML inference for real-time telemetry streaming.
    Supports ONNX models and provides async-safe execution.
    """
    def __init__(self, models_dir: str = "models"):
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)
        
        # Model cache: {model_id: InferenceSession}
        self.sessions: Dict[str, ort.InferenceSession] = {}
        
        # Device management
        self.providers = ort.get_available_providers()
        logger.info(f"Available ONNX providers: {self.providers}")
        
        # Target 'CPUExecutionProvider' as default for stability, 
        # 'CUDAExecutionProvider' if available and requested.
        self.default_providers = ['CPUExecutionProvider']
        if 'CUDAExecutionProvider' in self.providers:
            self.default_providers.insert(0, 'CUDAExecutionProvider')

    def load_model(self, model_id: str, filename: str):
        """Loads an ONNX model into the runtime."""
        model_path = self.models_dir / filename
        if not model_path.exists():
            logger.warning(f"Model file not found: {model_path}")
            return False
            
        try:
            session = ort.InferenceSession(str(model_path), providers=self.default_providers)
            self.sessions[model_id] = session
            logger.info(f"Loaded AI Model: {model_id} from {filename}")
            return True
        except Exception as e:
            logger.error(f"Failed to load model {model_id}: {e}")
            return False

    def predict(self, model_id: str, inputs: Dict[str, np.ndarray]) -> Optional[Dict[str, np.ndarray]]:
        """
        Synchronous inference call. 
        Target latency: <10ms for small batch/sequence.
        """
        if model_id not in self.sessions:
            logger.error(f"Model {model_id} not loaded")
            return None
            
        session = self.sessions[model_id]
        start_t = time.perf_counter()
        
        try:
            # Map input dict to ONNX names
            # session.run(output_names, input_feed, run_options)
            outputs = session.run(None, inputs)
            
            # Map back to dict
            output_names = [out.name for out in session.get_outputs()]
            result = {name: outputs[i] for i, name in enumerate(output_names)}
            
            latency = (time.perf_counter() - start_t) * 1000
            if latency > 20:
                logger.warning(f"AI Inference Lag: {model_id} took {latency:.2f}ms")
                
            return result
        except Exception as e:
            logger.error(f"Inference error for {model_id}: {e}")
            return None

    def unload_model(self, model_id: str):
        if model_id in self.sessions:
            del self.sessions[model_id]
            logger.info(f"Unloaded model: {model_id}")

    def get_model_info(self, model_id: str) -> Dict[str, Any]:
        if model_id not in self.sessions: return {}
        session = self.sessions[model_id]
        return {
            "inputs": [{"name": i.name, "shape": i.shape, "type": i.type} for i in session.get_inputs()],
            "outputs": [{"name": o.name, "shape": o.shape, "type": o.type} for o in session.get_outputs()]
        }

# Global runtime instance
ai_runtime = AIRuntime()
