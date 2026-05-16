"""
Voice Engineer System
Provides real-time spoken coaching and alerts using TTS.
"""
import pyttsx3
import threading
import queue
import logging
from typing import Dict, Any, Optional
import asyncio
from core.telemetry_events import event_bus

logger = logging.getLogger(__name__)

class VoiceEngineer:
    """
    Manages an asynchronous speech queue for real-time race engineering feedback.
    """
    def __init__(self, use_local_tts: bool = True):
        self.speech_queue = queue.Queue()
        self.use_local_tts = use_local_tts
        self._stop_event = threading.Event()
        self._thread = None
        
        if self.use_local_tts:
            self._thread = threading.Thread(target=self._speech_worker, daemon=True)
            self._thread.start()
            
        # Subscribe to speech events
        event_bus.subscribe("engineer_speech", self.on_speech_event)

    async def on_speech_event(self, data: Dict[str, Any]):
        """Adds a message to the speech queue."""
        message = data.get("message", "")
        priority = data.get("priority", "normal")
        
        if message:
            # If high priority, we could theoretically clear the queue
            # but for now, we just append
            self.speech_queue.put(message)
            logger.debug(f"Queued speech: {message}")

    def _speech_worker(self):
        """Background thread to process speech synchronously without blocking the event loop."""
        # Initialize engine in this thread
        try:
            engine = pyttsx3.init()
            engine.setProperty('rate', 175) # Speed of speech
            engine.setProperty('volume', 0.9)
            
            # Select a neutral/professional voice if possible
            voices = engine.getProperty('voices')
            if len(voices) > 1:
                engine.setProperty('voice', voices[1].id) # Usually a female voice, often clearer

            logger.info("Voice Engineer speech worker active")
            
            while not self._stop_event.is_set():
                try:
                    # Wait for a message with a timeout to allow checking stop_event
                    message = self.speech_queue.get(timeout=1.0)
                    
                    logger.info(f"Speaking: {message}")
                    engine.say(message)
                    engine.runAndWait()
                    
                    self.speech_queue.task_done()
                except queue.Empty:
                    continue
                except Exception as e:
                    logger.error(f"Speech engine error: {e}")
                    # Re-init engine if it crashes
                    time.sleep(2)
                    engine = pyttsx3.init()
        except Exception as e:
            logger.error(f"Failed to initialize local TTS: {e}")

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)
        logger.info("Voice Engineer stopped")
