import os
import time
import logging
import tempfile
import shutil
from app.core.utils import schedule_file_deletion

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_scheduled_deletion():
    """Test the scheduled file deletion functionality"""
    # Create test files
    data_temp_dir = os.path.join("data", "temp")
    os.makedirs(data_temp_dir, exist_ok=True)
    
    test_files = []
    for i in range(3):
        # Create a test file
        file_path = os.path.join(data_temp_dir, f"test_file_{i}.txt")
        with open(file_path, "w") as f:
            f.write(f"Test content {i}")
        test_files.append(file_path)
        logger.info(f"Created test file: {file_path}")
    
    # Schedule files for deletion after 1 minute (for testing)
    schedule_file_deletion(test_files, delay_minutes=1)
    logger.info(f"Scheduled {len(test_files)} files for deletion after 1 minute")
    
    # Wait for files to be deleted
    logger.info("Waiting for files to be deleted...")
    time.sleep(70)  # Wait a bit longer than 1 minute
    
    # Check if files were deleted
    deleted_count = 0
    for file_path in test_files:
        if not os.path.exists(file_path):
            deleted_count += 1
            logger.info(f"File was deleted: {file_path}")
        else:
            logger.warning(f"File was NOT deleted: {file_path}")
    
    logger.info(f"Test complete: {deleted_count}/{len(test_files)} files were deleted")

if __name__ == "__main__":
    test_scheduled_deletion()
