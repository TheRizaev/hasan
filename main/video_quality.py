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
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"ffprobe error: {result.stderr}")
            raise Exception(f"ffprobe exited with code {result.returncode}")
        
        import json
        data = json.loads(result.stdout)
        stream_data = data.get('streams', [{}])[0]
        format_data = data.get('format', {})
        
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
        return {'width': None, 'height': None, 'codec': None, 'duration': 0, 'framerate': 30}

def process_video_quality(video_file_path, user_id, video_id, bucket_name):
    """Process video into different quality variants and upload to GCS"""
    logger.info(f"Starting process_video_quality for video_id: {video_id}, input: {video_file_path}")
    quality_paths = {}
    ffmpeg_path = get_ffmpeg_path()
    
    # Get video info to determine which qualities to process
    video_info = get_video_info(video_file_path)
    video_height = video_info.get('height', 0)
    
    # Filter quality presets based on input video resolution
    applicable_qualities = {
        q: p for q, p in QUALITY_PRESETS.items()
        if int(p['resolution'].split('x')[1]) <= video_height
    }
    
    if not applicable_qualities:
        logger.warning(f"No applicable quality presets for video resolution {video_height}p")
        return quality_paths
    
    for quality, preset in applicable_qualities.items():
        output_path = f"gs://{bucket_name}/{user_id}/videos/{video_id}_{quality}.mp4"
        cmd = [
            ffmpeg_path, '-i', video_file_path,
            '-vf', f"scale={preset['resolution']}:force_original_aspect_ratio=decrease,pad={preset['resolution']}:(ow-iw)/2:(oh-ih)/2",
            '-c:v', 'libx264', '-b:v', preset['bitrate'],
            '-c:a', 'aac', '-b:a', preset['audio_bitrate'],
            '-preset', 'medium', '-y', output_path
        ]
        logger.info(f"Running FFmpeg command: {' '.join(cmd)}")
        
        try:
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            stdout, stderr = process.communicate()
            if process.returncode == 0:
                logger.info(f"Successfully created {quality} variant at {output_path}")
                quality_paths[quality] = output_path
            else:
                logger.error(f"FFmpeg failed for {quality}: {stderr}")
        except Exception as e:
            logger.error(f"Error processing {quality}: {str(e)}")
    
    return quality_paths

def create_quality_variants(video_file_path, user_id, video_id):
    """Create quality variants for a video and update its metadata"""
    from .gcs_storage import get_bucket, get_video_metadata, BUCKET_NAME
    import json
    
    logger.info(f"Processing quality variants for video {video_id}")
    
    try:
        # Process video qualities
        quality_paths = process_video_quality(video_file_path, user_id, video_id, BUCKET_NAME)
        if not quality_paths:
            logger.error(f"No quality variants created for video {video_id}")
            raise RuntimeError("Failed to create quality variants")
        
        # Get GCS bucket
        bucket = get_bucket(BUCKET_NAME)
        if not bucket:
            logger.error(f"Could not get bucket {BUCKET_NAME}")
            raise RuntimeError(f"Could not get bucket {BUCKET_NAME}")
        
        # Get existing metadata
        metadata = get_video_metadata(user_id, video_id)
        if not metadata:
            logger.error(f"Could not get metadata for video {video_id}")
            raise RuntimeError(f"Could not get metadata for video {video_id}")
        
        # Populate quality variants
        quality_variants = {}
        for quality, gcs_path in quality_paths.items():
            quality_variants[quality] = {
                'path': gcs_path,
                'resolution': QUALITY_PRESETS[quality]['resolution'],
                'bitrate': QUALITY_PRESETS[quality]['bitrate']
            }
        
        # Update metadata
        metadata['quality_variants'] = quality_variants
        metadata['available_qualities'] = list(quality_variants.keys())
        metadata['highest_quality'] = max(quality_variants.keys(), key=lambda q: int(q.rstrip('p')))
        
        # Upload updated metadata
        metadata_path = f"{user_id}/metadata/{video_id}.json"
        metadata_blob = bucket.blob(metadata_path)
        metadata_blob.upload_from_string(json.dumps(metadata, indent=2), content_type='application/json')
        
        logger.info(f"Updated metadata with quality variants for video {video_id}")
        return quality_variants
    
    except Exception as e:
        logger.error(f"Error creating quality variants for video {video_id}: {str(e)}")
        raise