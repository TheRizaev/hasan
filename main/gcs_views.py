from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib import messages
from .models import Category, Video
from django.views.decorators.http import require_http_methods
from django.conf import settings
import os
from .gcs_storage import upload_video_with_quality_processing, get_video_metadata, upload_thumbnail, generate_video_url, get_video_url_with_quality, BUCKET_NAME
from .video_quality_processor import process_video_quality_async
import json
from datetime import datetime, timedelta
import uuid
import tempfile
import logging
import random
logger = logging.getLogger(__name__)

from .gcs_storage import (
    create_user_folder_structure,
    upload_video,
    upload_thumbnail,
    get_video_metadata,
    generate_video_url,
    delete_video,
    get_bucket,
    BUCKET_NAME,
    get_user_profile_from_gcs
)

@login_required
@require_http_methods(["POST"])
def upload_video_to_gcs(request):
    """
    Handler for uploading videos to Google Cloud Storage with quality processing
    """
    try:
        # Get files and data from request
        video_file = request.FILES.get('video_file')
        thumbnail = request.FILES.get('thumbnail')
        title = request.POST.get('title')
        description = request.POST.get('description', '')
        category_id = request.POST.get('category')
        process_qualities = request.POST.get('process_qualities', 'true').lower() == 'true'
        
        if not video_file or not title:
            return JsonResponse({'error': 'Video and title are required'}, status=400)
        
        # Create temp directory if it doesn't exist
        temp_dir = os.path.join(settings.MEDIA_ROOT, 'temp')
        os.makedirs(temp_dir, exist_ok=True)
        
        # Get username for GCS storage (preserve @ prefix)
        username = request.user.username
        user_id = f"@{username}" if not username.startswith('@') else username
        
        # Temporarily save video file on server
        temp_video_path = os.path.join(temp_dir, f"{uuid.uuid4()}_{video_file.name}")
        with open(temp_video_path, 'wb+') as destination:
            for chunk in video_file.chunks():
                destination.write(chunk)
        
        # Upload video to GCS
        video_id = upload_video_with_quality_processing(
            user_id=user_id,
            video_file_path=temp_video_path,
            title=title,
            description=description,
            process_qualities=False  # We'll handle quality processing separately
        )
        
        # If video upload failed
        if not video_id:
            if os.path.exists(temp_video_path):
                os.remove(temp_video_path)
            return JsonResponse({'error': 'Failed to upload video to Google Cloud Storage'}, status=500)
        
        # Get the GCS path of the uploaded video
        metadata = get_video_metadata(user_id, video_id)
        if not metadata or 'file_path' not in metadata:
            if os.path.exists(temp_video_path):
                os.remove(temp_video_path)
            return JsonResponse({'error': 'Failed to retrieve video metadata'}, status=500)
        
        gcs_video_path = f"gs://{BUCKET_NAME}/{metadata['file_path']}"
        
        # Handle thumbnail if present
        thumbnail_url = None
        if thumbnail:
            temp_thumbnail_path = os.path.join(temp_dir, f"{uuid.uuid4()}_{thumbnail.name}")
            with open(temp_thumbnail_path, 'wb+') as destination:
                for chunk in thumbnail.chunks():
                    destination.write(chunk)
            
            thumbnail_success = upload_thumbnail(user_id, video_id, temp_thumbnail_path)
            
            if os.path.exists(temp_thumbnail_path):
                os.remove(temp_thumbnail_path)
                
            if thumbnail_success:
                metadata = get_video_metadata(user_id, video_id)
                if metadata and "thumbnail_path" in metadata:
                    thumbnail_url = generate_video_url(
                        user_id, 
                        video_id, 
                        file_path=metadata["thumbnail_path"], 
                        expiration_time=3600
                    )
        
        # Delete temp video file
        if os.path.exists(temp_video_path):
            os.remove(temp_video_path)
        
        # Get metadata for uploaded video
        video_metadata = get_video_metadata(user_id, video_id)
        
        # Generate temporary URL for video access
        video_url_info = get_video_url_with_quality(user_id, video_id, expiration_time=3600)
        
        # Add URL to metadata
        if video_metadata:
            if video_url_info:
                video_metadata['url'] = video_url_info['url']
                video_metadata['quality'] = video_url_info['quality']
                video_metadata['available_qualities'] = video_url_info['available_qualities']
            
            if thumbnail_url:
                video_metadata['thumbnail_url'] = thumbnail_url
                
            # Create or update Video object in database
            try:
                category = None
                if category_id:
                    try:
                        category = Category.objects.get(id=category_id)
                    except Category.DoesNotExist:
                        pass
                
                video_obj, created = Video.objects.get_or_create(
                    title=title,
                    defaults={
                        'channel_id': 1,  # Assume channel already created
                        'category': category,
                        'views': '0',
                        'age_text': 'Just now',
                        'duration': video_metadata.get('duration', '00:00'),
                    }
                )
                
                video_metadata['video_db_id'] = video_obj.id
            except Exception as db_err:
                logger.error(f"Error creating database record: {db_err}")
        
        # Process quality variants if requested
        if process_qualities and video_id:
            try:
                logger.info(f"Starting quality processing for video {video_id} with process_qualities={process_qualities}")
                process_video_quality_async(gcs_video_path, user_id, video_id)
                logger.info(f"Quality processing started for video {video_id}")
            except Exception as quality_err:
                logger.error(f"Failed to start quality processing: {quality_err}")
        
        return JsonResponse({
            'success': True,
            'video_id': video_id,
            'metadata': video_metadata,
            'processing_qualities': process_qualities
        })
        
    except Exception as e:
        logger.error(f"Error uploading video: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


def list_all_videos(request):
    """
    Полностью переработанная функция для получения списка видео.
    Напрямую ищет видео в GCS без использования кэша.
    """
    try:
        from .gcs_storage import get_bucket, BUCKET_NAME, generate_video_url
        import logging
        import json
        from datetime import datetime
        
        logger = logging.getLogger(__name__)
        
        logger.info("Starting direct list_all_videos API request")
        
        # Параметры пагинации и фильтрации
        try:
            offset = int(request.GET.get('offset', 0))
        except (ValueError, TypeError):
            offset = 0
            
        try:
            limit = int(request.GET.get('limit', 20))
        except (ValueError, TypeError):
            limit = 20
            
        only_metadata = request.GET.get('only_metadata', 'false').lower() == 'true'
        
        # Получаем бакет
        bucket = get_bucket(BUCKET_NAME)
        if not bucket:
            logger.error("Failed to get bucket")
            return JsonResponse({'error': 'Не удалось получить доступ к хранилищу'}, status=500)
        
        # Получаем список пользователей напрямую
        blobs = list(bucket.list_blobs(max_results=100))
        users = set()
        for blob in blobs:
            parts = blob.name.split('/')
            if parts and parts[0] and parts[0].startswith('@'):
                users.add(parts[0])
        
        logger.info(f"Found {len(users)} users in direct fetch")
        
        # Собираем все видео
        all_videos = []
        
        for user_id in users:
            try:
                # Ищем папку metadata для пользователя
                metadata_prefix = f"{user_id}/metadata/"
                metadata_blobs = list(bucket.list_blobs(prefix=metadata_prefix))
                
                # Получаем профиль пользователя
                user_profile = None
                try:
                    user_meta_blob = bucket.blob(f"{user_id}/bio/user_meta.json")
                    if user_meta_blob.exists():
                        user_profile = json.loads(user_meta_blob.download_as_text())
                except Exception as profile_error:
                    logger.error(f"Error loading profile for {user_id}: {profile_error}")
                
                # Перебираем все JSON-файлы метаданных для видео
                for blob in metadata_blobs:
                    if blob.name.endswith('.json'):
                        try:
                            # Получаем метаданные видео
                            metadata = json.loads(blob.download_as_text())
                            
                            # Добавляем информацию о пользователе
                            metadata['user_id'] = user_id
                            if user_profile:
                                metadata['display_name'] = user_profile.get('display_name', user_id.replace('@', ''))
                            else:
                                metadata['display_name'] = user_id.replace('@', '')
                            
                            # Добавляем канал для совместимости с шаблоном
                            metadata['channel'] = metadata.get('display_name', user_id.replace('@', ''))
                            
                            # Форматируем просмотры
                            views = metadata.get('views', 0)
                            if isinstance(views, (int, str)) and str(views).isdigit():
                                views = int(views)
                                metadata['views_formatted'] = f"{views // 1000}K просмотров" if views >= 1000 else f"{views} просмотров"
                            else:
                                metadata['views_formatted'] = "0 просмотров"
                            
                            # Форматируем дату загрузки
                            upload_date = metadata.get('upload_date', '')
                            if upload_date:
                                try:
                                    upload_datetime = datetime.fromisoformat(upload_date)
                                    metadata['upload_date_formatted'] = upload_datetime.strftime("%d.%m.%Y")
                                except Exception:
                                    metadata['upload_date_formatted'] = upload_date[:10] if upload_date else "Недавно"
                            else:
                                metadata['upload_date_formatted'] = "Недавно"
                            
                            all_videos.append(metadata)
                        except Exception as e:
                            logger.error(f"Error processing metadata for {blob.name}: {e}")
            except Exception as e:
                logger.error(f"Error processing user {user_id}: {e}")
        
        # Проверяем, нашли ли мы видео
        if not all_videos:
            logger.warning("No videos found in direct search")
            # Возвращаем пустой список
            return JsonResponse({
                'success': True,
                'videos': [],
                'total': 0
            })
        
        # Сортируем видео по дате загрузки (новые сначала)
        try:
            all_videos.sort(key=lambda x: x.get('upload_date', ''), reverse=True)
        except Exception as sort_error:
            logger.error(f"Error sorting videos: {sort_error}")
        
        total_videos = len(all_videos)
        
        # Применяем пагинацию
        paginated_videos = all_videos[offset:offset + limit]
        
        # Если запрашиваются только метаданные, возвращаем их как есть
        if not only_metadata:
            # Генерируем URL для видео и миниатюр
            for video in paginated_videos:
                try:
                    video_id = video.get('video_id')
                    user_id = video.get('user_id')
                    
                    if video_id and user_id:
                        # URL для видео
                        video['url'] = generate_video_url(user_id, video_id, expiration_time=3600)
                        
                        # URL для миниатюры
                        if 'thumbnail_path' in video:
                            video['thumbnail_url'] = generate_video_url(
                                user_id, video_id, file_path=video['thumbnail_path'], expiration_time=3600
                            )
                except Exception as url_error:
                    logger.error(f"Error generating URL for video {video.get('video_id')}: {url_error}")
        
        logger.info(f"Returning {len(paginated_videos)} videos from direct fetch")
        return JsonResponse({
            'success': True,
            'videos': paginated_videos,
            'total': total_videos
        })
    
    except Exception as e:
        import traceback
        logger.error(f"Error in direct list_all_videos: {e}")
        logger.error(traceback.format_exc())
        
        return JsonResponse({
            'success': False,
            'error': str(e),
            'videos': []
        }, status=500)

@login_required
@require_http_methods(["GET"])
def list_user_videos(request, username=None):
    """
    Optimized function to retrieve a list of videos for a specific user.
    Only returns metadata and previews, without loading the actual video content.
    
    Args:
        request: HTTP request
        username: Username of the video owner (optional, defaults to requesting user)
        
    Returns:
        JsonResponse with list of videos and their metadata
    """
    try:
        from .gcs_storage import get_bucket, BUCKET_NAME, generate_video_url, get_user_profile_from_gcs
        import logging
        import json
        from datetime import datetime
        
        logger = logging.getLogger(__name__)
        
        logger.info("Starting optimized list_user_videos API request")
        
        # If username not provided, use the logged-in user's username
        if not username:
            if not request.user.is_authenticated:
                return JsonResponse({'error': 'Пользователь не авторизован'}, status=401)
            username = request.user.username
        
        # Get parameters from the request
        try:
            offset = int(request.GET.get('offset', 0))
        except (ValueError, TypeError):
            offset = 0
            
        try:
            limit = int(request.GET.get('limit', 20))
        except (ValueError, TypeError):
            limit = 20
            
        only_metadata = request.GET.get('only_metadata', 'false').lower() == 'true'
        
        # Get the GCS bucket
        bucket = get_bucket(BUCKET_NAME)
        if not bucket:
            logger.error(f"Failed to get bucket for user {username}")
            return JsonResponse({'error': 'Не удалось получить доступ к хранилищу'}, status=500)

        # Get user profile for display name
        user_profile = None
        try:
            user_profile = get_user_profile_from_gcs(username)
        except Exception as profile_error:
            logger.error(f"Error loading profile for {username}: {profile_error}")
        
        # Get metadata files for the user
        metadata_prefix = f"{username}/metadata/"
        metadata_blobs = list(bucket.list_blobs(prefix=metadata_prefix))
        
        # Process metadata files
        videos = []
        for blob in metadata_blobs:
            if blob.name.endswith('.json'):
                try:
                    # Get video metadata
                    metadata = json.loads(blob.download_as_text())
                    
                    # Add user information
                    metadata['user_id'] = username
                    if user_profile:
                        metadata['display_name'] = user_profile.get('display_name', username.replace('@', ''))
                    else:
                        metadata['display_name'] = username.replace('@', '')
                        
                    # Add channel for compatibility with the template
                    metadata['channel'] = metadata.get('display_name', username.replace('@', ''))
                    
                    # Format views
                    views = metadata.get('views', 0)
                    if isinstance(views, (int, str)) and str(views).isdigit():
                        views = int(views)
                        metadata['views_formatted'] = f"{views // 1000}K просмотров" if views >= 1000 else f"{views} просмотров"
                    else:
                        metadata['views_formatted'] = "0 просмотров"
                    
                    # Format upload date
                    upload_date = metadata.get('upload_date', '')
                    if upload_date:
                        try:
                            upload_datetime = datetime.fromisoformat(upload_date)
                            metadata['upload_date_formatted'] = upload_datetime.strftime("%d.%m.%Y")
                        except Exception:
                            metadata['upload_date_formatted'] = upload_date[:10] if upload_date else "Недавно"
                    else:
                        metadata['upload_date_formatted'] = "Недавно"
                    
                    videos.append(metadata)
                except Exception as e:
                    logger.error(f"Error processing metadata for {blob.name}: {e}")
        
        # Sort videos by upload date (newest first)
        try:
            videos.sort(key=lambda x: x.get('upload_date', ''), reverse=True)
        except Exception as sort_error:
            logger.error(f"Error sorting videos: {sort_error}")
        
        total_videos = len(videos)
        
        # Apply pagination
        paginated_videos = videos[offset:offset + limit]
        
        # If not requesting only metadata, generate URLs for videos and thumbnails
        if not only_metadata:
            for video in paginated_videos:
                try:
                    video_id = video.get('video_id')
                    
                    if video_id:
                        # URL for video
                        video['url'] = generate_video_url(username, video_id, expiration_time=3600)
                        
                        # URL for thumbnail
                        if 'thumbnail_path' in video:
                            video['thumbnail_url'] = generate_video_url(
                                username, video_id, file_path=video['thumbnail_path'], expiration_time=3600
                            )
                except Exception as url_error:
                    logger.error(f"Error generating URL for video {video.get('video_id')}: {url_error}")
        
        logger.info(f"Returning {len(paginated_videos)} videos for user {username}")
        return JsonResponse({
            'success': True,
            'videos': paginated_videos,
            'total': total_videos
        })
    
    except Exception as e:
        import traceback
        logger.error(f"Error in list_user_videos: {e}")
        logger.error(traceback.format_exc())
        
        return JsonResponse({
            'success': False,
            'error': str(e),
            'videos': []
        }, status=500)            

# Улучшенная функция для генерации URL
def generate_video_url(user_id, video_id, file_path=None, expiration_time=3600):
    """
    Улучшенная версия для генерации временных URL
    """
    from .gcs_storage import get_bucket, get_video_metadata
    
    try:
        bucket = get_bucket()
        if not bucket:
            logger.error("Failed to get bucket")
            return None
            
        # Если указан конкретный путь к файлу (например, для миниатюры)
        if file_path:
            blob = bucket.blob(file_path)
            if not blob.exists():
                logger.error(f"File not found at path: {file_path}")
                return None
        else:
            # Получаем путь к файлу видео из метаданных
            metadata = get_video_metadata(user_id, video_id)
            if not metadata or "file_path" not in metadata:
                logger.error(f"Could not find information about video {video_id}")
                return None
            
            blob = bucket.blob(metadata["file_path"])
            if not blob.exists():
                logger.error(f"Video file not found in storage")
                return None
        
        # Генерируем URL
        url = blob.generate_signed_url(
            version="v4",
            expiration=expiration_time,
            method="GET"
        )
        
        return url
    
    except Exception as e:
        logger.error(f"Error generating URL: {e}")
        return None

@login_required
def studio_view(request):
    """
    Fast-loading view for the studio page that shows placeholders immediately,
    similar to how index.html works.
    """
    # Check if the user is an author
    if not request.user.profile.is_author:
        messages.error(request, 'У вас нет доступа к Студии. Вы должны стать автором, чтобы получить доступ.')
        return redirect('become_author')
    
    try:
        categories = Category.objects.all()
        
        username = request.user.username
        bucket = get_bucket(BUCKET_NAME)
        
        if bucket:
            # Just check if metadata folder has any files
            metadata_prefix = f"{username}/metadata/"
            metadata_blobs = list(bucket.list_blobs(prefix=metadata_prefix, max_results=1))
            has_videos = len(metadata_blobs) > 0
        else:
            has_videos = False
        
        # Return the template with either placeholders or empty state
        return render(request, 'studio/studio.html', {
            'categories': categories,
            'has_videos': has_videos  # Flag to indicate if videos exist
        })
        
    except Exception as e:
        messages.error(request, f'Ошибка при получении данных: {e}')
        logger.error(f"Error in studio_view: {e}")
        
    return render(request, 'studio/studio.html', {
        'categories': categories if 'categories' in locals() else [],
        'has_videos': False
    })
    
@login_required
@require_http_methods(["DELETE"])
def delete_video_from_gcs(request, video_id):
    """
    Удаляет видео из GCS
    """
    try:
        username = request.user.username
        # ВАЖНО: больше не удаляем префикс @, сохраняем его для GCS
            
        success = delete_video(username, video_id)
        
        if success:
            return JsonResponse({'success': True})
        else:
            return JsonResponse({'error': 'Не удалось удалить видео'}, status=400)
            
    except Exception as e:
        logger.error(f"Error deleting video: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@require_http_methods(["GET"])
def get_video_url(request, video_id):
    """
    Gets temporary URL for video or its thumbnail with quality selection.
    Enhanced version with support for thumbnail request and videos from other users.
    
    Parameters:
    - thumbnail: if 'true', returns thumbnail URL instead of video
    - user_id: ID of the user who owns the video (optional)
    - quality: Video quality to retrieve (e.g., '480p', '720p', '1080p')
    """
    try:
        # Check if specific user_id is provided in query parameters
        user_id = request.GET.get('user_id')
        
        # If no user_id provided in query params, check if video_id contains user info
        if not user_id and '__' in video_id:
            user_id, video_id = video_id.split('__', 1)
        
        # If still no user_id, default to current user
        if not user_id:
            user_id = request.user.username
            
        is_thumbnail = request.GET.get('thumbnail', 'false').lower() == 'true'
        quality = request.GET.get('quality')  # New parameter for quality selection
        
        # Get video metadata
        from .gcs_storage import get_video_metadata, generate_video_url, get_video_url_with_quality
        metadata = get_video_metadata(user_id, video_id)
        
        if not metadata:
            return JsonResponse({'error': 'Video metadata not found'}, status=404)
        
        if is_thumbnail:
            thumbnail_path = metadata.get('thumbnail_path')
            if not thumbnail_path:
                return JsonResponse({'error': 'Video has no thumbnail'}, status=404)
                
            url = generate_video_url(user_id, video_id, file_path=thumbnail_path, expiration_time=3600)
            if url:
                return JsonResponse({
                    'success': True,
                    'url': url,
                    'is_thumbnail': True
                })
        else:
            # Generate URL for video with quality selection
            video_url_info = get_video_url_with_quality(user_id, video_id, quality, expiration_time=3600)
            
            if video_url_info and video_url_info['url']:
                return JsonResponse({
                    'success': True,
                    'url': video_url_info['url'],
                    'quality': video_url_info['quality'],
                    'available_qualities': video_url_info['available_qualities'],
                    'is_thumbnail': False
                })
        
        return JsonResponse({'error': 'Failed to generate URL'}, status=400)
            
    except Exception as e:
        logger.error(f"Error generating URL: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

@require_http_methods(["GET"])
def get_thumbnail_url(request, video_id):
    """
    Отдельный эндпоинт для получения URL миниатюры для видео.
    Поддерживает использование как для своих, так и для чужих видео.
    
    Args:
        video_id: ID видео или составной ID пользователь__видео
    """
    try:
        # Проверяем, содержит ли video_id составной идентификатор
        if '__' in video_id:
            user_id, gcs_video_id = video_id.split('__', 1)
        else:
            # Если пользователь авторизован, используем его ID
            if request.user.is_authenticated:
                user_id = request.user.username
                gcs_video_id = video_id
            else:
                return JsonResponse({'error': 'Необходимо указать ID пользователя в формате user__video'}, status=400)
        
        # Получаем метаданные видео
        from .gcs_storage import get_video_metadata, generate_video_url
        
        metadata = get_video_metadata(user_id, gcs_video_id)
        if not metadata:
            return JsonResponse({'error': 'Метаданные видео не найдены'}, status=404)
        
        # Генерируем URL для миниатюры
        thumbnail_path = metadata.get('thumbnail_path')
        if not thumbnail_path:
            return JsonResponse({'error': 'У видео нет миниатюры'}, status=404)
            
        url = generate_video_url(user_id, gcs_video_id, file_path=thumbnail_path, expiration_time=3600)
        
        if url:
            return JsonResponse({
                'success': True,
                'url': url
            })
        else:
            return JsonResponse({'error': 'Не удалось сгенерировать URL миниатюры'}, status=400)
            
    except Exception as e:
        logger.error(f"Error generating thumbnail URL: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@require_http_methods(["GET"])
def refresh_metadata_cache(request):
    """
    API для принудительного обновления кэша метаданных видео.
    Требует аутентификации и доступен только админам.
    """
    try:
        # Проверяем, является ли пользователь суперпользователем
        if not request.user.is_superuser:
            return JsonResponse({
                'success': False,
                'error': 'Доступ запрещен. Требуются права администратора.'
            }, status=403)
            
        from .gcs_storage import cache_video_metadata
        
        # Обновляем кэш метаданных
        success = cache_video_metadata()
        
        if success:
            return JsonResponse({
                'success': True,
                'message': 'Кэш метаданных видео успешно обновлен'
            })
        else:
            return JsonResponse({
                'success': False,
                'error': 'Не удалось обновить кэш метаданных'
            }, status=500)
            
    except Exception as e:
        logger.error(f"Error refreshing metadata cache: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)