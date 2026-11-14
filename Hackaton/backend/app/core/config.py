"""Configuración central de FuegoClaro.

La MAP_KEY de NASA FIRMS vive exclusivamente en el backend (.env).
El frontend nunca recibe credenciales.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = PROJECT_ROOT / "backend"


class Settings(BaseSettings):
    app_name: str = "FuegoClaro API"
    version: str = "0.1.0"
    firms_map_key: str = ""
    data_dir: Path = PROJECT_ROOT / "data"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def processed_dir(self) -> Path:
        return self.data_dir / "processed"

    @property
    def samples_dir(self) -> Path:
        return self.data_dir / "samples"

    @property
    def manifests_dir(self) -> Path:
        return self.data_dir / "manifests"

    @property
    def regions_dir(self) -> Path:
        return self.data_dir / "regions"

    @property
    def detections_file(self) -> Path:
        return self.processed_dir / "detections.csv"

    @property
    def manifest_file(self) -> Path:
        return self.processed_dir / "manifest.json"


@lru_cache
def get_settings() -> Settings:
    return Settings()
