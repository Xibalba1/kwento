import zipfile
import os
import argparse
from fnmatch import fnmatch


def zip_directory(root_dir, zip_file_path, ignore_patterns):
    with zipfile.ZipFile(zip_file_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for foldername, subfolders, filenames in os.walk(root_dir):
            # Normalize foldername to a relative path for comparison
            rel_folder = os.path.relpath(foldername, root_dir)

            # Skip this entire folder if it matches any pattern
            if any(fnmatch(rel_folder, pat) for pat in ignore_patterns):
                print(f"Skipping folder: {rel_folder}")
                subfolders[:] = []  # Clear subfolders to stop os.walk from descending
                continue

            # Process files in this folder
            for filename in filenames:
                file_path = os.path.join(foldername, filename)
                rel_file_path = os.path.relpath(file_path, root_dir)

                # Skip files matching any ignore pattern or the zip file itself
                if (
                    any(fnmatch(rel_file_path, pat) for pat in ignore_patterns)
                    or file_path == zip_file_path
                ):
                    print(f"Skipping file: {rel_file_path}")
                    continue

                # Write file to zip, preserving the relative path from the root directory
                arcname = os.path.relpath(file_path, root_dir)
                print(f"Adding to zip: {arcname}")
                zipf.write(file_path, arcname)


def main():
    parser = argparse.ArgumentParser(
        description="Zip the files in a project, ignoring specified files or directories."
    )
    parser.add_argument(
        "--ignore",
        nargs="*",
        default=[],
        help="Patterns to ignore, similar to .gitignore (e.g., *settings.json*)",
    )
    args = parser.parse_args()

    project_root = os.getcwd()
    project_name = os.path.basename(project_root)
    zip_file_path = f"{project_name}.zip"
    ignore_patterns = args.ignore

    # Add the zip file itself to ignore patterns to prevent recursive zipping
    ignore_patterns.append(zip_file_path)

    zip_directory(project_root, zip_file_path, ignore_patterns)


if __name__ == "__main__":
    main()
