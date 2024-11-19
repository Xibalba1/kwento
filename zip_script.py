import zipfile
import os
import argparse
from fnmatch import fnmatch


def zip_directory(root_dir, zip_file_path, ignore_patterns):
    with zipfile.ZipFile(zip_file_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for foldername, subfolders, filenames in os.walk(root_dir):
            # Exclude folders matching the ignore pattern
            subfolders[:] = [
                d
                for d in subfolders
                if not any(
                    fnmatch(os.path.join(foldername, d), pat) for pat in ignore_patterns
                )
            ]

            for filename in filenames:
                file_path = os.path.join(foldername, filename)
                # Skip files matching any ignore pattern or the zip file itself
                if (
                    any(
                        fnmatch(os.path.relpath(file_path, root_dir), pat)
                        for pat in ignore_patterns
                    )
                    or file_path == zip_file_path
                ):
                    continue
                # Write file to zip, preserving the relative path from the root directory
                arcname = os.path.relpath(file_path, root_dir)
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
