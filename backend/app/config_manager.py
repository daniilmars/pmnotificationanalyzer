import json
import os
from threading import Lock

CONFIG_FILE = os.path.join(os.path.dirname(__file__), '..', 'config.json')
lock = Lock()

DEFAULT_CONFIG = {
    "quality_rules": [
        "A batch number is mandatory for M1 notifications.",
        "The root cause must be clearly identified.",
        "Product impact assessment must be explicitly stated."
    ],
    "analysis_llm_settings": {
        "model": "gemini-1.5-flash-latest",
        "temperature": 0.2
    },
    "chat_llm_settings": {
        "model": "gemini-1.5-flash-latest",
        "temperature": 0.4
    }
}

def get_config() -> dict:
    """Reads the application configuration from the JSON file."""
    with lock:
        if not os.path.exists(CONFIG_FILE):
            return DEFAULT_CONFIG
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except (IOError, json.JSONDecodeError):
            return DEFAULT_CONFIG

def save_config(config_data: dict) -> None:
    """Saves the application configuration to the JSON file."""
    with lock:
        try:
            with open(CONFIG_FIlE, 'w') as f:
                json.dump(config_data, f, indent=4)
        except IOError as e:
            print(f"Error saving configuration: {e}")
            raise
