"""
Application configuration using Pydantic Settings.
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Application
    app_name: str = "StitchFlow V2"
    app_env: str = "development"
    debug: bool = True
    
    # Database
    database_url: str = "sqlite:///./stitchflow.db"
    
    # Z.AI GLM API Configuration
    zhipu_api_key: str  # Required - must be in .env
    glm_model: str  # Required - must be in .env (e.g., "ilmu-glm-5.1" or "glm-4-plus")
    glm_base_url: str  # Required - must be in .env (e.g., "https://api.ilmu.ai/anthropic")

    # Security
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # File Storage
    upload_dir: str = "./uploads"
    max_upload_size_mb: int = 10
    
    # Retry Configuration
    max_retries: int = 3
    retry_initial_delay: float = 1.0
    retry_backoff_factor: float = 2.0
    
    # Logging
    log_level: str = "INFO"
    log_file: str = "./logs/stitchflow.log"
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()
