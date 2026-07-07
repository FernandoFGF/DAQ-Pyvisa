"""
Configuration Loader Module

This module handles loading configuration from config.yaml and .env files.
It provides a centralized way to access all application settings.

Author: Fernando Fuentes-Guerra
Date: 2025
"""

import os
import yaml
from pathlib import Path
from dotenv import load_dotenv
from typing import Any, Dict, Optional


class ConfigLoader:
    """
    Loads and manages application configuration from YAML and environment files.
    """
    
    _instance = None
    _config: Dict[str, Any] = {}
    _loaded = False
    
    def __new__(cls):
        """Singleton pattern to ensure only one configuration instance."""
        if cls._instance is None:
            cls._instance = super(ConfigLoader, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize the configuration loader."""
        if not self._loaded:
            self.load_config()
    
    def load_config(self, config_path: Optional[str] = None) -> None:
        """
        Load configuration from YAML file and environment variables.

        Args:
            config_path: Optional path to config file. If None, uses default 'config.yaml'
        """
        # Load environment variables from .env file if it exists
        load_dotenv()

        # Determine config file path
        if config_path is None:
            config_path = os.getenv('CONFIG_PATH', 'config.yaml')

        # Get project root directory
        self.project_root = Path(__file__).parent.resolve()

        # Resolve the actual file we are going to load from; remember the
        # absolute path so _save_config writes back to the same file
        # even if the caller passed a relative or absolute path.
        config_file = Path(config_path)
        if not config_file.is_absolute():
            config_file = self.project_root / config_file
        self._config_path = config_file

        if not config_file.exists():
            raise FileNotFoundError(
                f"Configuration file not found: {config_file}\n"
                f"Please ensure config.yaml exists in the project root."
            )

        with open(config_file, 'r', encoding='utf-8') as f:
            self._config = yaml.safe_load(f)

        self._loaded = True
    
    @property
    def config(self) -> Dict[str, Any]:
        """Get the full configuration dictionary."""
        return self._config
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value by key.
        
        Args:
            key: Configuration key (supports dot notation like 'instruments.smu.address')
            default: Default value if key not found
            
        Returns:
            Configuration value or default
        """
        keys = key.split('.')
        value = self._config
        
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default
    
    # Instrument configuration
    def get_instrument_address(self, instrument_name: str) -> str:
        """
        Get the address for a specific instrument.

        Args:
            instrument_name: Name of the instrument (e.g., 'smu', 'scope1')

        Returns:
            Instrument address string

        Raises:
            KeyError: If instrument not found in configuration
        """
        try:
            return self._config['instruments'][instrument_name]['address']
        except KeyError:
            raise KeyError(
                f"Instrument '{instrument_name}' not found in configuration. "
                f"Available instruments: {list(self._config['instruments'].keys())}"
            )

    def set_instrument_address(self, instrument_name: str, new_address: str) -> None:
        """
        Update the in-memory address for ``instrument_name`` and persist it
        back to the config YAML file on disk.

        Raises:
            KeyError: If ``instrument_name`` is not in the configuration.
        """
        if 'instruments' not in self._config or instrument_name not in self._config['instruments']:
            raise KeyError(
                f"Instrument '{instrument_name}' not found in configuration. "
                f"Available instruments: {list(self._config.get('instruments', {}).keys())}"
            )
        self._config['instruments'][instrument_name]['address'] = new_address
        self._save_config()

    def _save_config(self, config_path: Optional[str] = None) -> None:
        """Write the in-memory config back to the YAML file we loaded from.

        If ``config_path`` is provided, write to that path (absolute paths
        are honoured). Otherwise, write back to the file recorded by
        ``load_config``. As a last-resort fallback (no load happened),
        honour the ``CONFIG_PATH`` env var.
        """
        if config_path is not None:
            target = Path(config_path)
            if not target.is_absolute():
                project_root = getattr(self, "project_root", Path.cwd())
                target = project_root / target
        elif getattr(self, "_config_path", None) is not None:
            target = self._config_path
        else:
            fallback = os.getenv('CONFIG_PATH', 'config.yaml')
            target = Path(fallback)
            if not target.is_absolute():
                project_root = getattr(self, "project_root", Path.cwd())
                target = project_root / target
        with open(target, 'w', encoding='utf-8') as f:
            yaml.safe_dump(self._config, f, default_flow_style=False, sort_keys=False)
    
    def get_instrument_timeout(self, instrument_name: str) -> Optional[int]:
        """
        Get the timeout value for a specific instrument.
        
        Args:
            instrument_name: Name of the instrument
            
        Returns:
            Timeout in milliseconds or None
        """
        try:
            return self._config['instruments'][instrument_name].get('timeout')
        except KeyError:
            return None
    
    def get_instrument_config(self, instrument_name: str) -> Dict[str, Any]:
        """
        Get full configuration for a specific instrument.
        
        Args:
            instrument_name: Name of the instrument
            
        Returns:
            Dictionary with instrument configuration
        """
        try:
            return self._config['instruments'][instrument_name]
        except KeyError:
            raise KeyError(f"Instrument '{instrument_name}' not found in configuration")
    
    # Path configuration
    def get_output_path(self, measurement_type: Optional[str] = None) -> Path:
        """
        Get the output path for saving measurement results.
        
        Args:
            measurement_type: Optional measurement type ('iv_curves', 'spectrum', 'waveform')
            
        Returns:
            Path object for the output directory
        """
        # Check for custom output path in environment variable
        custom_path = os.getenv('OUTPUT_PATH')
        
        if custom_path:
            base_path = Path(custom_path)
        else:
            # Use path from config relative to project root
            base_path = self.project_root / self._config['paths']['output_base']
        
        # Add measurement type subdirectory if specified
        if measurement_type:
            subdir = self._config['paths'].get(measurement_type, measurement_type)
            return base_path / subdir
        
        return base_path
    
    # Constants
    def get_constant(self, constant_name: str, default: Any = None) -> Any:
        """
        Get a constant value from configuration.
        
        Args:
            constant_name: Name of the constant
            default: Default value if constant not found
            
        Returns:
            Constant value or default
        """
        return self._config.get('constants', {}).get(constant_name, default)
    
    # GUI Settings
    def get_gui_setting(self, setting_name: str, default: Any = None) -> Any:
        """
        Get a GUI setting from configuration.
        
        Args:
            setting_name: Name of the setting
            default: Default value if setting not found
            
        Returns:
            Setting value or default
        """
        return self._config.get('gui', {}).get(setting_name, default)
    
    # Audio settings
    def get_audio_setting(self, setting_name: str, default: Any = None) -> Any:
        """
        Get an audio setting from configuration.
        
        Args:
            setting_name: Name of the setting
            default: Default value if setting not found
            
        Returns:
            Setting value or default
        """
        return self._config.get('audio', {}).get(setting_name, default)
    
    # Logging settings
    def get_logging_config(self) -> Dict[str, Any]:
        """
        Get logging configuration.
        
        Returns:
            Dictionary with logging configuration
        """
        return self._config.get('logging', {})
    
    # File formats
    def get_file_format(self, format_name: str, default: str = "") -> str:
        """
        Get a file format setting.
        
        Args:
            format_name: Name of the format setting
            default: Default value if setting not found
            
        Returns:
            Format string or default
        """
        return self._config.get('file_formats', {}).get(format_name, default)
    
    # Development mode
    def is_dev_mode(self) -> bool:
        """
        Check if development mode is enabled.
        
        Returns:
            True if development mode is enabled
        """
        return os.getenv('DEV_MODE', 'false').lower() == 'true'
    
    def __repr__(self) -> str:
        """String representation of the configuration."""
        return f"ConfigLoader(loaded={self._loaded}, config_keys={list(self._config.keys())})"


# Global configuration instance
_config_instance = ConfigLoader()


# Convenience functions for direct access
def get_config() -> ConfigLoader:
    """Get the global configuration instance."""
    return _config_instance


def get_instrument_address(instrument_name: str) -> str:
    """Get instrument address from configuration."""
    return _config_instance.get_instrument_address(instrument_name)


def get_output_path(measurement_type: Optional[str] = None) -> Path:
    """Get output path from configuration."""
    return _config_instance.get_output_path(measurement_type)


def get_constant(constant_name: str, default: Any = None) -> Any:
    """Get constant from configuration."""
    return _config_instance.get_constant(constant_name, default)


# Example usage
if __name__ == "__main__":
    # Test the configuration loader
    config = ConfigLoader()
    
    print("Configuration loaded successfully!")
    print(f"\nProject root: {config.project_root}")
    print(f"\nSMU Address: {config.get_instrument_address('smu')}")
    print(f"Output path: {config.get_output_path()}")
    print(f"Histogram bins: {config.get_constant('histogram_bins')}")
    print(f"Dev mode: {config.is_dev_mode()}")
