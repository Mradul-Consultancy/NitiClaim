"""
Enterprise Core Configuration & Settings Management
Loads from environment variables or .env file with type validation.
"""
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # App Information
    APP_NAME: str = "NitiClaim Enterprise Engine"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = False
    
    # Security
    SECRET_KEY: str = "niticlaim-super-secret-key-change-in-production-2026"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 1 day
    API_KEY_HEADER_NAME: str = "X-API-KEY"
    DEFAULT_API_KEY: str = "niticlaim-dev-key-12345"
    
    # Database
    DATABASE_URL: str = "sqlite:///./insurance_claims.db"
    
    # Vector DB
    CHROMA_PERSIST_DIR: str = "./chroma_db"
    
    # LLM Settings
    DEFAULT_LLM_PROVIDER: str = "perplexity"  # perplexity, openai, or mock
    PERPLEXITY_API_KEY: Optional[str] = None
    PERPLEXITY_MODEL: str = "sonar-pro"
    
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4o"
    
    # Retrieval Configuration
    TOP_K_CLAUSES: int = 5
    HYBRID_SEARCH_ALPHA: float = 0.6  # 0.6 Dense Vector + 0.4 BM25
    MIN_CONFIDENCE_THRESHOLD: float = 0.65  # Flag for human review if below

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
