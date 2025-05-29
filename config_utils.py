import json
import logging
from pathlib import Path
from PyQt6.QtWidgets import QMessageBox # Required for save_app_config

# Configuration Constants
CONFIG_FILE_NAME = "config.json"
CONFIG_KEY_DEFAULT_FOLDER = "DEFAULT_FOLDER"
CONFIG_KEY_LAST_NOTE = "LAST_NOTE"
CONFIG_KEY_GEMINI_API_KEY = "GEMINI_API_KEY"

def _get_config_path() -> Path:
    """Returns the absolute path to the configuration file.
    Assumes config.json is in the same directory as this utils file,
    or that this logic is adjusted if config_utils.py is moved elsewhere.
    For now, assuming it's at the project root alongside main.py.
    If main.py is in a subdirectory, this might need adjustment or
    a more robust way to find the project root or config location.
    Given current structure, Path(__file__).resolve().parent assumes config_utils.py
    is in the same directory where config.json should be (e.g. project root).
    If main.py was calling this and main.py was in root, it was Path(main_py__file__)... etc.
    Let's assume config_utils.py is in the same directory as main.py for now.
    """
    current_path = Path(__file__).resolve().parent
    project_root = None
    # Ascend up to 5 levels to find .git directory
    for _ in range(5):
        if (current_path / ".git").is_dir():
            project_root = current_path
            break
        if current_path.parent == current_path: # Reached the root of the filesystem
            break
        current_path = current_path.parent

    if project_root:
        config_path = project_root / CONFIG_FILE_NAME
    else:
        original_path = Path(__file__).resolve().parent / CONFIG_FILE_NAME
        logging.warning(
            f"Could not determine project root. Falling back to original config path: {original_path}"
        )
        config_path = original_path
    
    return config_path.resolve() # Ensure absolute path

def load_app_config() -> dict:
    """Loads the application configuration from config.json.

    Returns:
        dict: The configuration dictionary, or an empty dict if loading fails.
    """
    config_path = _get_config_path()
    if not config_path.exists():
        return {}
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"Warning: Could not parse {CONFIG_FILE_NAME} at {config_path}: {e}")
        return {}
    except IOError as e:
        print(f"Warning: Could not read {CONFIG_FILE_NAME} at {config_path}: {e}")
        return {}

def save_app_config(config_data: dict) -> bool:
    """Saves the application configuration to config.json.

    Args:
        config_data (dict): The configuration dictionary to save.

    Returns:
        bool: True if saving was successful, False otherwise.
    """
    config_path = _get_config_path()
    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=2)
        return True
    except IOError as e:
        QMessageBox.warning(None, "Config Error", f"Could not write to {CONFIG_FILE_NAME} at {config_path}:\n{e}")
        return False
    except TypeError as e:
        QMessageBox.warning(None, "Config Error", f"Invalid data type provided for saving to {CONFIG_FILE_NAME}:\n{e}")
        return False
