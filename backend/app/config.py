import os
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    ENVIRONMENT: str = "development"
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    DEBUG: bool = True
    LOG_LEVEL: str = "info"

    # Simulation defaults
    SIMULATION_DT: float = 0.5
    DEFAULT_SPEED_LIMIT_MPS: float = 13.89  # 50 km/h ~ 13.89 m/s
    MAX_SIMULATION_STEPS: int = 7200

    # Optimization
    QAOA_MAX_ITER: int = 25
    QAOA_REPS: int = 1
    OPTIMIZATION_TIMEOUT_SECONDS: float = 20.0
    QUANTUM_PROVIDER: str = "aer_simulator"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
