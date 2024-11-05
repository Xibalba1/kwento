# backend/src/kwento_backend/utils/general_utils.py
from pathlib import Path


def get_project_root() -> Path:
    """
    Determines the project root by navigating up the directory tree until it finds
    a recognizable marker, such as a specific file or folder (e.g., pyproject.toml).
    In this case, it sets 'backend' as the root folder if found in the current path.
    """
    current_dir = Path(__file__).resolve()
    for parent in current_dir.parents:
        # Look for 'backend' as the specific project root marker
        if parent.name == "backend" and (parent / "pyproject.toml").exists():
            return parent
    raise RuntimeError("Project root could not be determined.")


def get_target_directory(relative_path: str) -> Path:
    """
    Gets or creates the target directory within the project based on a relative path
    from the project root. Ensures it’s a directory we can reliably access for saving files.

    Parameters:
    - relative_path: A relative path string to the target directory within the project.

    Returns:
    - Path: The full path to the target directory.
    """
    # Get the project root dynamically
    project_root = get_project_root()

    # Determine the target directory path
    target_dir = project_root / relative_path

    # Create the directory if it doesn't exist
    target_dir.mkdir(parents=True, exist_ok=True)

    return target_dir


def save_file(file_name: str, content: str, relative_path: str = "local_data") -> Path:
    """
    Saves a file with given content to a target directory within the project.

    Parameters:
    - file_name: The name of the file to save.
    - content: The content to write into the file.
    - relative_path: Relative path to the target directory within the project.

    Returns:
    - Path: The path to the saved file.
    """
    # Get or create the target directory
    target_dir = get_target_directory(relative_path)

    # Define the full file path
    file_path = target_dir / file_name

    # Write content to the file
    with open(file_path, "w") as f:
        f.write(content)

    return file_path


if __name__ == "__main__":
    # titles = [
    #     "Fuzzy's Spectactular Adventure",
    #     "Gulliver's Travels",
    #     "The Wormtongue Bible",
    #     "Alien 3",
    #     "Fight Club",
    #     "The Spectacular Now",
    #     "X-Men: Apocalypse",
    # ]
    # for t in titles:
    #     print(f"{t} --> {book_title_normalize(t)}")

    # Example content and filename
    file_name = "sample_output2.txt"
    content = "This is a sample output to be saved in local_data."

    # Call save_file function to save in "local_data"
    file_path = save_file(file_name, content, relative_path="local_data")

    print(f"File saved at: {file_path}")
