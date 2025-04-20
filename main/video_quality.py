import os
import uuid
import logging
import subprocess
from django.conf import settings
from google.cloud import storage

logger = logging.getLogger(__name__)

# Quality presets with their respective settings
QUALITY_PRESETS = {
    '360p': {
        'resolution': '640x360',
        'bitrate': '800k',
        'audio_bitrate': '96k'
    },
    '720p': {
        'resolution': '1280x720',
        'bitrate': '2500k',
        'audio_bitrate': '128k'
    },
    '1080p': {
        'resolution': '1920x1080',
        'bitrate': '5000k',
        'audio_bitrate': '192k'
    },
    '2160p': {
        'resolution': '3840x2160',
        'bitrate': '12000k',
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
        ffmpeg_path = 'ffmpeg'  # Fallback to system ffmpeg
    return ffmpeg_path

def get_video_info(video_path):
    """Get video information using ffprobe"""
    try:
        ffprobe_path = os.path.join(settings.BASE_DIR, 'ffmpeg', 'bin', 'ffprobe.exe' if os.name == 'nt' else 'ffprobe')
        if not os.path.exists(ffprobe_path):
            ffprobe_path = 'ffprobe'
        
        cmd = [
            ffprobe_path, '-v', 'error', '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height,codec_name,r_frame_rate',
            '-show_entries', 'format=duration', '-of', 'json', video_path
        ]
        
        logger.info(f"Running ffprobe command: {' '.join(cmd)}")
        
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            logger.error(f"ffprobe error: {result.stderr}")
            logger.error(f"ffprobe output: {result.stdout}")
            raise Exception(f"ffprobe exited with code {result.returncode}")
        
        logger.info(f"ffprobe result: {result.stdout}")
        
        import json
        data = json.loads(result.stdout)
        stream_data = data.get('streams', [{}])[0]
        format_data = data.get('format', {})
        
        width = stream_data.get('width')
        height = stream_data.get('height')
        
        logger.info(f"Detected video dimensions: {width}x{height}")
        
        framerate = stream_data.get('r_frame_rate', '30/1')
        if '/' in framerate:
            try:
                num, den = map(int, framerate.split('/'))
                framerate = round(num / den, 2)
            except (ValueError, ZeroDivisionError):
                framerate = 30.0
        else:
            try:
                framerate = float(framerate)
            except ValueError:
                framerate = 30.0
        
        return {
            'width': width,
            'height': height,
            'codec': stream_data.get('codec_name'),
            'duration': float(format_data.get('duration', 0)),
            'framerate': framerate
        }
    except Exception as e:
        logger.error(f"Error getting video info: {str(e)}")
        # Return default values with None for dimensions
        return {'width': None, 'height': None, 'codec': None, 'duration': 0, 'framerate': 30}

def process_video_quality(video_file_path, user_id, video_id, bucket_name):
    """Process video into different quality variants and upload to GCS"""
    logger.info(f"Starting process_video_quality for video_id: {video_id}, input: {video_file_path}")
    quality_paths = {}
    ffmpeg_path = get_ffmpeg_path()
    
    # Get video info to determine which qualities to process
    video_info = get_video_info(video_file_path)
    video_height = video_info.get('height', 0)
    video_width = video_info.get('width', 0)
    
    logger.info(f"Original video dimensions: {video_width}x{video_height}")
    
    # Filter quality presets based on input video resolution
    applicable_qualities = {
        q: p for q, p in QUALITY_PRESETS.items()
        if int(p['resolution'].split('x')[1]) <= video_height
    }
    
    if not applicable_qualities:
        logger.warning(f"No applicable quality presets for video resolution {video_height}p")
        return quality_paths
    
    import tempfile
    temp_dir = tempfile.mkdtemp()
    
    for quality, preset in applicable_qualities.items():
        target_width, target_height = map(int, preset['resolution'].split('x'))
        
        # Create a more reliable scaling filter
        scale_filter = f"scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2:color=black"
        
        output_path = os.path.join(temp_dir, f"{video_id}_{quality}.mp4")
        
        cmd = [
            ffmpeg_path, '-i', video_file_path,
            '-vf', scale_filter,
            '-c:v', 'libx264', '-b:v', preset['bitrate'],
            '-c:a', 'aac', '-b:a', preset['audio_bitrate'],
            '-preset', 'medium', '-y', output_path
        ]
        
        logger.info(f"Running FFmpeg command: {' '.join(cmd)}")
        
        try:
            process = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if process.returncode != 0:
                logger.error(f"FFmpeg error for {quality}: {process.stderr}")
                continue
                
            # Check if output file exists and has size
            if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
                logger.error(f"Output file for {quality} was not created or is empty")
                continue
                
            # Upload to GCS
            from google.cloud import storage
            client = storage.Client()
            bucket = client.bucket(bucket_name)
            
            gcs_path = f"{user_id}/videos/{video_id}_{quality}.mp4"
            blob = bucket.blob(gcs_path)
            blob.upload_from_filename(output_path, content_type='video/mp4')
            
            logger.info(f"Successfully created {quality} variant at {gcs_path}")
            quality_paths[quality] = gcs_path
            
            # Clean up temporary file
            try:
                os.remove(output_path)
            except Exception as e:
                logger.warning(f"Could not remove temporary file {output_path}: {e}")
                
        except Exception as e:
            logger.error(f"Error processing {quality}: {str(e)}")
    
    # Clean up temp directory
    try:
        os.rmdir(temp_dir)
    except Exception as e:
        logger.warning(f"Could not remove temp directory {temp_dir}: {e}")
    
    return quality_paths

def create_quality_variants(video_file_path, user_id, video_id):
    """Create quality variants for a video and update its metadata"""
    from .gcs_storage import get_bucket, get_video_metadata, BUCKET_NAME
    import json
    import os
    import tempfile
    import subprocess
    
    logger.info(f"Processing quality variants for video {video_id}")
    
    try:
        # Get video info to determine which qualities to process
        video_info = get_video_info(video_file_path)
        video_height = video_info.get('height', 0)
        video_width = video_info.get('width', 0)
        
        logger.info(f"Original video dimensions: {video_width}x{video_height}")
        
        # Filter quality presets based on input video resolution
        applicable_qualities = {
            q: p for q, p in QUALITY_PRESETS.items()
            if int(p['resolution'].split('x')[1]) <= video_height
        }
        
        if not applicable_qualities:
            logger.warning(f"No applicable quality presets for video resolution {video_height}p")
            return {}
            
        # Get GCS bucket
        bucket = get_bucket(BUCKET_NAME)
        if not bucket:
            logger.error(f"Could not get bucket {BUCKET_NAME}")
            raise RuntimeError(f"Could not get bucket {BUCKET_NAME}")
            
        # Create temporary directory for processed videos
        temp_dir = tempfile.mkdtemp()
        
        # Process each quality variant
        quality_variants = {}
        for quality, preset in applicable_qualities.items():
            logger.info(f"Processing {quality} variant for video {video_id}")
            
            try:
                # Set output path for processed video
                output_path = os.path.join(temp_dir, f"{video_id}_{quality}.mp4")
                
                # Calculate aspect ratio to maintain proportions
                target_width, target_height = map(int, preset['resolution'].split('x'))
                
                # Use a simplified scale filter that maintains aspect ratio
                scale_filter = f"scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2:color=black"
                
                # Process video to target quality
                ffmpeg_path = get_ffmpeg_path()
                cmd = [
                    ffmpeg_path, '-i', video_file_path,
                    '-vf', scale_filter,
                    '-c:v', 'libx264', '-b:v', preset['bitrate'],
                    '-c:a', 'aac', '-b:a', preset['audio_bitrate'],
                    '-preset', 'medium', '-y', output_path
                ]
                
                logger.info(f"Running FFmpeg command: {' '.join(cmd)}")
                
                process = subprocess.run(cmd, capture_output=True, text=True, check=False)
                
                if process.returncode != 0:
                    logger.error(f"FFmpeg error for {quality}: {process.stderr}")
                    continue
                    
                # Check if the output file exists and has size
                if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
                    logger.error(f"Output file for {quality} was not created or is empty")
                    continue
                
                # Upload processed video to GCS
                target_path = f"{user_id}/videos/{video_id}_{quality}.mp4"
                blob = bucket.blob(target_path)
                blob.upload_from_filename(output_path, content_type='video/mp4')
                
                # Add to quality variants
                quality_variants[quality] = {
                    'path': target_path,
                    'resolution': preset['resolution'],
                    'bitrate': preset['bitrate']
                }
                
                logger.info(f"Successfully created and uploaded {quality} variant for video {video_id}")
                
                # Clean up temporary file
                try:
                    if os.path.exists(output_path):
                        os.remove(output_path)
                except Exception as e:
                    logger.warning(f"Could not remove temporary file {output_path}: {e}")
                
            except Exception as e:
                logger.error(f"Error processing {quality} variant: {str(e)}")
        
        # Clean up temp directory
        try:
            os.rmdir(temp_dir)
        except Exception as e:
            logger.warning(f"Could not remove temp directory {temp_dir}: {e}")
        
        if not quality_variants:
            logger.warning(f"No quality variants were successfully created for video {video_id}")
            return {}
            
        # Get existing metadata
        metadata = get_video_metadata(user_id, video_id)
        if not metadata:
            logger.error(f"Could not get metadata for video {video_id}")
            raise RuntimeError(f"Could not get metadata for video {video_id}")
        
        # Update metadata
        metadata['quality_variants'] = quality_variants
        metadata['available_qualities'] = list(quality_variants.keys())
        if quality_variants:
            metadata['highest_quality'] = max(quality_variants.keys(), key=lambda q: int(q.rstrip('p')))
        
        # Upload updated metadata
        metadata_path = f"{user_id}/metadata/{video_id}.json"
        metadata_blob = bucket.blob(metadata_path)
        metadata_blob.upload_from_string(json.dumps(metadata, indent=2), content_type='application/json')
        
        logger.info(f"Updated metadata with quality variants for video {video_id}")
        return quality_variants
    
    except Exception as e:
        logger.error(f"Error creating quality variants for video {video_id}: {str(e)}")
        return {}