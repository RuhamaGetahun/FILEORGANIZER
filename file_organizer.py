import os
import shutil
import json
import hashlib
import time
import logging
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from logging.handlers import RotatingFileHandler

#EXTENSIONS dictionary with tuples
EXTENSIONS = {
    # 3D Models
    (".stl", ".obj", ".fbx", ".blend", ".dae", ".3ds", ".ply"): "3DModels",

    # Images
    (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".svg", ".heic", ".webp"): "Images",

    # Videos
    (".mp4", ".mkv", ".mov", ".avi", ".wmv", ".flv", ".webm", ".mpeg"): "Videos",

    # Audio
    (".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a", ".wma", ".aiff"): "Audio",

    # Documents
    (".doc", ".docx", ".pdf", ".txt", ".rtf", ".odt", ".tex", ".md"): "Documents",
    (".xlsx", ".xls", ".csv", ".ods"): "Spreadsheets",
    (".ppt", ".pptx", ".key", ".odp"): "Presentations",

    # Code
    (".py", ".java", ".cpp", ".c", ".cs", ".js", ".ts", ".html", ".css", ".php", ".rb", ".swift", ".go", ".rs"): "Code",

    # Archives
    (".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz"): "Archives",

    # Executables and Installers
    (".exe", ".msi", ".sh", ".bat", ".apk", ".dmg"): "Executables",

    # Fonts
    (".ttf", ".otf", ".woff", ".woff2"): "Fonts",

    # Ebooks
    (".epub", ".mobi", ".azw", ".azw3"): "Ebooks",

    # CAD Files
    (".dwg", ".dxf"): "CAD",

    # Disk Images
    (".iso", ".img"): "DiskImages",

    # Others
    (".sln", ".log", ".cfg", ".ini", ".bak"): "Others",
}

# Setting up logging configuration with rotation
logger = logging.getLogger("FileOrganizer")
logger.setLevel(logging.INFO)

# Rotating file handler (5 MB per file, up to 3 backups)
handler = RotatingFileHandler(
    "file_organization.log", maxBytes=5*1024*1024, backupCount=3
)
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)


def alert_user(message):
    """"
    Send a user alert when a critical error occurs.

    message -- The error or critical alert message to be sent.
    """
    logger.critical(f"ALERT: {message}") 

def categorize_error(error):
    """
    Categorizes errors for better decision-making in the retry logic.
    
    Argument:
    error -- The exception that was raised during the file move operation.
    
    Returns:
    A string indicating the type of error ('recoverable', 'non_recoverable', or 'unknown').
    """
    if isinstance(error, PermissionError):
        return 'recoverable'
    elif isinstance(error, FileNotFoundError):
        return 'non_recoverable'
    else:
        return 'unknown'

def retry_move_file(source, destination, retries=3, delay=2):
    """
    Try to move a file from source to destination with retries for recoverable errors.
    
    Arguments:
    source -- The source file path.
    destination -- The destination file path.
    retries -- Number of retry attempts (default: 3).
    delay -- Time delay between retries in seconds (default: 2 seconds).
    
    Returns:
    True if the file was successfully moved, False otherwise.
    
    Detailed Operation:
    - The function attempts to move a file from the source to the destination.
    - If a recoverable error occurs (like a permission error), it retries up to the specified number of retries.
    - For non-recoverable errors (like file not found), it stops and returns False.
    - If the file move fails after all retries, it logs the failure and alerts the user.
    """
    attempt = 0
    while attempt < retries:
        try:
            # Try to move the file
            os.rename(source, destination)
            logger.info(f"Successfully moved {source} to {destination}.")
            return True  # Successful move
        except Exception as e:
            error_type = categorize_error(e)
            
            # Handle recoverable errors
            if error_type == 'recoverable':
                logger.error(f"Attempt {attempt + 1}: Recoverable error when moving {source}. Error: {e}")
            # Handle non-recoverable errors (e.g., file not found)
            elif error_type == 'non_recoverable':
                logger.error(f"Attempt {attempt + 1}: Non-recoverable error when moving {source}. Skipping.")
                return False  # No need to retry if file is not found
            else:
                logger.error(f"Attempt {attempt + 1}: Unknown error when moving {source}. Error: {e}")
            
            attempt += 1
            time.sleep(delay)  # Wait before retrying

    logger.error(f"Failed to move {source} to {destination} after {retries} attempts.")
    alert_user(f"Failed to move {source} to {destination} after multiple attempts. Please check the log for details.")
    return False  # Final failure after retries

LOG_FILE = "file_movement_log.json"
CUSTOM_RULES_FILE = "custom_rules.json"


def load_custom_rules():
    """
    Loads custom file categorization rules from a JSON file.

    Checks if the custom rules file exists and loads the JSON data.
    If the file does not exist, returns an empty dictionary.

    Returns:
        dict: A dictionary containing custom file categorization rules.
    """
    if os.path.exists(CUSTOM_RULES_FILE):
        with open(CUSTOM_RULES_FILE, "r") as file:
            return json.load(file)
    return {}


