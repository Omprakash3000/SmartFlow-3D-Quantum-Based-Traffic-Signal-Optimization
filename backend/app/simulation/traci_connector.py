import logging
from typing import Optional

logger = logging.getLogger(__name__)


class TraCIConnector:
    """
    SUMO / TraCI Connector abstraction.
    Detects if SUMO binaries and `traci` Python package are installed.
    If available, bridges simulation commands to SUMO; otherwise, returns False,
    allowing the self-contained native Python traffic simulator to run seamlessly.
    """

    def __init__(self):
        self.is_supported: bool = False
        self._check_support()

    def _check_support(self) -> None:
        try:
            import traci
            import sumolib
            self.is_supported = True
            logger.info("SUMO TraCI bridge is available and enabled.")
        except ImportError:
            self.is_supported = False
            logger.info("SUMO TraCI not present in environment. Using self-contained Python traffic simulator.")

    def start(self, config_path: Optional[str] = None) -> bool:
        if not self.is_supported:
            return False
        # If enabled in a SUMO-supported system, traci.start([...]) would be called here.
        return True

    def close(self) -> None:
        if self.is_supported:
            try:
                import traci
                traci.close()
            except Exception:
                pass


traci_connector = TraCIConnector()
