from django.core.management.base import BaseCommand, CommandError
import os
import tempfile
import logging
from django.conf import settings
import sys

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Process video qualities for existing videos in Google Cloud Storage'

    def add_arguments(self, parser):
        parser.add_argument('--user', type=str, help='Process videos only for specific user (with @ prefix)')
        parser.add_argument('--video-id', type=str, help='Process specific video ID')
        parser.add_argument('--max-videos', type=int, default=None, help='Maximum number of videos to process')
        parser.add_argument('--force', action='store_true', help='Force re-processing videos that already have quality variants')
        parser.add_argument('--dry-run', action='store_true', help='Show what would be processed without actually processing')

    def handle(self, *args, **options):
        from main.gcs_storage import get_bucket, BUCKET_NAME, get_video_metadata
        from main.video_quality import create_quality_variants
        
        specific_user = options.get('user')
        specific_video = options.get('video_id')
        max_videos = options.get('max_videos')
        force = options.get('force')
        dry_run = options.get('dry_run')
        
        # Setup logging
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        
        # Get GCS bucket
        bucket = get_bucket(BUCKET_NAME)
        if not bucket:
            raise CommandError(f"Could not get bucket {BUCKET_NAME}")
        
        # Create temporary directory for video downloads
        temp_dir = tempfile.mkdtemp(prefix='video_quality_')
        
        try:
            # Get list of users (or specific user)
            if specific_user:
                users = [specific_user]
                self.stdout.write(f"Processing videos for user: {specific_user}")
            else:
                # Get all users in bucket
                blobs = bucket.list_blobs(delimiter='/')
                users = [prefix.rstrip('/') for prefix in blobs.prefixes if prefix.startswith('@')]
                self.stdout.write(f"Found {len(users)} users")
            
            # Keep track of processed videos
            processed_count = 0
            skipped_count = 0
            
            # Process each user's videos
            for user_id in users:
                self.stdout.write(f"Processing user: {user_id}")
                
                # Get list of videos for this user
                if specific_video:
                    videos_to_process = [specific_video]
                else:
                    # List all video metadata files
                    metadata_prefix = f"{user_id}/metadata/"
                    metadata_blobs = list(bucket.list_blobs(prefix=metadata_prefix))
                    videos_to_process = []
                    
                    for blob in metadata_blobs:
                        if blob.name.endswith('.json'):
                            video_id = os.path.splitext(os.path.basename(blob.name))[0]
                            videos_to_process.append(video_id)
                    
                    self.stdout.write(f"Found {len(videos_to_process)} videos for user {user_id}")
                
                # Process each video
                for video_id in videos_to_process:
                    # Check if we've reached the max videos limit
                    if max_videos is not None and processed_count >= max_videos:
                        self.stdout.write(f"Reached maximum of {max_videos} videos to process")
                        break
                    
                    # Get video metadata
                    metadata = get_video_metadata(user_id, video_id)
                    if not metadata:
                        self.stdout.write(self.style.WARNING(f"Could not find metadata for video {video_id}"))
                        skipped_count += 1
                        continue
                    
                    # Check if video already has quality variants (unless force is specified)
                    if not force and metadata.get('quality_variants'):
                        self.stdout.write(f"Skipping video {video_id} - already has quality variants")
                        skipped_count += 1
                        continue
                    
                    # Get the original video file path
                    file_path = metadata.get('file_path')
                    if not file_path:
                        self.stdout.write(self.style.WARNING(f"No file path found in metadata for video {video_id}"))
                        skipped_count += 1
                        continue
                    
                    # In dry run mode, just report what would be processed
                    if dry_run:
                        self.stdout.write(f"Would process video {video_id} (user: {user_id}, path: {file_path})")
                        processed_count += 1
                        continue
                    
                    try:
                        # Download the video to a temp file
                        blob = bucket.blob(file_path)
                        if not blob.exists():
                            self.stdout.write(self.style.WARNING(f"Video file not found in GCS: {file_path}"))
                            skipped_count += 1
                            continue
                        
                        temp_video_path = os.path.join(temp_dir, f"{video_id}_{os.path.basename(file_path)}")
                        blob.download_to_filename(temp_video_path)
                        
                        self.stdout.write(f"Processing video {video_id} (file: {os.path.basename(file_path)})")
                        
                        # Process video qualities
                        quality_variants = create_quality_variants(temp_video_path, user_id, video_id)
                        
                        # Delete the temp file
                        os.remove(temp_video_path)
                        
                        if quality_variants:
                            available_qualities = list(quality_variants.keys())
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f"Successfully processed video {video_id} with qualities: {', '.join(available_qualities)}"
                                )
                            )
                            processed_count += 1
                        else:
                            self.stdout.write(self.style.WARNING(f"No quality variants created for video {video_id}"))
                            skipped_count += 1
                    
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"Error processing video {video_id}: {str(e)}"))
                        skipped_count += 1
                        # Clean up the temp file if it exists
                        if os.path.exists(temp_video_path):
                            os.remove(temp_video_path)
            
            # Summary
            if dry_run:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Dry run completed. Would process {processed_count} videos. Would skip {skipped_count} videos."
                    )
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Processing completed. Processed {processed_count} videos. Skipped {skipped_count} videos."
                    )
                )
        
        finally:
            # Clean up temporary directory
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)