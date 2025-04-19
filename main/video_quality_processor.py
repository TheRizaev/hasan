from django.conf import settings
import os
import threading
import logging
import time
from django.db import close_old_connections

logger = logging.getLogger(__name__)

def process_video_quality_async(video_file_path, user_id, video_id):
    """
    Start a background thread to process video quality without blocking the main thread
    
    Args:
        video_file_path (str): Path to the original video file
        user_id (str): User ID (with @ prefix)
        video_id (str): Video ID
    """
    # Create a copy of the video file since the original might be deleted
    temp_dir = os.path.join(settings.MEDIA_ROOT, 'temp', 'quality_processing')
    os.makedirs(temp_dir, exist_ok=True)
    
    # Generate a temp filename for the copy
    import uuid
    temp_file_path = os.path.join(temp_dir, f"{uuid.uuid4()}_{os.path.basename(video_file_path)}")
    
    try:
        # Copy the file
        with open(video_file_path, 'rb') as src, open(temp_file_path, 'wb') as dst:
            dst.write(src.read())
        
        # Create a thread to process the video quality
        worker_thread = threading.Thread(
            target=run_quality_processing,
            args=(temp_file_path, user_id, video_id)
        )
        worker_thread.daemon = True
        worker_thread.start()
        
        logger.info(f"Started background quality processing for video {video_id}")
        
        return True
    except Exception as e:
        logger.error(f"Error starting quality processing: {e}")
        # Clean up temp file if it exists
        if os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except:
                pass
        return False

def run_quality_processing(video_file_path, user_id, video_id):
    """
    Run the quality processing in a background thread
    
    Args:
        video_file_path (str): Path to the video file
        user_id (str): User ID (with @ prefix)
        video_id (str): Video ID
    """
    try:
        # Avoid Django connection issues in threads
        close_old_connections()
        
        # Sleep for a moment to allow the main request to complete
        time.sleep(2)
        
        # Import here to avoid circular imports
        from .video_quality import create_quality_variants
        
        # Start processing
        logger.info(f"Processing quality variants for video {video_id}")
        
        # Create quality variants
        quality_variants = create_quality_variants(video_file_path, user_id, video_id)
        
        # Log result
        if quality_variants:
            available_qualities = list(quality_variants.keys())
            logger.info(f"Successfully created {len(available_qualities)} quality variants for video {video_id}: {', '.join(available_qualities)}")
        else:
            logger.warning(f"No quality variants created for video {video_id}")
        
        # Clean up the temp file
        try:
            if os.path.exists(video_file_path):
                os.remove(video_file_path)
            # Try to remove parent directory if empty
            parent_dir = os.path.dirname(video_file_path)
            if os.path.exists(parent_dir) and not os.listdir(parent_dir):
                os.rmdir(parent_dir)
        except Exception as e:
            logger.error(f"Error cleaning up temp file: {e}")
    
    except Exception as e:
        logger.error(f"Error in background quality processing: {e}")
        # Clean up the temp file
        try:
            if os.path.exists(video_file_path):
                os.remove(video_file_path)
        except:
            pass