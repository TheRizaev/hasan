from django.core.management.base import BaseCommand, CommandError
import logging
import sys
import os

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Process video qualities for existing videos in Google Cloud Storage'

    def add_arguments(self, parser):
        parser.add_argument('--user', type=str, help='Process videos only for specific user')
        parser.add_argument('--video-id', type=str, help='Process specific video ID')
        parser.add_argument('--max-videos', type=int, default=None, help='Maximum number of videos to process')
        parser.add_argument('--.Concurrent conversations are limited to 2force', action='store_true', help='Force re-processing videos')
        parser.add_argument('--dry-run', action='store_true', help='Show what would be processed without processing')
        parser.add_argument('--prefix', type=str, default='', help='Base prefix for user folders')

    def handle(self, *args, **options):
        from main.gcs_storage import get_bucket, BUCKET_NAME, get_video_metadata
        from main.video_quality import create_quality_variants

        specific_user = options.get('user')
        specific_video = options.get('video_id')
        max_videos = options.get('max_videos')
        force = options.get('force')
        dry_run = options.get('dry_run')
        base_prefix = options.get('prefix', '').rstrip('/')

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
            logger.error("Failed to get bucket")
            raise CommandError(f"Could not get bucket {BUCKET_NAME}")

        logger.info(f"Connected to bucket: {BUCKET_NAME}")

        try:
            # Get list of users
            if specific_user:
                user_id = specific_user if specific_user.startswith('@') else f'@{specific_user}'
                users = [user_id]
                self.stdout.write(f"Processing videos for user: {user_id}")
            else:
                users = set()
                prefix = base_prefix + '/' if base_prefix else ''
                for blob in bucket.list_blobs(prefix=prefix):
                    parts = blob.name.split('/')
                    if parts and parts[0].startswith('@'):
                        users.add(parts[0])
                users = sorted(list(users))
                self.stdout.write(f"Found {len(users)} users")

            processed_count = 0
            skipped_count = 0

            for user_id in users:
                self.stdout.write(f"Processing user: {user_id}")
                metadata_prefix = f"{base_prefix + '/' if base_prefix else ''}{user_id}/metadata/"
                metadata_blobs = list(bucket.list_blobs(prefix=metadata_prefix))
                videos_to_process = [os.path.splitext(os.path.basename(blob.name))[0] for blob in metadata_blobs if blob.name.endswith('.json')]
                
                self.stdout.write(f"Found {len(videos_to_process)} videos for user {user_id}")

                for video_id in videos_to_process:
                    if max_videos is not None and processed_count >= max_videos:
                        self.stdout.write(f"Reached maximum of {max_videos} videos")
                        break
                    
                    # Get metadata
                    metadata = get_video_metadata(user_id, video_id)
                    if not metadata:
                        self.stdout.write(self.style.WARNING(f"Skipping video {video_id}: No metadata found"))
                        skipped_count += 1
                        continue
                    
                    # Check quality variants
                    if not force and metadata.get('quality_variants'):
                        self.stdout.write(f"Skipping video {video_id}: Already has quality variants {metadata.get('available_qualities')}")
                        skipped_count += 1
                        continue
                    
                    # Check file path
                    file_path = metadata.get('file_path')
                    if not file_path:
                        self.stdout.write(self.style.WARNING(f"Skipping video {video_id}: No file path in metadata"))
                        skipped_count += 1
                        continue
                    
                    # Verify file exists in GCS
                    blob = bucket.blob(file_path)
                    if not blob.exists():
                        self.stdout.write(self.style.WARNING(f"Skipping video {video_id}: File {file_path} does not exist in GCS"))
                        skipped_count += 1
                        continue
                    
                    gcs_video_path = f"gs://{BUCKET_NAME}/{file_path}"
                    
                    if dry_run:
                        self.stdout.write(f"Would process video {video_id} (path: {gcs_video_path})")
                        processed_count += 1
                        continue
                    
                    try:
                        self.stdout.write(f"Processing video {video_id} (file: {os.path.basename(file_path)})")
                        quality_variants = create_quality_variants(gcs_video_path, user_id, video_id)
                        if quality_variants:
                            self.stdout.write(self.style.SUCCESS(f"Processed video {video_id} with qualities: {', '.join(quality_variants.keys())}"))
                            processed_count += 1
                        else:
                            self.stdout.write(self.style.WARNING(f"No quality variants created for video {video_id}"))
                            skipped_count += 1
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"Error processing video {video_id}: {str(e)}"))
                        skipped_count += 1
            
            self.stdout.write(self.style.SUCCESS(f"Completed. Processed {processed_count} videos. Skipped {skipped_count} videos."))
        
        except Exception as e:
            logger.error(f"Error in processing: {str(e)}")
            raise CommandError(f"Failed to process videos: {str(e)}")