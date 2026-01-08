"""Pydantic models for mantis configuration validation."""
from typing import Dict, List, Optional, Any

from pydantic import BaseModel, Field, model_validator


class ExtensionConfig(BaseModel):
    """Configuration for an extension."""
    service: Optional[str] = None


class EncryptionConfig(BaseModel):
    """Encryption configuration."""
    deterministic: bool = True
    folder: str = "<MANTIS>"


class ConfigsConfig(BaseModel):
    """Configs folder configuration."""
    folder: str = "<MANTIS>/.."


class BuildConfig(BaseModel):
    """Build configuration."""
    tool: str = "compose"
    args: Dict[str, str] = Field(default_factory=dict)


class ComposeConfig(BaseModel):
    """Docker Compose configuration."""
    command: str = "docker-compose"
    folder: str = "<MANTIS>/../compose"


class EnvironmentConfig(BaseModel):
    """Environment files configuration."""
    folder: str = "<MANTIS>/../environments"
    file_prefix: str = ""


class MantisConfig(BaseModel):
    """Main mantis configuration schema."""
    # Extensions
    extensions: Dict[str, ExtensionConfig] = Field(default_factory=dict)

    # Core settings
    encryption: EncryptionConfig = Field(default_factory=EncryptionConfig)
    configs: ConfigsConfig = Field(default_factory=ConfigsConfig)
    build: BuildConfig = Field(default_factory=BuildConfig)
    compose: ComposeConfig = Field(default_factory=ComposeConfig)
    environment: EnvironmentConfig = Field(default_factory=EnvironmentConfig)

    # Deployment
    zero_downtime: List[str] = Field(default_factory=list)
    project_path: str = "~"

    # Connections (mutually exclusive)
    connection: Optional[str] = None
    connections: Dict[str, str] = Field(default_factory=dict)

    # Custom manager class
    manager_class: str = "mantis.managers.BaseManager"

    model_config = {"extra": "forbid"}

    @model_validator(mode='after')
    def validate_connections(self):
        """Validate that only one of connection or connections is set."""
        if self.connection and self.connections:
            raise ValueError(
                'Cannot define both "connection" and "connections". '
                'Use either single connection mode or named environments, not both.'
            )
        return self


def validate_config(config_dict: Dict[str, Any]) -> MantisConfig:
    """
    Validate a config dictionary and return a MantisConfig instance.

    Raises pydantic.ValidationError with detailed error messages if validation fails.
    """
    return MantisConfig.model_validate(config_dict)