def save_custom_rules(rules):
    """
    Saves custom file categorization rules to a JSON file.

    Arguments:
        rules (dict): A dictionary of custom file categorization rules to be saved.
    """
    with open(CUSTOM_RULES_FILE, "w") as file:
        json.dump(rules, file, indent=4)


def add_custom_rule(extension, folder_name):
    """
    Adds a custom categorization rule for a specific file extension.

    Arguments:
        extension (str): The file extension to be categorized (e.g., ".txt").
        folder_name (str): The folder name to assign to files with the given extension.

    Updates the custom rules file with the new rule.
    """
    rules = load_custom_rules()
    rules[extension] = folder_name
    save_custom_rules(rules)
    print(f"Custom rule added: {extension} -> {folder_name}")


def log_movement(src, dest):
    """
    Logs the movement of a file from source to destination in a JSON log file.

    If the log file does not exist, it initializes the file and writes an empty dictionary.
    Otherwise, it reads the existing log, updates it with the new file movement,
    and rewrites the updated log.

    Arguments:
        src (str): The source file path.
        dest (str): The destination file path.
    """
    movement_data = {src: dest}
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w") as log:
            json.dump({}, log)
    with open(LOG_FILE, "r+") as log:
        data = json.load(log)
        data.update(movement_data)
        log.seek(0)
        json.dump(data, log, indent=4)


def undo_selected_moves():
    """
    Allows the user to undo file movements based on the directory input.

    The function reads the movement log, searches for movements related to the
    specified directory (or part of the path), and attempts to move the files
    back to their original locations. After completing the undo operation,
    it updates the log to remove the undone movements.

    User input is used to specify the directory for which to undo actions.
    """
    if not os.path.exists(LOG_FILE):
        logger.info("No log file found. Nothing to undo.")
        return

    with open(LOG_FILE, "r") as log:
        data = json.load(log)

    directory_input = input("Enter the directory (or part of the path) for the actions you'd like to undo: ").strip()
    matching_entries = {dest: src for dest, src in data.items() if directory_input in src}

    if not matching_entries:
        logger.info(f"No actions found for the directory: {directory_input}")
        return

    for dest, src in matching_entries.items():
        try:
            os.makedirs(os.path.dirname(src), exist_ok=True)
            shutil.move(dest, src)
            logger.info(f"Moved back: {dest} -> {src}")
        except Exception as e:
            logger.error(f"Error moving {dest} back to {src}: {e}")

    remaining_data = {dest: src for dest, src in data.items() if dest not in matching_entries}

    with open(LOG_FILE, "w") as log:
        json.dump(remaining_data, log, indent=4)

    logger.info("Undo operation completed for the specified directory.")


def reset_custom_rules():
    """
    Resets the custom categorization rules by deleting the custom rules file.

    If the custom rules file exists, it is removed to restore default categorization behavior.
    """
    if os.path.exists(CUSTOM_RULES_FILE):
        os.remove(CUSTOM_RULES_FILE)
        print("Custom rules have been reset to default.")
    else:
        print("No custom rules found to reset.")


def get_file_hash(file_path, chunk_size=8192):
    """
    Generates the MD5 hash of a file to detect duplicates.

    Reads the file in chunks to avoid memory issues with large files.
    The generated hash can be used to identify duplicate files based on their content.

    Argumentss:
        file_path (str): The path to the file to be hashed.
        chunk_size (int): The size of chunks to read from the file (default: 8192 bytes).

    Returns:
        str: The MD5 hash of the file content.
    """
    hasher = hashlib.md5()
    with open(file_path, "rb") as file:
        while chunk := file.read(chunk_size):
            hasher.update(chunk)
    return hasher.hexdigest()


def get_folder_name(extension, extensions_map):
    """
    Retrieves the folder name associated with a given file extension.

    This function iterates through the extension map and returns the folder
    name corresponding to the file extension. If no match is found, it returns "Others".

    Arguments:
        extension (str): The file extension (e.g., ".jpg").
        extensions_map (dict): A dictionary mapping extension groups to folder names.

    Returns:
        str: The folder name associated with the file extension.
    """
    for ext_group, folder_name in extensions_map.items():
        if extension in ext_group:
            return folder_name
    return "Others"


