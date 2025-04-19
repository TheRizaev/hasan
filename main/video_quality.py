import os
import uuid
import logging
import subprocess
from django.conf import settings

logger = logging.getLogger(__name__)

# Quality presets with their respective settings
QUALITY_PRESETS = {
    '240p': {
        'resolution': '426x240',
        'bitrate': '400k',
        'audio_bitrate': '64k'
    },
    '360p': {
        'resolution': '640x360',
        'bitrate': '700k',
        'audio_bitrate': '96k'
    },
    '480p': {
        'resolution': '854x480',
        'bitrate': '1500k',
        'audio_bitrate': '128k'
    },
    '720p': {
        'resolution': '1280x720',
        'bitrate': '3000k',
        'audio_bitrate': '192k'
    },
    '1080p': {
        'resolution': '1920x1080',
        'bitrate': '6000k',
        'audio_bitrate': '256k'
    }
}

def get_ffmpeg_path():
    """Get the path to the ffmpeg executable"""
    if os.name == 'nt':  # Windows
        ffmpeg_path = os.path.join(settings.BASE_DIR, 'ffmpeg', 'bin', 'ffmpeg.exe')
    else:  # Unix/Linux
        ffmpeg_path = os.path.join(settings.BASE_DIR, 'ffmpeg', 'bin', 'ffmpeg')
    
    if not os.path.exists(ffmpeg_path):
        logger.error(f"ffmpeg not found at {ffmpeg_path}")
        # Try to use system ffmpeg
        ffmpeg_path = 'ffmpeg'
    
    return ffmpeg_path

