import logging
import platform
import shutil
import subprocess
import time
import urllib.request

logger = logging.getLogger(__name__)

class OllamaManager:
    @staticmethod
    def ensure_service():
        """
        Try to start 'ollama serve' in the background if not already running.
        """
        try:
            urllib.request.urlopen("http://localhost:11434/api/tags", timeout=1)
            logger.info("[ollama] already running - skipping auto-start")
            return
        except Exception:
            pass

        if not shutil.which("ollama"):
            logger.warning("[ollama] binary not found on PATH - skipping auto-start")
            return

        try:
            kwargs = dict(stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if platform.system() == "Windows":
                kwargs["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
            else:
                kwargs["start_new_session"] = True

            subprocess.Popen(["ollama", "serve"], **kwargs)
            logger.info("[ollama] starting ollama serve in background...")

            for _ in range(16):
                time.sleep(0.5)
                try:
                    urllib.request.urlopen("http://localhost:11434/api/tags", timeout=1)
                    logger.info("[ollama] service is ready")
                    return
                except Exception:
                    pass
            logger.warning("[ollama] still starting - will be available shortly")
        except Exception as e:
            logger.error(f"[ollama] could not auto-start: {e}")
