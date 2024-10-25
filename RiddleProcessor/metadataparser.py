import json
import os
from typing import Optional, Dict

def save_or_update_dict_by_key(file_path: str, key: str, value: Dict) -> None:
    """
    Saves a new key-value pair to the JSON file or updates the value if the key already exists.

    Parameters:
    - file_path (str): Path to the JSON file.
    - key (str): The key under which the value will be stored.
    - value (dict): The dictionary value to be saved or updated.

    Raises:
    - IOError: If there is an issue reading or writing the file.
    - ValueError: If the existing file contains invalid JSON.
    """
    read_json = {}

    # Check if the file exists
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                data = json.load(file)
                if isinstance(data, dict):
                    read_json = data
                    
        except Exception as e:
            read_json = {}

    # Update the dictionary with the new key-value pair
    read_json[key] = value

    # Write the updated dictionary back to the file
    try:
        with open(file_path, 'w', encoding='utf-8') as file:
            json.dump(read_json, file, indent=4, ensure_ascii=False)
    except Exception as e:
        raise IOError(f"Error writing to {file_path}: {e}")

def read_dict_by_key(file_path: str, key: str) -> Optional[Dict]:
    """
    Reads and returns the dictionary associated with the specified key from the JSON file.

    Parameters:
    - file_path (str): Path to the JSON file.
    - key (str): The key whose associated dictionary value will be retrieved.

    Returns:
    - dict or None: The dictionary associated with the key, or None if the key does not exist.

    Raises:
    - IOError: If there is an issue reading the file.
    - ValueError: If the existing file contains invalid JSON.
    """
    if not os.path.exists(file_path):
        print(f"File {file_path} does not exist.")
        return None

    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            data = json.load(file)
            if not isinstance(data, dict):
                raise ValueError("JSON content is not a dictionary.")
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON format in {file_path}: {e}")
    except Exception as e:
        raise IOError(f"Error reading {file_path}: {e}")

    return data.get(key)

