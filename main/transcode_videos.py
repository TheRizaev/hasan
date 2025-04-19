"""
Django management command to transcode videos.
Can be run manually or as a scheduled task.
"""

import os
import json
import logging
import tempfile
from django.core.management.base import BaseCommand
from django.conf import settings
from main.gcs_storage import get_bucket, BUCKET_NAME, get_video_metadata
from main.video_transcoder import transcode_to_quality, get_video_info

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Transcode videos to different quality levels'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--user',
            help='Process videos for specific user (with @ prefix)',
        )
        parser.add_argument(
            '--video',
            help='Process specific video ID',
        )
        parser.add_argument(
            '--quality',
            choices=['240p', '360p', '480p', '720p', '1080p', 'all'],
            default='all',
            help='Quality to transcode to',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=10,
            help='Maximum number of videos to process',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force transcoding even if quality already exists',
        )
        
    def handle(self, *args, **options):
        user_filter = options['user']
        video_filter = options['video']
        quality = options['quality']
        limit = options['limit']
        force = options['force']
        
        self.stdout.write(self.style.NOTICE('Starting video transcoding...'))
        
        # Get bucket
        bucket = get_bucket(BUCKET_NAME)
        if not bucket:
            self.stdout.write(self.style.ERROR('Failed to get GCS bucket'))
            return
            
        # Find videos to transcode
        videos_to_process = self.find_videos_to_transcode(bucket, user_filter, video_filter, limit)
        
        if not videos_to_process:
            self.stdout.write(self.style.WARNING('No videos found to transcode'))
            return
            
        self.stdout.write(self.style.SUCCESS(f'Found {len(videos_to_process)} videos to process'))
        
        # Process each video
        for video_info in videos_to_process:
            self.transcode_video(bucket, video_info, quality, force)
            
        self.stdout.write(self.style.SUCCESS('Transcoding completed'))
    
    def find_videos_to_transcode(self, bucket, user_filter=None, video_filter=None, limit=10):
        """Find videos that need transcoding based on filters"""
        videos_to_process = []
        
        try:
            # If specific video is requested
            if user_filter and video_filter:
                metadata = get_video_metadata(user_filter, video_filter)
                if metadata:
                    videos_to_process.append({
                        'user_id': user_filter,
                        'video_id': video_filter,
                        'metadata': metadata
                    })
                return videos_to_process
                
            # If only user filter is provided
            if user_filter:
                prefix = f"{user_filter}/metadata/"
                blobs = list(bucket.list_blobs(prefix=prefix))
                
                for blob in blobs:
                    if blob.name.endswith('.json'):
                        try:
                            metadata = json.loads(blob.download_as_text())
                            video_id = metadata.get('video_id')
                            if video_id:
                                videos_to_process.append({
                                    'user_id': user_filter,
                                    'video_id': video_id,
                                    'metadata': metadata
                                })
                        except Exception as e:
                            logger.error(f"Error processing metadata {blob.name}: {e}")
                
                # Limit number of videos
                return videos_to_process[:limit]
            
            # If no filters, scan all users
            blobs = bucket.list_blobs(delimiter='/')
            prefixes = list(blobs.prefixes)
            users = [prefix.replace('/', '') for prefix in prefixes 
                    if not prefix.startswith('system/')]
                    
            # For each user, find videos that need transcoding
            for user_id in users:
                # Skip if not a valid user folder (must start with @)
                if not user_id.startswith('@'):
                    continue
                    
                # Find metadata files
                prefix = f"{user_id}/metadata/"
                metadata_blobs = list(bucket.list_blobs(prefix=prefix))
                
                user_videos = []
                for blob in metadata_blobs:
                    if blob.name.endswith('.json'):
                        try:
                            metadata = json.loads(blob.download_as_text())
                            video_id = metadata.get('video_id')
                            
                            # Check if video needs transcoding (has no available_qualities)
                            if video_id and (
                                'available_qualities' not in metadata or 
                                len(metadata['available_qualities']) < 3  # Less than 3 qualities
                            ):
                                user_videos.append({
                                    'user_id': user_id,
                                    'video_id': video_id,
                                    'metadata': metadata
                                })
                        except Exception as e:
                            logger.error(f"Error processing metadata {blob.name}: {e}")
                
                # Add videos for this user, up to our limit
                remaining = limit - len(videos_to_process)
                videos_to_process.extend(user_videos[:remaining])
                
                if len(videos_to_process) >= limit:
                    break
            
            return videos_to_process
                
        except Exception as e:
            logger.error(f"Error finding videos to transcode: {e}")
            return []
            
    def transcode_video(self, bucket, video_info, quality_option, force=False):
        """Transcode a video to the specified quality"""
        user_id = video_info['user_id']
        video_id = video_info['video_id']
        metadata = video_info['metadata']
        
        self.stdout.write(f"Processing video {video_id} for user {user_id}")
        
        # Get original video path
        original_path = metadata.get('file_path')
        if not original_path:
            self.stdout.write(self.style.ERROR(f"No file path found for video {video_id}"))
            return
            
        # Get available qualities
        available_qualities = metadata.get('available_qualities', [])
        
        # Determine qualities to generate
        qualities_to_generate = []
        if quality_option == 'all':
            # Select qualities based on original resolution
            original_height = metadata.get('height', 0)
            
            if original_height >= 1080:
                qualities_to_generate = ['480p', '720p', '1080p']
            elif original_height >= 720:
                qualities_to_generate = ['360p', '480p', '720p']
            elif original_height >= 480:
                qualities_to_generate = ['240p', '360p', '480p']
            elif original_height >= 360:
                qualities_to_generate = ['240p', '360p']
            else:
                qualities_to_generate = ['240p']
        else:
            qualities_to_generate = [quality_option]
        
        # Filter out qualities that already exist unless force is True
        if not force:
            qualities_to_generate = [q for q in qualities_to_generate if q not in available_qualities]
            
        if not qualities_to_generate:
            self.stdout.write(self.style.SUCCESS(f"No new qualities to generate for {video_id}"))
            return
            
        self.stdout.write(f"Generating qualities: {', '.join(qualities_to_generate)}")
        
        # Download original video to temp file
        original_blob = bucket.blob(original_path)
        if not original_blob.exists():
            self.stdout.write(self.style.ERROR(f"Original video not found at {original_path}"))
            return
            
        # Create temp directory for processing
        with tempfile.TemporaryDirectory() as temp_dir:
            # Download original video
            local_input_path = os.path.join(temp_dir, f"original_{video_id}.mp4")
            self.stdout.write(f"Downloading original video...")
            original_blob.download_to_filename(local_input_path)
            
            # Get video info with ffprobe
            video_info = get_video_info(local_input_path)
            if not video_info:
                self.stdout.write(self.style.ERROR(f"Could not get video info for {video_id}"))
                return
                
            # Process each quality
            for quality in qualities_to_generate:
                try:
                    self.stdout.write(f"Transcoding to {quality}...")
                    
                    # Set output path for transcoded video
                    local_output_path = os.path.join(temp_dir, f"{video_id}_{quality}.mp4")
                    
                    # Transcode video
                    success = transcode_to_quality(local_input_path, local_output_path, quality)
                    
                    if not success:
                        self.stdout.write(self.style.ERROR(f"Failed to transcode {video_id} to {quality}"))
                        continue
                        
                    # Upload transcoded video to GCS
                    transcoded_path = f"{user_id}/videos/{video_id}_{quality}.mp4"
                    transcoded_blob = bucket.blob(transcoded_path)
                    
                    self.stdout.write(f"Uploading {quality} version...")
                    transcoded_blob.upload_from_filename(
                        local_output_path, 
                        content_type='video/mp4'
                    )
                    
                    # Update available qualities in metadata
                    if quality not in available_qualities:
                        available_qualities.append(quality)
                        
                    self.stdout.write(self.style.SUCCESS(f"Successfully processed {quality} version"))
                    
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"Error transcoding to {quality}: {e}"))
            
            # Update metadata with new available qualities
            metadata['available_qualities'] = available_qualities
            metadata_path = f"{user_id}/metadata/{video_id}.json"
            metadata_blob = bucket.blob(metadata_path)
            
            self.stdout.write(f"Updating metadata with new qualities: {available_qualities}")
            metadata_blob.upload_from_string(
                json.dumps(metadata, indent=2), 
                content_type='application/json'
            )
            
            self.stdout.write(self.style.SUCCESS(f"Completed processing video {video_id}"))