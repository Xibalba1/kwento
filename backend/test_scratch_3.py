import os
import json
from jsonschema import validate, ValidationError

# Define the JSON schema
schema = {
    "type": "object",
    "properties": {
        "book_id": {"type": "string"},
        "book_title": {"type": "string"},
        "book_length_n_pages": {"type": "integer"},
        "characters": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "appearance": {"type": "string"},
                },
                "required": ["name", "description", "appearance"],
            },
        },
        "plot_synopsis": {"type": "string"},
        "pages": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "page_number": {"type": "integer"},
                    "content": {
                        "type": "object",
                        "properties": {
                            "text_content_of_this_page": {"type": "string"},
                            "illustration_b64_data": {"type": "string"},
                            "characters_in_this_page": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                        },
                        "required": [
                            "text_content_of_this_page",
                            "illustration_b64_data",
                            "characters_in_this_page",
                        ],
                    },
                },
                "required": ["page_number", "content"],
            },
        },
    },
    "required": [
        "book_id",
        "book_title",
        "book_length_n_pages",
        "characters",
        "plot_synopsis",
        "pages",
    ],
}


def validate_json_file(file_path):
    try:
        with open(file_path, "r") as file:
            data = json.load(file)
        validate(instance=data, schema=schema)
        return True, None
    except ValidationError as e:
        return False, str(e)
    except json.JSONDecodeError as e:
        return False, f"Invalid JSON format: {e}"


def main(directory):
    results = []
    for subdir, _, files in os.walk(directory):
        json_files = [f for f in files if f.endswith(".json")]
        if len(json_files) == 1:  # Ensure only one JSON file in the subdir
            json_file_path = os.path.join(subdir, json_files[0])
            is_valid, error = validate_json_file(json_file_path)
            results.append(
                {
                    "subdirectory": subdir,
                    "file": json_files[0],
                    "status": "Valid" if is_valid else "Invalid",
                    "error": error,
                }
            )
        elif len(json_files) > 1:
            results.append(
                {
                    "subdirectory": subdir,
                    "file": None,
                    "status": "Error",
                    "error": "Multiple JSON files found",
                }
            )
        elif len(json_files) == 0:
            results.append(
                {
                    "subdirectory": subdir,
                    "file": None,
                    "status": "Error",
                    "error": "No JSON file found",
                }
            )

    # Report results
    for result in results:
        print(f"Subdirectory: {result['subdirectory']}")
        print(f"File: {result['file']}")
        print(f"Status: {result['status']}")
        if result["error"]:
            print(f"Error: {result['error']}")
        print("-" * 40)


# Replace 'your_directory_path' with the directory you want to process
if __name__ == "__main__":
    main("/Users/ik/repos/kwento/backend/local_data")