def organize_files(directory):
    """
    Organizes files in the given directory based on their extensions.
    If duplicates are detected, they are handled (deleted or backed up).
    
    Arguments:
        directory (str): The directory where files are to be organized.
    """
    logger.info(f"Starting file organization in directory: {directory}")
    custom_rules = load_custom_rules()
    hash_map = {}  # For tracking file hashes to detect duplicates
    duplicates = []  # To store information about duplicate files

    for root, _, files in os.walk(directory):
        for filename in files:
            file_path = os.path.join(root, filename)
            file_extension = os.path.splitext(filename)[1].lower()
            
            # Determine target folder
            folder_name = custom_rules.get(file_extension) or get_folder_name(file_extension, EXTENSIONS)
            target_folder = os.path.join(directory, folder_name)
            os.makedirs(target_folder, exist_ok=True)

            # Calculate file hash to detect duplicates
            file_hash = get_file_hash(file_path)
            if file_hash in hash_map:
                # Found duplicate, handle it here
                duplicate_info = (file_path, hash_map[file_hash])
                duplicates.append(duplicate_info)
            else:
                # Move the file and log the movement
                hash_map[file_hash] = file_path
                new_path = os.path.join(target_folder, filename)

                try:
                    shutil.move(file_path, new_path)
                    log_movement(file_path, new_path)
                    logger.info(f"Moved: {file_path} -> {new_path}")
                except PermissionError:
                    logger.warning(f"Permission denied for: {file_path}")
                except Exception as e:
                    logger.error(f"Error moving {file_path}: {e}")

    # Handle duplicates after all files are processed
    handle_duplicates(duplicates)

    # Clean up empty directories left behind 
    for root, dirs, _ in os.walk(directory, topdown=False):
        for subdir in dirs:
            subfolder_path = os.path.join(root, subdir)
            if not os.listdir(subfolder_path):
                try:
                    os.rmdir(subfolder_path)
                    logger.info(f"Deleted empty folder: {subfolder_path}")
                except Exception as e:
                    logger.error(f"Error deleting folder {subfolder_path}: {e}")

    logger.info("\nOrganization complete! All files have been processed.")


def handle_duplicates(duplicates):
    """
    Handles duplicate files detected during the organization process.

    Parameters:
        duplicates (list): A list of tuples containing duplicate and original file paths.
    """
    if not duplicates:
        logger.info("No duplicate files found.")
        return

    logger.info("\nDuplicate Files Found:")
    for idx, (dup, original) in enumerate(duplicates, start=1):
        logger.info(f"{idx}. Duplicate: {dup}\n   Original: {original}\n")

    while True:
        choice = input("Do you want to delete all duplicates? (yes/no/backup): ").strip().lower()
        if choice in {"yes", "no", "backup"}:
            break
        print("Invalid choice. Please enter 'yes', 'no', or 'backup'.")

    if choice == "yes":
        delete_files(duplicates)
    elif choice == "backup":
        backup_duplicates(duplicates)
    else:
        logger.info("No changes made.")

def delete_files(duplicates):
    """
    Deletes the duplicate files provided in the duplicates list.

    Parameters:
        duplicates (list): A list of tuples containing duplicate file paths.
    """
    for dup, _ in duplicates:
        try:
            os.remove(dup)
            logger.info(f"Deleted: {dup}")
        except Exception as e:
            logger.error(f"Error deleting {dup}: {e}")

def backup_duplicates(duplicates, backup_dir="backup"):
    """
    Moves duplicate files to a backup directory.

    Parameters:
        duplicates (list): List of tuples containing duplicate and original file paths.
        backup_dir (str): Directory to move duplicates to.
    """
    os.makedirs(backup_dir, exist_ok=True)
    for dup, _ in duplicates:
        try:
            backup_path = os.path.join(backup_dir, os.path.basename(dup))
            os.rename(dup, backup_path)
            logger.info(f"Moved {dup} to {backup_path}")
        except Exception as e:
            logger.error(f"Error moving {dup} to backup: {e}")

class FileHandler(FileSystemEventHandler):
    """
    Handles events for real-time file system monitoring. When a new file is created,
    it triggers the file organization process.

    Attributes:
        directory (str): The directory to monitor for new files.
    """
    def __init__(self, directory):
        self.directory = directory

    def on_created(self, event):
        """
        Triggered when a new file is created. It calls the organize_files function to 
        organize the newly created file.
        """
        if not event.is_directory:
            print(f"New file detected: {event.src_path}")
            organize_files(self.directory)


def start_monitoring(directory):
    """
    Starts real-time monitoring of the specified directory to organize files 
    as soon as they are created.

    Parameters:
        directory (str): The directory to monitor for file creation.
    """
    event_handler = FileHandler(directory)
    observer = Observer()
    observer.schedule(event_handler, directory, recursive=True)
    observer.start()
    print(f"Real-time monitoring started for: {directory}")
    print("Press Ctrl+C to stop.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        observer.join()
        print("\nReal-time monitoring stopped.")


def main():
    """
    Main function to run the file organizer script. It presents a menu to the user 
    to select the desired action.
    """
    logger.info("Application started")
    print("File Organizer Script")
    print("1. Organize files (including nested folders)")
    print("2. Undo last moves")
    print("3. Add custom rule")
    print("4. Reset custom rules")
    print("5. Start real-time monitoring")
    choice = input("Enter your choice: ")

    if choice == "1":
        folder = input("Enter the folder to organize: ")
        if os.path.exists(folder):
            organize_files(folder)
        else:
            print("Folder does not exist.")
    elif choice == "2":
        undo_selected_moves()
    elif choice == "3":
        extension = input("Enter the file extension (e.g., .example): ").strip().lower()
        folder_name = input("Enter the folder name for this extension: ").strip()
        add_custom_rule(extension, folder_name)
    elif choice == "4":
        reset_custom_rules()
    elif choice == "5":
        folder = input("Enter the folder to monitor: ")
        if os.path.exists(folder):
            start_monitoring(folder)
        else:
            print("Folder does not exist.")
    else:
        print("Invalid choice. Please select a valid option.")


if __name__ == "__main__":
    main()