def get_video_info(video_path):
    """
    Get video information using ffprobe
    
    Returns:
        dict: Video info including height, width, duration, etc.
    """
    try:
        # Get path to ffprobe executable
        if os.name == 'nt':  # Windows
            ffprobe_path = os.path.join(settings.BASE_DIR, 'ffmpeg', 'bin', 'ffprobe.exe')
        else:  # Unix/Linux
            ffprobe_path = os.path.join(settings.BASE_DIR, 'ffmpeg', 'bin', 'ffprobe')
        
        if not os.path.exists(ffprobe_path):
            logger.error(f"ffprobe not found at {ffprobe_path}")
            # Try to use system ffprobe
            ffprobe_path = 'ffprobe'
        
        # Run ffprobe command
        cmd = [
            ffprobe_path,
            '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height,codec_name,r_frame_rate',
            '-show_entries', 'format=duration',
            '-of', 'json',
            video_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.error(f"ffprobe error: {result.stderr}")
            raise Exception(f"ffprobe exited with code {result.returncode}: {result.stderr}")
        
        import json
        data = json.loads(result.stdout)
        
        # Extract relevant information
        stream_data = data.get('streams', [{}])[0]
        format_data = data.get('format', {})
        
        # Parse framerate which is returned as a fraction (e.g., "30000/1001")
        framerate = stream_data.get('r_frame_rate', '30/1')
        if '/' in framerate:
            num, den = map(int, framerate.split('/'))
            framerate = round(num / den, 2)
        else:
            framerate = float(framerate)
        
        return {
            'width': stream_data.get('width'),
            'height': stream_data.get('height'),
            'codec': stream_data.get('codec_name'),
            'duration': float(format_data.get('duration', 0)),
            'framerate': framerate
        }
    
    except Exception as e:
        logger.error(f"Error getting video info: {str(e)}")
        return {
            'width': None,
            'height': None,
            'codec': None,
            'duration': 0,
            'framerate': 30  # Default framerate
        }

def process_video_quality(input_path, output_dir, max_height=1080):
    """
    Process video into multiple quality variants
    
    Args:
        input_path (str): Path to the original video file
        output_dir (str): Directory to save the processed videos
        max_height (int): Maximum height to process (default: 1080p)
    
    Returns:
        dict: Paths to the processed video files for each quality
    """
    try:
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Get video info to determine original resolution
        video_info = get_video_info(input_path)
        original_height = video_info.get('height', 0) or 1080
        
        # Only process qualities up to the original video resolution
        available_qualities = {}
        
        # Get the path to ffmpeg
        ffmpeg_path = get_ffmpeg_path()
        
        # Process each quality preset
        for quality, settings in QUALITY_PRESETS.items():
            # Extract height from the resolution (e.g., 1920x1080 -> 1080)
            quality_height = int(settings['resolution'].split('x')[1])
            
            # Skip if quality is higher than original or max requested height
            if quality_height > original_height or quality_height > max_height:
                continue
            
            # Output filename
            output_filename = f"{os.path.splitext(os.path.basename(input_path))[0]}_{quality}.mp4"
            output_path = os.path.join(output_dir, output_filename)
            
            # ffmpeg command for this quality
            cmd = [
                ffmpeg_path,
                '-i', input_path,
                '-vf', f"scale={settings['resolution']}:force_original_aspect_ratio=decrease,pad={settings['resolution']}:-1:-1:color=black",
                '-c:v', 'libx264',
                '-b:v', settings['bitrate'],
                '-c:a', 'aac',
                '-b:a', settings['audio_bitrate'],
                '-preset', 'medium',  # Balance between speed and quality
                '-movflags', '+faststart',  # Optimize for web streaming
                '-y',  # Overwrite output file if exists
                output_path
            ]
            
            logger.info(f"Processing {quality} version: {' '.join(cmd)}")
            
            # Run ffmpeg command
            process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            
            # Monitor progress
            while True:
                output = process.stderr.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    logger.debug(output.strip())
            
            # Get return code
            return_code = process.poll()
            
            if return_code == 0:
                # Success
                available_qualities[quality] = output_path
                logger.info(f"Successfully created {quality} version at {output_path}")
            else:
                # Error
                logger.error(f"Error creating {quality} version: {process.stderr.read()}")
        
        return available_qualities
    
    except Exception as e:
        logger.error(f"Error processing video qualities: {str(e)}")
        return {}

def create_quality_variants(video_file_path, user_id, video_id):
    """
    Create quality variants for a video and update its metadata
    
    Args:
        video_file_path (str): Path to the original video file
        user_id (str): User ID
        video_id (str): Video ID
    
    Returns:
        dict: Quality variants information
    """
    try:
        from .gcs_storage import get_bucket, get_video_metadata, BUCKET_NAME
        
        # Create temporary directory for processing
        temp_dir = os.path.join(settings.MEDIA_ROOT, 'temp', str(uuid.uuid4()))
        os.makedirs(temp_dir, exist_ok=True)
        
        logger.info(f"Processing quality variants for video {video_id} in {temp_dir}")
        
        # Process video into different qualities
        quality_paths = process_video_quality(video_file_path, temp_dir)
        
        if not quality_paths:
            logger.warning(f"No quality variants created for video {video_id}")
            return None
        
        # Upload each quality variant to GCS
        bucket = get_bucket(BUCKET_NAME)
        if not bucket:
            logger.error(f"Could not get bucket {BUCKET_NAME}")
            return None
        
        quality_variants = {}
        
        # Get the metadata to update
        metadata = get_video_metadata(user_id, video_id)
        if not metadata:
            logger.error(f"Could not get metadata for video {video_id}")
            return None
        
        # Upload each quality variant
        for quality, file_path in quality_paths.items():
            try:
                # Define the path in GCS
                gcs_path = f"{user_id}/videos/{video_id}_{quality}.mp4"
                
                # Upload the file
                blob = bucket.blob(gcs_path)
                blob.upload_from_filename(file_path, content_type='video/mp4')
                
                # Add to variants
                quality_variants[quality] = {
                    'path': gcs_path,
                    'resolution': QUALITY_PRESETS[quality]['resolution'],
                    'bitrate': QUALITY_PRESETS[quality]['bitrate']
                }
                
                logger.info(f"Uploaded {quality} variant to {gcs_path}")
                
                # Remove temporary file
                os.remove(file_path)
            except Exception as e:
                logger.error(f"Error uploading {quality} variant: {str(e)}")
        
        # Update metadata with quality variants
        if quality_variants:
            metadata['quality_variants'] = quality_variants
            
            # Update highest quality available
            available_qualities = list(quality_variants.keys())
            metadata['highest_quality'] = max(available_qualities, key=lambda q: int(q.rstrip('p')))
            
            # Upload updated metadata
            metadata_path = f"{user_id}/metadata/{video_id}.json"
            metadata_blob = bucket.blob(metadata_path)
            
            import json
            metadata_blob.upload_from_string(json.dumps(metadata, indent=2), content_type='application/json')
            
            logger.info(f"Updated metadata with quality variants for video {video_id}")
        
        # Clean up temp directory
        try:
            os.rmdir(temp_dir)
        except:
            pass
        
        return quality_variants
    
    except Exception as e:
        logger.error(f"Error creating quality variants: {str(e)}")
        return None