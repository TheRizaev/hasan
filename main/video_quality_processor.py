from django.conf import settings
import os
import threading
import logging
import time
import shutil
from django.db import close_old_connections

logger = logging.getLogger(__name__)

def process_video_quality_async(video_file_path, user_id, video_id):
    """
    Start a background thread to process video quality without blocking the main thread
    
    Args:
        video_file_path (str): Path to the original video file (local or gs:// path)
        user_id (str): User ID (with @ prefix)
        video_id (str): Video ID
    """
    try:
        # Create a thread to process the video quality
        worker_thread = threading.Thread(
            target=run_quality_processing,
            args=(video_file_path, user_id, video_id)
        )
        worker_thread.daemon = True
        worker_thread.start()
        
        logger.info(f"Started background quality processing for video {video_id}")
        
        return True
    except Exception as e:
        logger.error(f"Error starting quality processing: {e}")
        return False

def run_quality_processing(video_file_path, user_id, video_id):
    """
    Run the quality processing in a background thread.
    This is used as a fallback when synchronous processing fails.
    
    Args:
        video_file_path (str): Path to the video file (local or gs:// path)
        user_id (str): User ID (with @ prefix)
        video_id (str): Video ID
    """
    try:
        # Avoid Django connection issues in threads
        close_old_connections()
        
        # Sleep for a moment to allow the main request to complete
        time.sleep(2)
        
        logger.info(f"Starting background quality processing for video {video_id} from file {video_file_path}")
        
        # Get existing metadata
        from .gcs_storage import get_video_metadata
        metadata = get_video_metadata(user_id, video_id)
        
        # Check if quality variants already exist
        if metadata and 'quality_variants' in metadata and metadata['quality_variants']:
            logger.info(f"Video {video_id} already has quality variants, skipping processing")
            return
        
        # Import here to avoid circular imports
        from .video_quality import create_quality_variants
        
        # Create quality variants
        quality_variants = create_quality_variants(video_file_path, user_id, video_id)
        
        # Log result
        if quality_variants:
            available_qualities = list(quality_variants.keys())
            logger.info(f"Successfully created {len(available_qualities)} quality variants for video {video_id}: {', '.join(available_qualities)}")
        else:
            logger.warning(f"No quality variants created for video {video_id}")
        
    except Exception as e:
        logger.error(f"Error in background quality processing: {e}")
        import traceback
        logger.error(traceback.format_exc())