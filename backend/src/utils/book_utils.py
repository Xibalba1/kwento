# backend/src/kwento_backend/utils/book_utils.py
import re
from datetime import datetime


def book_title_normalize(input_string: str, append_datetime: bool = True) -> str:
    """Normalize a string by removing non-alphanumeric characters, replacing whitespace with
    underscores, and optionally appending the current datetime in YYYYMMDD_HHMMSS format.

    Args:
        input_string (str): The string to be normalized and appended with the datetime.
        append_datetime (bool): Whether to append the current datetime.

    Returns:
        str: The normalized string with the datetime appended if specified.

    Raises:
        TypeError: If the input_string is not of type str.
    """
    if not isinstance(input_string, str):
        raise TypeError("Input must be a string")

    # Remove all non-alphanumeric characters except whitespace
    normalized_string = re.sub(r"[^a-zA-Z0-9\s]", "", input_string)

    # Replace any whitespace (single or multiple) with a single underscore
    normalized_string = re.sub(r"\s+", "_", normalized_string)

    # Convert all characters to lowercase
    normalized_string = normalized_string.lower()

    if append_datetime:
        # Append the current datetime in YYYYMMDD_HHMMSS format
        current_datetime = datetime.now().strftime("%Y%m%d_%H%M%S")
        result = f"{normalized_string}_{current_datetime}"
    else:
        result = normalized_string

    return result
