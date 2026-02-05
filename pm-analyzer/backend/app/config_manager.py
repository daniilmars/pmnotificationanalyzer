import json
import os

CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'config.json')

DEFAULT_CONFIG = {
    "analysis_llm_settings": {
        "model": "gemini-1.5-flash",
        "temperature": 0.2
    },
    "chat_llm_settings": {
        "model": "gemini-1.5-flash",
        "temperature": 0.7
    }
}

def get_config() -> dict:
    """Loads the configuration from the JSON file, using defaults if the file doesn't exist."""
    if not os.path.exists(CONFIG_FILE):
        return DEFAULT_CONFIG
    with open(CONFIG_FILE, 'r') as f:
        return json.load(f)

def set_config(config: dict):
    """Saves the configuration to the JSON file."""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)

# Alias for backward compatibility
save_config = set_config