import os
import logging
import shutil
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Set

# Set up logging
logger = logging.getLogger(__name__)

# Global set to track files scheduled for deletion
_files_scheduled_for_deletion: Set[str] = set()

def clean_temp_folder(max_age_hours=24):
    """
    Clean up temporary files from the data/temp folder

    Args:
        max_age_hours: Maximum age of files to keep (in hours)

    Returns:
        tuple: (number of files deleted, total size freed in bytes)
    """
    try:
        # Get temp folder path
        temp_folder = os.path.join("data", "temp")

        # Check if folder exists
        if not os.path.exists(temp_folder):
            logger.warning(f"Temp folder not found: {temp_folder}")
            return 0, 0

        # Calculate cutoff time
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)

        # Track statistics
        files_deleted = 0
        bytes_freed = 0

        # Iterate through files in temp folder
        for item in os.listdir(temp_folder):
            item_path = os.path.join(temp_folder, item)

            # Skip directories for now
            if os.path.isdir(item_path):
                continue

            # Check file modification time
            mtime = datetime.fromtimestamp(os.path.getmtime(item_path))

            # Delete files older than cutoff time
            if mtime < cutoff_time:
                # Get file size before deleting
                file_size = os.path.getsize(item_path)

                try:
                    os.remove(item_path)
                    files_deleted += 1
                    bytes_freed += file_size
                    logger.info(f"Deleted temp file: {item}")
                except Exception as e:
                    logger.error(f"Error deleting temp file {item}: {str(e)}")

        # Clean empty subdirectories
        for root, dirs, files in os.walk(temp_folder, topdown=False):
            for dir_name in dirs:
                dir_path = os.path.join(root, dir_name)
                if not os.listdir(dir_path):  # Check if directory is empty
                    try:
                        os.rmdir(dir_path)
                        logger.info(f"Removed empty directory: {dir_path}")
                    except Exception as e:
                        logger.error(f"Error removing directory {dir_path}: {str(e)}")

        logger.info(f"Temp folder cleanup: {files_deleted} files deleted, {bytes_freed/1024:.2f} KB freed")
        return files_deleted, bytes_freed

    except Exception as e:
        logger.error(f"Error cleaning temp folder: {str(e)}")
        return 0, 0

def clean_all_temp_files():
    """
    Remove all files and subdirectories from the temp folder

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Get temp folder path
        temp_folder = os.path.join("data", "temp")

        # Check if folder exists
        if not os.path.exists(temp_folder):
            logger.warning(f"Temp folder not found: {temp_folder}")
            return True

        # Delete all contents
        for item in os.listdir(temp_folder):
            item_path = os.path.join(temp_folder, item)

            try:
                if os.path.isfile(item_path):
                    os.remove(item_path)
                    logger.info(f"Deleted temp file: {item}")
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                    logger.info(f"Deleted temp directory: {item}")
            except Exception as e:
                logger.error(f"Error deleting temp item {item}: {str(e)}")

        logger.info("All temporary files cleaned")
        return True

    except Exception as e:
        logger.error(f"Error cleaning all temp files: {str(e)}")
        return False

def schedule_file_deletion(file_paths: List[str], delay_minutes: int = 10) -> bool:
    """
    Schedule files for deletion after a specified delay

    Args:
        file_paths: List of file paths to delete
        delay_minutes: Delay in minutes before deletion (default: 10)

    Returns:
        bool: True if scheduling was successful, False otherwise
    """
    global _files_scheduled_for_deletion

    try:
        if not file_paths:
            return True

        # Add files to the scheduled set to avoid duplicate scheduling
        newly_scheduled = []
        for file_path in file_paths:
            if file_path not in _files_scheduled_for_deletion:
                _files_scheduled_for_deletion.add(file_path)
                newly_scheduled.append(file_path)

        if not newly_scheduled:
            return True

        # Start a thread to delete the files after the delay
        def delayed_deletion():
            try:
                # Sleep for the specified delay
                time.sleep(delay_minutes * 60)

                # Delete each file
                deleted_count = 0
                bytes_freed = 0

                for file_path in newly_scheduled:
                    try:
                        if os.path.exists(file_path):
                            # Get file size before deleting
                            file_size = os.path.getsize(file_path)

                            # Delete the file
                            os.remove(file_path)

                            # Update counters
                            deleted_count += 1
                            bytes_freed += file_size

                            # Remove from the scheduled set
                            _files_scheduled_for_deletion.discard(file_path)

                            logger.info(f"Deleted file after {delay_minutes} minutes: {file_path}")
                    except Exception as file_error:
                        logger.error(f"Error deleting scheduled file {file_path}: {str(file_error)}")
                        # Remove from the scheduled set even if deletion failed
                        _files_scheduled_for_deletion.discard(file_path)

                logger.info(f"Scheduled deletion complete: {deleted_count} files deleted, {bytes_freed/1024:.2f} KB freed")
            except Exception as thread_error:
                logger.error(f"Error in delayed deletion thread: {str(thread_error)}")

        # Start the deletion thread
        deletion_thread = threading.Thread(target=delayed_deletion)
        deletion_thread.daemon = True  # Make thread a daemon so it doesn't block program exit
        deletion_thread.start()

        logger.info(f"Scheduled {len(newly_scheduled)} files for deletion after {delay_minutes} minutes")
        return True

    except Exception as e:
        logger.error(f"Error scheduling file deletion: {str(e)}")
        return False
