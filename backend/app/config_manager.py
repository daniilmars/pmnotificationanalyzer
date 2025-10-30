import json
import os
from typing import Dict, Any

CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'config.json')

def get_config() -> Dict[str, Any]:
    """Reads and returns the configuration from config.json."""
    if not os.path.exists(CONFIG_FILE):
        # This is a fallback for the initial state or if the file is deleted.
        # In a real-world scenario, you might want to create a default config.
        return {
            "analysis_llm_settings": {
                "model": "gemini-1.5-flash-latest",
                "temperature": 0.2
            },
            "chat_llm_settings": {
                "model": "gemini-1.5-flash-latest",
                "temperature": 0.4
            },
            "quality_rules": [
                "The long text must be detailed and clearly describe the problem.",
                "A root cause for the issue must be identified.",
                "An assessment of the product impact must be included.",
                "Corrective and preventive actions (CAPA) must be outlined."
            ]
        }
    with open(CONFIG_FILE, 'r') as f:
        return json.load(f)

def save_config(config_data: Dict[str, Any]) -> None:
    """Saves the provided configuration data to config.json."""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config_data, f, indent=4)