from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    """Application settings"""
    
    # Application
    APP_NAME: str = "Pesa Analyser"
    APP_VERSION: str = "1.0.0"
    ENV: str = "development"
    DEBUG: bool = True
    PORT: int = 8000
    
    # Database
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/pesa_db"
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    
    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    
    # Security
    SECRET_KEY: str = "your-secret-key-change-in-production"
    JWT_SECRET: str = "your-jwt-secret-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440
    
    # CORS - Parse as string then split
    CORS_ORIGINS_STR: str = "http://localhost:3000,http://localhost:3001"
    
    @property
    def CORS_ORIGINS(self) -> List[str]:
        """Parse CORS origins from string"""
        return [origin.strip() for origin in self.CORS_ORIGINS_STR.split(",") if origin.strip()]
    
    # API Keys
    GEMINI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    
    # M-PESA
    MPESA_CONSUMER_KEY: Optional[str] = None
    MPESA_CONSUMER_SECRET: Optional[str] = None
    MPESA_PASSKEY: Optional[str] = None
    MPESA_SHORTCODE: Optional[str] = None
    MPESA_ENVIRONMENT: str = "sandbox"
    
    # Email
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM: Optional[str] = None
    
    # File Upload
    MAX_FILE_SIZE: int = 52428800
    UPLOAD_DIR: str = "./uploads"
    TEMP_DIR: str = "./temp"
    
    # Payment
    MINIMUM_PAYMENT: int = 50
    BASIC_ANALYSIS_PRICE: int = 50
    PREMIUM_ANALYSIS_PRICE: int = 150
    CREDIT_REPORT_PRICE: int = 500
    
    # AI
    AI_MODEL: str = "gemini-1.5-flash"
    AI_TEMPERATURE: float = 0.3
    AI_MAX_TOKENS: int = 4096

    
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        # Allow extra fields in .env
        extra = "ignore"

# Create singleton instance
settings = Settings()
