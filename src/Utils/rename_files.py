"""Utility script to batch rename files by replacing a substring in their names."""

from pathlib import Path

# Update these global variables before running the script.
path_files = ".data/PDFs"  # Directory that contains the files to rename.
type_files = ".pdf"  # File extension or suffix filter, e.g. ".txt" or "_report.pdf".
old_pattern = "%3A"  # Substring to replace in the file name.
new_pattern = "%2F"  # Replacement substring for the file name.


def rename_files(directory: Path, suffix: str, old: str, new: str) -> int:
    """Rename files inside directory by swapping the `old` substring for `new`."""
    renamed_count = 0
    pattern = f"*{suffix}" if suffix else "*"

    for file_path in directory.glob(pattern):
        if not file_path.is_file():
            continue
        if old not in file_path.name:
            continue

        new_name = file_path.name.replace(old, new)
        if new_name == file_path.name:
            continue

        destination = file_path.with_name(new_name)
        if destination.exists():
            print(f"Overwriting existing file '{destination.name}'.")

        file_path.replace(destination)
        print(f"Renamed '{file_path.name}' -> '{destination.name}'")
        renamed_count += 1

    return renamed_count


def main() -> None:
    directory = Path(path_files).expanduser()
    if not directory.is_dir():
        raise NotADirectoryError(f"'{directory}' is not a valid directory.")

    renamed_total = rename_files(directory, type_files, old_pattern, new_pattern)
    if renamed_total == 0:
        print("No files were renamed.")


if __name__ == "__main__":
    main()
