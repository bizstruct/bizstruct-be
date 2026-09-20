from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    """
        Application configuration settings.
    """
    
    title: str = Field(
        default="BizStruct API",
        description="The title of the application"
    )
    description: str = Field(
        default="AI-driven business modeling SaaS backend",
        description="A brief description of the application"
    )
    version: str = Field(
        default="1.0.0",
        description="The version of the application"
    )


class CORSConfig(BaseSettings):
    """
        CORS (Cross-Origin Resource Sharing) configuration settings.
    """
    
    allowed_origins: list[str] = Field(
        default=["*"],
        description="List of allowed origins for CORS"
    )
    allow_credentials: bool = Field(
        default=True,
        description="Whether to allow credentials in CORS requests"
    )
    allow_methods: list[str] = Field(
        default=["*"],
        description="List of allowed HTTP methods for CORS"
    )
    allow_headers: list[str] = Field(
        default=["*"],
        description="List of allowed headers for CORS"
    )



class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app: AppConfig = AppConfig()
    cors: CORSConfig = CORSConfig()

    # Database
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"
    postgres_db: str = "bizstruct"
    postgres_host: str = "db"
    postgres_port: int = 5432

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # App
    debug: bool = False
    allowed_origins: list[str] = ["*"]

    # Internal API key — used by ML service to authenticate internal endpoints
    internal_api_key: str = "change-me-in-production"

    # Azure Service Bus — enqueues ML generation tasks
    service_bus_connection_string: str | None = None
    service_bus_queue_name: str = "generation-tasks"

    # Azure Web PubSub
    azure_web_pubsub_connection_string: str = ""
    azure_web_pubsub_hub: str = "bizstruct"

settings = Settings()
