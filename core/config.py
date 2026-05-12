from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./app.db"
    # Add other project-wide settings here

    class Config:
        env_file = ".env"
