
from django.shortcuts import render, redirect
from .models import VideoLike, Category, Subscription
import random
from .gcs_storage import get_video_metadata, get_bucket
from django.db import transaction
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from .forms import (
    UserRegistrationForm, UserLoginForm, UserProfileForm, 
    AuthorApplicationForm, EmailVerificationForm, DisplayNameForm
)
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.core.paginator import Paginator
from django.core.mail import send_mail
from django.conf import settings
import random
import os
import uuid
import logging
import datetime
import requests
import json
from django.http import JsonResponse
logger = logging.getLogger(__name__)

def custom_page_not_found(request, exception):
    return render(request, 'main/404.html', status=404)


def index(request):
    categories = Category.objects.all()
    
    try:
        logger.info("Starting optimized video metadata loading for index page")
        
        # Запрашиваем метаданные первых 20 видео через API без использования кэша
        response = requests.get(f"{request.scheme}://{request.get_host()}/api/list-all-videos/?only_metadata=true&limit=20")
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success') and data.get('videos'):
                selected_videos = data.get('videos')
                
                # Перетасовываем видео для случайного порядка
                random.shuffle(selected_videos)
                
                logger.info(f"Successfully loaded and shuffled {len(selected_videos)} video metadata from API")
                return render(request, 'main/index.html', {
                    'categories': categories,
                    'gcs_videos': selected_videos
                })
        
        logger.warning("Failed to load videos from API, falling back to empty state")
        return render(request, 'main/index.html', {'categories': categories, 'gcs_videos': []})
        
    except Exception as e:
        logger.error(f"Error in optimized index view: {e}")
        return render(request, 'main/index.html', {'categories': categories, 'gcs_videos': []})

def video_detail(request, video_id):
    """
    Shows detailed information about a video from GCS.
    Optimized version with improved loading - fetches metadata first and loads the video asynchronously.
    
    Args:
        request: HTTP request
        video_id: ID video (string in format gcs_video_id)
    """
    try:
        # Check if video_id contains user information
        # Video ID format either username__video_id or just video_id
        if '__' in video_id:
            # If ID contains a separator, split it
            user_id, gcs_video_id = video_id.split('__', 1)
        else:
            # If old format or no user, search in metadata of all videos
            gcs_video_id = video_id
            user_id = None
            
            from .gcs_storage import get_bucket, BUCKET_NAME
            bucket = get_bucket(BUCKET_NAME)
            
            if bucket:
                # Get list of users
                blobs = bucket.list_blobs(delimiter='/')
                prefixes = list(blobs.prefixes)
                users = [prefix.replace('/', '') for prefix in prefixes]
                
                # Look for the video among all users
                from .gcs_storage import get_video_metadata
                for user in users:
                    metadata = get_video_metadata(user, gcs_video_id)
                    if metadata:  # If we find the video, use this user
                        user_id = user
                        break
        
        # Если не удается найти видео или пользователя, отображаем страницу без остановки
        if not user_id:
            # Вместо ошибки используем пустые данные для отображения страницы
            video_data = {
                'id': f"unknown__{gcs_video_id}",
                'gcs_id': gcs_video_id,
                'user_id': "unknown",
                'title': "Видео не найдено",
                'description': "Видео не найдено или было удалено",
                'channel': "Неизвестно",
                'display_name': "Неизвестно",
                'views': 0,
                'views_formatted': "0 просмотров",
                'likes': 0,
                'dislikes': 0,
                'duration': "00:00",
                'upload_date': "",
                'age': "Недавно"
            }
            
            return render(request, 'main/video.html', {
                'video': video_data,
                'comments': [],
                'recommended_videos': []
            })
        
        # Fetch the metadata first - this is essential for displaying the page
        from .gcs_storage import get_video_metadata, get_video_comments, get_user_profile_from_gcs
        
        # Get video metadata
        metadata = get_video_metadata(user_id, gcs_video_id)
        
        # Если не удается получить метаданные, отображаем страницу с базовыми данными
        if not metadata:
            video_data = {
                'id': f"{user_id}__{gcs_video_id}",
                'gcs_id': gcs_video_id,
                'user_id': user_id,
                'title': "Загрузка видео...",
                'description': "Информация о видео загружается",
                'channel': user_id.replace('@', ''),
                'display_name': user_id.replace('@', ''),
                'views': 0,
                'views_formatted': "0 просмотров",
                'likes': 0,
                'dislikes': 0,
                'duration': "00:00",
                'upload_date': "",
                'age': "Недавно"
            }
            
            return render(request, 'main/video.html', {
                'video': video_data,
                'comments': [],
                'recommended_videos': []
            })
        
        # Fetch user profile for display name
        user_profile = get_user_profile_from_gcs(user_id)
        display_name = user_profile.get('display_name', user_id.replace('@', '')) if user_profile else user_id.replace('@', '')
        
        # Get comments
        comments_data = get_video_comments(user_id, gcs_video_id)
        
        # Prepare video data without the actual video URL (will be fetched client-side)
        video_data = {
            'id': f"{user_id}__{gcs_video_id}",  # Composite ID for URL
            'gcs_id': gcs_video_id,              # Original ID in GCS
            'user_id': user_id,                  # User ID (owner)
            'title': metadata.get('title', 'No title'),
            'description': metadata.get('description', 'No description'),
            'channel': display_name,             # Use display_name from profile
            'display_name': display_name,        # Explicitly add display_name
            'views': metadata.get('views', 0),
            'views_formatted': f"{metadata.get('views', 0)} views",
            'likes': metadata.get('likes', 0),
            'dislikes': metadata.get('dislikes', 0),
            'duration': metadata.get('duration', '00:00'),
            # Don't set video_url here - it will be loaded asynchronously
            # Format upload date
            'upload_date': metadata.get('upload_date', ''),
            'age': metadata.get('age_text', 'Recently')
        }
        
        # Check if a thumbnail exists and add its path to the data
        if "thumbnail_path" in metadata:
            from .gcs_storage import generate_video_url
            video_data['thumbnail_url'] = generate_video_url(
                user_id, 
                gcs_video_id, 
                file_path=metadata["thumbnail_path"], 
                expiration_time=3600
            )
        
        # Get recommended videos using optimized function - can be loaded in background
        recommended_videos = get_recommended_videos(user_id, gcs_video_id)
        
        return render(request, 'main/video.html', {
            'video': video_data,
            'comments': comments_data.get('comments', []),
            'recommended_videos': recommended_videos
        })
    except Exception as e:
        # В случае ошибки все равно отображаем страницу с базовой информацией
        logger.error(f"Error loading video details: {e}")
        video_data = {
            'id': f"error__{video_id}",
            'gcs_id': video_id,
            'user_id': "error",
            'title': "Ошибка загрузки видео",
            'description': "Произошла ошибка при загрузке информации о видео",
            'channel': "Ошибка",
            'display_name': "Ошибка",
            'views': 0,
            'views_formatted': "0 просмотров",
            'likes': 0,
            'dislikes': 0,
            'duration': "00:00",
            'upload_date': "",
            'age': "Недавно"
        }
        
        return render(request, 'main/video.html', {
            'video': video_data,
            'comments': [],
            'recommended_videos': []
        })
        
def get_recommended_videos(current_user_id, current_video_id, limit=10):
    """
    Получает рекомендованные видео на основе текущего видео.
    Оптимизированная версия: получаем все видео из GCS, исключаем текущее и перемешиваем.
    
    Args:
        current_user_id: ID пользователя текущего видео
        current_video_id: ID текущего видео
        limit: максимальное количество рекомендаций
        
    Returns:
        list: Список рекомендованных видео
    """
    try:
        from .gcs_storage import list_user_videos, get_bucket, BUCKET_NAME, generate_video_url, get_user_profile_from_gcs
        import random
        import concurrent.futures
        
        # Получаем бакет
        bucket = get_bucket(BUCKET_NAME)
        if not bucket:
            return []
            
        # Получаем список пользователей
        blobs = bucket.list_blobs(delimiter='/')
        prefixes = list(blobs.prefixes)
        users = [prefix.replace('/', '') for prefix in prefixes]
        
        # Кэш для профилей пользователей
        user_profiles = {}
        
        # Используем ThreadPoolExecutor для параллельной загрузки видео
        all_videos = []
        
        # Функция для загрузки видео одного пользователя
        def load_user_videos(user_id):
            videos_list = []
            user_videos = list_user_videos(user_id)
            
            if not user_videos:
                return videos_list
                
            # Получаем профиль пользователя для display_name
            if user_id not in user_profiles:
                user_profile = get_user_profile_from_gcs(user_id)
                user_profiles[user_id] = user_profile
            else:
                user_profile = user_profiles[user_id]
            
            for video in user_videos:
                # Пропускаем текущее видео
                if user_id == current_user_id and video.get('video_id') == current_video_id:
                    continue
                    
                # Добавляем user_id к видео
                if 'user_id' not in video:
                    video['user_id'] = user_id
                
                # Добавляем display_name
                if user_id in user_profiles and user_profiles[user_id] and 'display_name' in user_profiles[user_id]:
                    video['display_name'] = user_profiles[user_id]['display_name']
                else:
                    # Если display_name отсутствует, используем username без префикса @
                    video['display_name'] = user_id.replace('@', '')
                    
                videos_list.append(video)
            
            return videos_list
            
        # Загружаем видео параллельно с таймаутом
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            future_to_user = {executor.submit(load_user_videos, user_id): user_id for user_id in users}
            for future in concurrent.futures.as_completed(future_to_user, timeout=5):
                try:
                    user_videos = future.result()
                    all_videos.extend(user_videos)
                except Exception as e:
                    user_id = future_to_user[future]
                    logger.error(f"Error loading videos for user {user_id}: {e}")
        
        # Перемешиваем видео
        random.shuffle(all_videos)
        
        # Ограничиваем количество
        recommended = all_videos[:limit]
        
        # Добавляем URL для каждого видео
        for video in recommended:
            video_id = video.get('video_id')
            user_id = video.get('user_id')
            if video_id and user_id:
                # URL для видео
                video['url'] = f"/video/{user_id}__{video_id}/"
                
                # URL для миниатюры
                if 'thumbnail_path' in video:
                    video['thumbnail_url'] = generate_video_url(
                        user_id, 
                        video_id, 
                        file_path=video['thumbnail_path'], 
                        expiration_time=3600
                    )
                
                # Форматируем данные для шаблона
                # Используем display_name из метаданных или user_id
                if 'channel' not in video:
                    video['channel'] = video.get('display_name', video.get('user_id', ''))
                
                # Форматируем просмотры
                views = video.get('views', 0)
                if isinstance(views, int) or (isinstance(views, str) and views.isdigit()):
                    views = int(views)
                    if views >= 1000:
                        video['views_formatted'] = f"{views // 1000}K просмотров"
                    else:
                        video['views_formatted'] = f"{views} просмотров"
                else:
                    video['views_formatted'] = "0 просмотров"
                    
        return recommended
        
    except Exception as e:
        logger.error(f"Error getting recommended videos: {e}")
        return []

def search_results(request):
    """
    Highly optimized search results page that loads quickly and only fetches necessary data
    """
    query = request.GET.get('query', '')
    offset = int(request.GET.get('offset', 0))
    limit = int(request.GET.get('limit', 20))
    json_response = request.GET.get('format') == 'json'
    
    # If no query provided, return empty results immediately
    if not query:
        if json_response:
            return JsonResponse({'videos': [], 'total': 0})
        return render(request, 'main/search.html', {'query': query, 'videos': []})
    
    # Search implementation using GCS - optimized version
    try:
        from .gcs_storage import get_bucket, BUCKET_NAME
        import logging
        import json
        from datetime import datetime
        import concurrent.futures
        
        logger = logging.getLogger(__name__)
        logger.info(f"Starting optimized search for: '{query}' with offset={offset}, limit={limit}")
        
        # Initial response with placeholder data (for fast initial page load)
        if not json_response:
            # Render the page immediately with placeholders
            return render(request, 'main/search.html', {
                'query': query,
                'videos': [],
                'is_loading': True,
                'placeholder_count': min(limit, 6)  # Show up to 6 placeholders
            })
        
        # For AJAX requests, perform the actual search
        # Get bucket - this is required for search
        bucket = get_bucket(BUCKET_NAME)
        if not bucket:
            logger.error("Failed to get bucket")
            return JsonResponse({'error': 'Failed to access storage', 'videos': []}, status=500)
            
        # Get list of users more efficiently - limit to 20 users max for speed
        blobs = list(bucket.list_blobs(max_results=100))
        users = set()
        for blob in blobs:
            parts = blob.name.split('/')
            if parts and parts[0] and parts[0].startswith('@'):
                users.add(parts[0])
                if len(users) >= 20:  # Limit to 20 users for faster search
                    break
        
        # Define function to search a single user's videos
        def search_user_videos(user_id):
            results = []
            try:
                # Use a single list_blobs call with a specific prefix and filter in memory
                # This is much faster than multiple API calls
                metadata_prefix = f"{user_id}/metadata/"
                metadata_blobs = list(bucket.list_blobs(prefix=metadata_prefix, max_results=50))
                
                # Get user profile for display name and avatar
                user_profile = None
                avatar_url = None
                try:
                    user_meta_blob = bucket.blob(f"{user_id}/bio/user_meta.json")
                    if user_meta_blob.exists():
                        user_profile = json.loads(user_meta_blob.download_as_text())
                        
                        # Check if user has a custom avatar and generate URL
                        if user_profile.get('avatar_path') and not user_profile.get('is_default_avatar', True):
                            avatar_blob = bucket.blob(user_profile.get('avatar_path'))
                            if avatar_blob.exists():
                                avatar_url = avatar_blob.generate_signed_url(
                                    version="v4",
                                    expiration=3600,
                                    method="GET"
                                )
                except Exception as profile_error:
                    logger.error(f"Error loading profile for {user_id}: {profile_error}")
                
                # Get display name from profile or fallback to username
                display_name = user_profile.get('display_name', user_id.replace('@', '')) if user_profile else user_id.replace('@', '')
                
                # Process each metadata file
                query_lower = query.lower()
                for blob in metadata_blobs:
                    if blob.name.endswith('.json'):
                        try:
                            metadata_text = blob.download_as_text()
                            video_data = json.loads(metadata_text)
                            
                            # Fast check for matches in title and description
                            title = (video_data.get('title') or '').lower()
                            description = (video_data.get('description') or '').lower()
                            
                            if query_lower in title or query_lower in description:
                                # Only extract minimum required fields for search results
                                # This reduces memory usage and processing time
                                minimal_data = {
                                    'video_id': video_data.get('video_id'),
                                    'title': video_data.get('title', 'No title'),
                                    'description': video_data.get('description', ''),
                                    'duration': video_data.get('duration', '00:00'),
                                    'user_id': user_id,
                                    'display_name': display_name,
                                    'channel': display_name,  # Add channel to prevent template error
                                    'avatar_url': avatar_url,  # Include avatar URL if available
                                    'upload_date': video_data.get('upload_date', ''),
                                }
                                
                                # Add thumbnail path if available
                                if 'thumbnail_path' in video_data:
                                    minimal_data['thumbnail_path'] = video_data['thumbnail_path']
                                
                                # Format views
                                views = video_data.get('views', 0)
                                if isinstance(views, (int, str)) and str(views).isdigit():
                                    views = int(views)
                                    minimal_data['views'] = views
                                    minimal_data['views_formatted'] = f"{views // 1000}K просмотров" if views >= 1000 else f"{views} просмотров"
                                else:
                                    minimal_data['views'] = 0
                                    minimal_data['views_formatted'] = "0 просмотров"
                                
                                # Format upload date
                                if minimal_data['upload_date']:
                                    try:
                                        upload_datetime = datetime.fromisoformat(minimal_data['upload_date'])
                                        minimal_data['upload_date_formatted'] = upload_datetime.strftime("%d.%m.%Y")
                                    except Exception:
                                        minimal_data['upload_date_formatted'] = minimal_data['upload_date'][:10] if minimal_data['upload_date'] else "Недавно"
                                else:
                                    minimal_data['upload_date_formatted'] = "Недавно"
                                
                                # Add to results
                                results.append(minimal_data)
                        except Exception as e:
                            logger.error(f"Error processing metadata {blob.name}: {str(e)}")
            except Exception as e:
                logger.error(f"Error searching user {user_id}: {str(e)}")
            
            return results
        
        # Use parallel processing to search multiple users at once
        search_results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            # Submit search tasks for each user
            future_to_user = {executor.submit(search_user_videos, user): user for user in users}
            
            # Collect results as they complete with a timeout
            for future in concurrent.futures.as_completed(future_to_user, timeout=3):
                user = future_to_user[future]
                try:
                    user_results = future.result()
                    search_results.extend(user_results)
                except Exception as exc:
                    logger.error(f"User {user} search generated an exception: {exc}")
        
        # Sort by relevance
        query_lower = query.lower()
        def sort_by_relevance(video):
            title = (video.get('title') or '').lower()
            description = (video.get('description') or '').lower()
            
            # Exact title match gets highest priority
            if title == query_lower:
                return (0, -video.get('views', 0))
            # Title starts with query gets second priority
            elif title.startswith(query_lower):
                return (1, -video.get('views', 0))
            # Title contains query gets third priority
            elif query_lower in title:
                return (2, -video.get('views', 0))
            # Description matches get lower priority
            elif description == query_lower:
                return (3, -video.get('views', 0))
            # Description starts with query
            elif description.startswith(query_lower):
                return (4, -video.get('views', 0))
            # Description contains query
            else:
                return (5, -video.get('views', 0))
        
        # Sort by relevance and then by views (within same relevance group)
        search_results.sort(key=sort_by_relevance)
        
        # Apply pagination
        total_results = len(search_results)
        paginated_results = search_results[offset:offset + limit]
        
        # Generate thumbnail URLs for paginated results only
        from .gcs_storage import generate_video_url
        for video in paginated_results:
            # Only generate URLs if thumbnail_path exists
            if video.get('thumbnail_path'):
                try:
                    video['thumbnail_url'] = generate_video_url(
                        video['user_id'], 
                        video['video_id'], 
                        file_path=video['thumbnail_path'], 
                        expiration_time=3600
                    )
                except Exception as url_error:
                    logger.error(f"Error generating thumbnail URL: {url_error}")
        
        # Return JSON response for AJAX
        return JsonResponse({
            'success': True,
            'videos': paginated_results,
            'total': total_results
        })
        
    except Exception as e:
        import traceback
        logger.error(f"Search error: {str(e)}")
        logger.error(traceback.format_exc())
        
        return JsonResponse({
            'success': False,
            'error': str(e),
            'videos': []
        }, status=500)

def send_verification_code(request, email):
    # Генерируем код подтверждения (6 цифр)
    verification_code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
    request.session['verification_code'] = verification_code
    
    # Подготавливаем контекст для шаблона
    context = {
        'verification_code': verification_code,
        'user_email': email,
    }
    
    # Рендерим HTML письмо
    html_message = render_to_string('emails/verification_email.html', context)
    # Создаем текстовую версию письма (для клиентов без поддержки HTML)
    plain_message = strip_tags(html_message)
    
    # Создаем и отправляем письмо
    subject = 'KRONIK - Подтверждение регистрации'
    email_message = EmailMessage(
        subject,
        html_message,
        settings.DEFAULT_FROM_EMAIL,
        [email]
    )
    email_message.content_subtype = 'html'
    
    # Отправляем письмо
    email_message.send()
    
    return verification_code

def register_view(request):
    """
    Handle user registration process with email verification and default avatar.
    
    :param request: Django request object
    :return: Rendered registration or verification page
    """
    # Redirect authenticated users
    if request.user.is_authenticated:
        # Check if email is verified
        if not request.user.profile.email_verified:
            return redirect('verify_email')
        
        # Check if user details are completed
        if not request.user.profile.display_name:
            return redirect('user_details')
        
        return redirect('index')
    
    # Check if we're in email verification phase
    if 'registration_data' in request.session:
        return redirect('verify_email')
    
    # Initial registration form
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            # Don't save yet, store in session and send verification email
            request.session['registration_data'] = request.POST.dict()
            
            # Send verification code
            email = form.cleaned_data.get('email')
            send_verification_code(request, email)
            
            messages.info(request, f'Код подтверждения отправлен на {email}. Пожалуйста, проверьте вашу почту.')
            return redirect('verify_email')
    else:
        form = UserRegistrationForm()
    
    return render(request, 'accounts/register.html', {'form': form})

def verify_email_view(request):
    # If not in registration process and not logged in, redirect to register
    if 'registration_data' not in request.session and not request.user.is_authenticated:
        return redirect('register')
        
    # If logged in but email already verified, check if we need user details
    if request.user.is_authenticated and request.user.profile.email_verified:
        if not request.user.profile.display_name:
            return redirect('user_details')
        return redirect('index')
        
    # Get email from session or user object
    if 'registration_data' in request.session:
        email = request.session['registration_data'].get('email')
    else:
        email = request.user.email
        
    if request.method == 'POST':
        verification_form = EmailVerificationForm(request.POST)
        if verification_form.is_valid():
            # Get stored verification code
            stored_code = request.session.get('verification_code')
            submitted_code = verification_form.cleaned_data['verification_code']
            
            # Verify the code
            if stored_code == submitted_code:
                # If in registration process
                if 'registration_data' in request.session:
                    # Get stored registration data
                    reg_data = request.session['registration_data']
                    
                    # Create user account
                    form = UserRegistrationForm(reg_data)
                    if form.is_valid():
                        user = form.save()
                        
                        # Set profile fields
                        if hasattr(user, 'profile'):
                            user.profile.date_of_birth = form.cleaned_data['date_of_birth']
                            user.profile.gender = form.cleaned_data['gender']  # Сохраняем пол
                            user.profile.email_verified = True
                            user.profile.save()
                        
                        # Clean up session
                        del request.session['registration_data']
                        del request.session['verification_code']
                        
                        # Log the user in
                        username = form.cleaned_data.get('username')
                        password = form.cleaned_data.get('password1')
                        user = authenticate(username=username, password=password)
                        login(request, user)
                        
                        messages.success(request, f'Email успешно подтвержден!')
                        return redirect('user_details')
                else:
                    # For existing users verifying email
                    request.user.profile.email_verified = True
                    request.user.profile.save()
                    
                    # Clean up session
                    if 'verification_code' in request.session:
                        del request.session['verification_code']
                        
                    messages.success(request, 'Email успешно подтвержден!')
                    
                    # Check if user details are completed
                    if not request.user.profile.display_name:
                        return redirect('user_details')
                    return redirect('index')
            else:
                messages.error(request, 'Неверный код подтверждения. Попробуйте снова.')
        else:
            for field, errors in verification_form.errors.items():
                for error in errors:
                    messages.error(request, f"{error}")
                    
    else:
        verification_form = EmailVerificationForm()
        
    # Handle resend code button
    if request.GET.get('resend') == 'true':
        if email:
            send_verification_code(request, email)
            messages.info(request, f'Новый код подтверждения отправлен на {email}. Пожалуйста, проверьте вашу почту.')
    
    return render(request, 'accounts/verify_email.html', {
        'form': verification_form,
        'email': email
    })

def user_details_view(request):
    # If not logged in, redirect to login
    if not request.user.is_authenticated:
        return redirect('login')
        
    # If email not verified, redirect to verification
    if not request.user.profile.email_verified:
        return redirect('verify_email')
        
    # If user details already completed, redirect to home
    if request.user.profile.display_name:
        return redirect('index')
        
    if request.method == 'POST':
        form = DisplayNameForm(request.POST, instance=request.user.profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Спасибо! Ваш профиль заполнен.')
            return redirect('index')
    else:
        form = DisplayNameForm(instance=request.user.profile)
    
    return render(request, 'accounts/user_details.html', {'form': form})

def login_view(request):
    if request.user.is_authenticated:
        # Check if email is verified
        if not request.user.profile.email_verified:
            # If not verified, redirect to verification page
            return redirect('verify_email')
        # Check if user details are completed
        if not request.user.profile.display_name:
            return redirect('user_details')
        return redirect('index')
        
    if request.method == 'POST':
        form = UserLoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                
                # Check if email is verified
                if not user.profile.email_verified:
                    # Send a new verification code
                    send_verification_code(request, user.email)
                    messages.info(request, f'Пожалуйста, подтвердите ваш email. Код подтверждения отправлен на {user.email}.')
                    return redirect('verify_email')
                
                # Check if user details are completed
                if not user.profile.display_name:
                    return redirect('user_details')
                    
                next_page = request.GET.get('next', 'index')
                return redirect(next_page)
            else:
                messages.error(request, 'Неверное имя пользователя или пароль')
    else:
        form = UserLoginForm()
    
    return render(request, 'accounts/login.html', {'form': form})

def logout_view(request):
    logout(request)
    return redirect('login')

@login_required
def profile_view(request):
    """
    User profile view with improved avatar handling.
    Now relying entirely on GCS for avatar storage.
    """
    # Check if email is verified
    if not request.user.profile.email_verified:
        # If not verified, redirect to verification page
        return redirect('verify_email')
    
    # Check if user details are completed
    if not request.user.profile.display_name:
        return redirect('user_details')
        
    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES, instance=request.user.profile)
        if form.is_valid():
            profile = form.save(commit=False)
            
            # Get username for GCS storage (with @ prefix)
            username = request.user.username
            
            # Check if "remove_avatar" was requested
            remove_avatar = request.POST.get('remove_avatar') == 'true'
            
            # Process profile picture if provided or removal requested
            profile_picture_path = None
            if request.FILES.get('profile_picture'):
                # Create temporary file
                temp_dir = os.path.join(settings.BASE_DIR, 'temp')
                os.makedirs(temp_dir, exist_ok=True)
                
                # Get file extension
                profile_pic = request.FILES['profile_picture']
                file_name = profile_pic.name
                file_extension = os.path.splitext(file_name)[1].lower()
                
                # Save uploaded file temporarily
                profile_picture_path = os.path.join(temp_dir, f"{uuid.uuid4()}{file_extension}")
                with open(profile_picture_path, 'wb+') as destination:
                    for chunk in profile_pic.chunks():
                        destination.write(chunk)
            elif remove_avatar:
                # If avatar removal requested, set default avatar
                default_avatar_path = os.path.join(settings.STATIC_ROOT, 'default.png')
                if not os.path.exists(default_avatar_path):
                    default_avatar_path = os.path.join(settings.BASE_DIR, 'static', 'default.png')
                if os.path.exists(default_avatar_path):
                    profile_picture_path = default_avatar_path
            
            try:
                # Update profile in GCS
                from .gcs_storage import update_user_profile_in_gcs
                
                gcs_result = update_user_profile_in_gcs(
                    user_id=username,
                    display_name=profile.display_name,
                    bio=profile.bio,
                    profile_picture_path=profile_picture_path
                )
                
                if not gcs_result:
                    logger.warning(f"Could not update profile in GCS for user {username}")
                
                # Clean up temporary file if created
                if profile_picture_path and os.path.exists(profile_picture_path) and profile_picture_path not in [
                    os.path.join(settings.STATIC_ROOT, 'default.png'),
                    os.path.join(settings.BASE_DIR, 'static', 'default.png')
                ]:
                    os.remove(profile_picture_path)
                    
            except Exception as e:
                logger.error(f"Error updating profile in GCS: {e}")
                
                # Clean up temporary file if created
                if profile_picture_path and os.path.exists(profile_picture_path) and profile_picture_path not in [
                    os.path.join(settings.STATIC_ROOT, 'default.png'),
                    os.path.join(settings.BASE_DIR, 'static', 'default.png')
                ]:
                    os.remove(profile_picture_path)
            
            # Save profile to database - importantly, don't save the profile_picture to DB anymore
            # Just maintain the profile record in Django
            profile.save()
            messages.success(request, 'Your profile has been updated!')
            return redirect('profile')
    else:
        form = UserProfileForm(instance=request.user.profile)
        
        # Try to load profile information from GCS
        try:
            username = request.user.username
            
            from .gcs_storage import get_user_profile_from_gcs
            gcs_profile = get_user_profile_from_gcs(username)
            
            # Pass GCS profile to template context if available
            if gcs_profile:
                return render(request, 'accounts/profile.html', {
                    'form': form,
                    'gcs_profile': gcs_profile
                })
        except Exception as e:
            logger.error(f"Error retrieving GCS profile: {e}")
    
    return render(request, 'accounts/profile.html', {'form': form})

@login_required
def author_application(request):
    # Проверяем, уже ли пользователь автор или подал заявку
    if request.user.profile.is_author:
        messages.info(request, 'Вы уже являетесь автором!')
        return redirect('studio')
        
    if request.user.profile.author_application_pending:
        messages.info(request, 'Ваша заявка на авторство уже находится на рассмотрении.')
        return redirect('profile')
    
    if request.method == 'POST':
        form = AuthorApplicationForm(request.POST, instance=request.user.profile)
        if form.is_valid():
            profile = form.save(commit=False)
            profile.author_application_pending = True
            profile.save()
            form.save_m2m()  # Сохраняем many-to-many поля
            
            # Отправляем уведомление администратору
            subject = f'Новая заявка на авторство от {request.user.username}'
            message = f"""
            Пользователь {request.user.username} ({request.user.email}) подал заявку на авторство.
            
            Области экспертизы: {', '.join(area.name for area in form.cleaned_data['expertise_areas'])}
            
            Данные о квалификации:
            {profile.credentials}
            
            Для подтверждения или отклонения заявки перейдите в админ-панель:
            {request.build_absolute_uri('/admin/main/userprofile/')}
            """
            
            send_mail(
                subject, 
                message, 
                settings.DEFAULT_FROM_EMAIL, 
                [settings.ADMIN_EMAIL],  # Добавьте свой email в settings.py
                fail_silently=False
            )
            
            messages.success(request, 'Ваша заявка на авторство успешно отправлена! Мы свяжемся с вами после рассмотрения.')
            return redirect('profile')
    else:
        form = AuthorApplicationForm(instance=request.user.profile)
    
    return render(request, 'accounts/author_application.html', {'form': form})

@login_required
def profile_settings_view(request):
    """
    Представление для страницы настроек профиля с возможностью изменения аватара.
    """
    # Проверяем, подтвержден ли email
    if not request.user.profile.email_verified:
        # Если не подтвержден, перенаправляем на страницу подтверждения
        return redirect('verify_email')
    
    # Проверяем, заполнены ли данные пользователя
    if not request.user.profile.display_name:
        return redirect('user_details')
        
    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES, instance=request.user.profile)
        if form.is_valid():
            profile = form.save(commit=False)
            
            # Получаем имя пользователя для хранения в GCS (с префиксом @)
            username = request.user.username
            
            # Проверяем, нужно ли удалить текущую аватарку
            remove_avatar = request.POST.get('remove_avatar') == 'true'
            
            # Обрабатываем фото профиля, если предоставлено или требуется удаление
            profile_picture_path = None
            if request.FILES.get('profile_picture'):
                # Создаем временный файл
                temp_dir = os.path.join(settings.MEDIA_ROOT, 'temp')
                os.makedirs(temp_dir, exist_ok=True)
                
                # Получаем расширение файла
                profile_pic = request.FILES['profile_picture']
                file_name = profile_pic.name
                file_extension = os.path.splitext(file_name)[1].lower()
                
                # Сохраняем загруженный файл временно
                profile_picture_path = os.path.join(temp_dir, f"{uuid.uuid4()}{file_extension}")
                with open(profile_picture_path, 'wb+') as destination:
                    for chunk in profile_pic.chunks():
                        destination.write(chunk)
            elif remove_avatar:
                # Если нужно удалить аватарку и установить дефолтную
                default_avatar_path = os.path.join(settings.STATIC_ROOT, 'default.png')
                if not os.path.exists(default_avatar_path):
                    default_avatar_path = os.path.join(settings.BASE_DIR, 'static', 'default.png')
                
                if os.path.exists(default_avatar_path):
                    profile_picture_path = default_avatar_path
            
            try:
                # Обновляем профиль в GCS
                from .gcs_storage import update_user_profile_in_gcs
                
                gcs_result = update_user_profile_in_gcs(
                    user_id=username,
                    display_name=profile.display_name,
                    bio=profile.bio,
                    profile_picture_path=profile_picture_path
                )
                
                if not gcs_result:
                    logger.warning(f"Не удалось обновить профиль в GCS для пользователя {username}")
                
                # Очищаем временный файл, если он был создан
                if profile_picture_path and os.path.exists(profile_picture_path) and profile_picture_path != os.path.join(settings.STATIC_ROOT, 'default.png') and profile_picture_path != os.path.join(settings.BASE_DIR, 'static', 'default.png'):
                    os.remove(profile_picture_path)
                    
            except Exception as e:
                logger.error(f"Ошибка при обновлении профиля в GCS: {e}")
                # Продолжаем сохранение профиля в базе данных, даже если обновление GCS не удалось
                
                # Очищаем временный файл, если он был создан
                if profile_picture_path and os.path.exists(profile_picture_path) and profile_picture_path != os.path.join(settings.STATIC_ROOT, 'default.png') and profile_picture_path != os.path.join(settings.BASE_DIR, 'static', 'default.png'):
                    os.remove(profile_picture_path)
            
            # Сохраняем профиль в базе данных
            profile.save()
            messages.success(request, 'Настройки профиля успешно обновлены!')
            return redirect('profile_settings')
    else:
        form = UserProfileForm(instance=request.user.profile)
        
        # Пытаемся загрузить информацию профиля из GCS для отображения
        try:
            username = request.user.username
            
            from .gcs_storage import get_user_profile_from_gcs
            gcs_profile = get_user_profile_from_gcs(username)
            
            # Передаем данные профиля GCS в контекст шаблона, если они доступны
            if gcs_profile:
                return render(request, 'accounts/profile_settings.html', {
                    'form': form,
                    'gcs_profile': gcs_profile
                })
        except Exception as e:
            logger.error(f"Ошибка при получении профиля GCS: {e}")
    
    return render(request, 'accounts/profile_settings.html', {'form': form})

@login_required
@require_http_methods(["POST"])
def toggle_subscription(request):
    """
    API endpoint to toggle subscription to a channel
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid method'}, status=405)

    try:
        channel_id = request.POST.get('channel_id')
        action = request.POST.get('action', 'toggle')  # toggle, subscribe, unsubscribe

        if not channel_id:
            return JsonResponse({'success': False, 'error': 'Missing channel_id'}, status=400)

        # Check if subscription exists
        subscription_exists = Subscription.objects.filter(
            subscriber=request.user,
            channel_id=channel_id
        ).exists()

        # Determine action based on current state and requested action
        if action == 'toggle':
            if subscription_exists:
                # Unsubscribe
                Subscription.objects.filter(
                    subscriber=request.user,
                    channel_id=channel_id
                ).delete()
                is_subscribed = False
            else:
                # Subscribe
                Subscription.objects.create(
                    subscriber=request.user,
                    channel_id=channel_id
                )
                is_subscribed = True
        elif action == 'subscribe' and not subscription_exists:
            # Subscribe only if not already subscribed
            Subscription.objects.create(
                subscriber=request.user,
                channel_id=channel_id
            )
            is_subscribed = True
        elif action == 'unsubscribe' and subscription_exists:
            # Unsubscribe only if currently subscribed
            Subscription.objects.filter(
                subscriber=request.user,
                channel_id=channel_id
            ).delete()
            is_subscribed = False
        else:
            # No change needed
            is_subscribed = subscription_exists

        # Get subscriber count for this channel
        subscriber_count = Subscription.objects.filter(channel_id=channel_id).count()

        return JsonResponse({
            'success': True,
            'is_subscribed': is_subscribed,
            'subscriber_count': subscriber_count
        })

    except Exception as e:
        logger.error(f"Error toggling subscription: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
def check_subscription(request, channel_id):
    """
    API endpoint to check if user is subscribed to a channel
    """
    try:
        is_subscribed = Subscription.objects.filter(
            subscriber=request.user,
            channel_id=channel_id
        ).exists()
        
        # Get subscriber count for this channel
        subscriber_count = Subscription.objects.filter(channel_id=channel_id).count()
        
        return JsonResponse({
            'success': True,
            'is_subscribed': is_subscribed,
            'subscriber_count': subscriber_count
        })
    except Exception as e:
        logger.error(f"Error checking subscription: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
def get_subscriptions(request):
    """
    API endpoint to get user's subscriptions
    """
    try:
        subscriptions = Subscription.objects.filter(subscriber=request.user).order_by('-subscribed_at')
        
        # Collect channel_ids to fetch profiles from GCS
        channel_ids = [sub.channel_id for sub in subscriptions]
        
        # Prepare subscription data with available info
        subscription_data = []
        from .gcs_storage import get_user_profile_from_gcs
        
        for channel_id in channel_ids:
            try:
                # Try to get channel profile from GCS
                channel_profile = get_user_profile_from_gcs(channel_id)
                
                if channel_profile:
                    subscription_data.append({
                        'channel_id': channel_id,
                        'display_name': channel_profile.get('display_name', channel_id.replace('@', '')),
                        'avatar_url': channel_profile.get('avatar_url', ''),
                        'subscriber_count': Subscription.objects.filter(channel_id=channel_id).count()
                    })
                else:
                    # Fallback if profile not found
                    subscription_data.append({
                        'channel_id': channel_id,
                        'display_name': channel_id.replace('@', ''),
                        'avatar_url': '',
                        'subscriber_count': Subscription.objects.filter(channel_id=channel_id).count()
                    })
            except Exception as profile_error:
                logger.error(f"Error fetching profile for {channel_id}: {profile_error}")
                # Add with minimal information
                subscription_data.append({
                    'channel_id': channel_id,
                    'display_name': channel_id.replace('@', ''),
                    'avatar_url': '',
                    'subscriber_count': Subscription.objects.filter(channel_id=channel_id).count()
                })
        
        return JsonResponse({
            'success': True,
            'subscriptions': subscription_data
        })
    except Exception as e:
        logger.error(f"Error getting subscriptions: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

def base_context_processor(request):
    """
    Context processor for adding profile information and subscription count for base.html
    Register this in settings.py in TEMPLATES['OPTIONS']['context_processors']
    """
    context = {}
    
    if request.user.is_authenticated:
        try:
            # Get profile from GCS to access avatar URL
            from .gcs_storage import get_user_profile_from_gcs
            gcs_profile = get_user_profile_from_gcs(request.user.username)
            
            if gcs_profile and 'avatar_url' in gcs_profile:
                context['user_avatar_url'] = gcs_profile['avatar_url']
                
            context['subscription_count'] = Subscription.objects.filter(subscriber=request.user).count()
        except Exception as e:
            logger.error(f"Error loading user profile for context: {e}")
    
    return context

def search_page(request):
    """
    Dedicated search page with just a search box (Google-like)
    """
    return render(request, 'main/search_page.html')

def toggle_video_like(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid method'}, status=405)

    try:
        video_id = request.POST.get('video_id')
        user_id = request.POST.get('user_id')

        if not video_id or not user_id:
            return JsonResponse({'success': False, 'error': 'Missing video_id or user_id'}, status=400)

        # Разделяем составной ID, если он передан
        if '__' in video_id:
            user_id, video_id = video_id.split('__', 1)

        # Получаем метаданные видео
        metadata = get_video_metadata(user_id, video_id)
        if not metadata:
            return JsonResponse({'success': False, 'error': 'Video not found'}, status=404)

        # Используем транзакцию для атомарного обновления
        with transaction.atomic():
            try:
                existing_like = VideoLike.objects.get(
                    user=request.user,
                    video_id=video_id,
                    video_owner=user_id
                )
                if existing_like.is_like:
                    # Удаляем лайк
                    metadata['likes'] = max(0, int(metadata.get('likes', 0)) - 1)
                    existing_like.delete()
                    is_liked = False
                else:
                    # Меняем дизлайк на лайк
                    metadata['likes'] = int(metadata.get('likes', 0)) + 1
                    metadata['dislikes'] = max(0, int(metadata.get('dislikes', 0)) - 1)
                    existing_like.is_like = True
                    existing_like.save()
                    is_liked = True
            except VideoLike.DoesNotExist:
                # Новый лайк
                metadata['likes'] = int(metadata.get('likes', 0)) + 1
                VideoLike.objects.create(
                    user=request.user,
                    video_id=video_id,
                    video_owner=user_id,
                    is_like=True
                )
                is_liked = True

            # Обновляем метаданные в GCS
            bucket = get_bucket()
            if not bucket:
                return JsonResponse({'success': False, 'error': 'Failed to access storage'}, status=500)

            metadata_path = f"{user_id}/metadata/{video_id}.json"
            metadata_blob = bucket.blob(metadata_path)
            if not metadata_blob.exists():
                return JsonResponse({'success': False, 'error': 'Metadata not found'}, status=404)

            metadata_blob.upload_from_string(json.dumps(metadata, indent=2), content_type='application/json')

        return JsonResponse({
            'success': True,
            'likes': metadata['likes'],
            'dislikes': metadata.get('dislikes', 0),
            'is_liked': is_liked,
            'is_disliked': False
        })

    except Exception as e:
        logger.error(f"Error toggling like: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
def toggle_video_dislike(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid method'}, status=405)

    try:
        video_id = request.POST.get('video_id')
        user_id = request.POST.get('user_id')

        if not video_id or not user_id:
            return JsonResponse({'success': False, 'error': 'Missing video_id or user_id'}, status=400)

        # Разделяем составной ID
        if '__' in video_id:
            user_id, video_id = video_id.split('__', 1)

        # Получаем метаданные видео
        metadata = get_video_metadata(user_id, video_id)
        if not metadata:
            return JsonResponse({'success': False, 'error': 'Video not found'}, status=404)

        # Используем транзакцию для атомарного обновления
        with transaction.atomic():
            try:
                existing_like = VideoLike.objects.get(
                    user=request.user,
                    video_id=video_id,
                    video_owner=user_id
                )
                if not existing_like.is_like:
                    # Удаляем дизлайк
                    metadata['dislikes'] = max(0, int(metadata.get('dislikes', 0)) - 1)
                    existing_like.delete()
                    is_disliked = False
                else:
                    # Меняем лайк на дизлайк
                    metadata['dislikes'] = int(metadata.get('dislikes', 0)) + 1
                    metadata['likes'] = max(0, int(metadata.get('likes', 0)) - 1)
                    existing_like.is_like = False
                    existing_like.save()
                    is_disliked = True
            except VideoLike.DoesNotExist:
                # Новый дизлайк
                metadata['dislikes'] = int(metadata.get('dislikes', 0)) + 1
                VideoLike.objects.create(
                    user=request.user,
                    video_id=video_id,
                    video_owner=user_id,
                    is_like=False
                )
                is_disliked = True

            # Обновляем метаданные в GCS
            bucket = get_bucket()
            if not bucket:
                return JsonResponse({'success': False, 'error': 'Failed to access storage'}, status=500)

            metadata_path = f"{user_id}/metadata/{video_id}.json"
            metadata_blob = bucket.blob(metadata_path)
            if not metadata_blob.exists():
                return JsonResponse({'success': False, 'error': 'Metadata not found'}, status=404)

            metadata_blob.upload_from_string(json.dumps(metadata, indent=2), content_type='application/json')

        return JsonResponse({
            'success': True,
            'likes': metadata.get('likes', 0),
            'dislikes': metadata['dislikes'],
            'is_liked': False,
            'is_disliked': is_disliked
        })

    except Exception as e:
        logger.error(f"Error toggling dislike: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

def get_video_like_status(request, video_id):
    if not request.user.is_authenticated:
        return JsonResponse({
            'success': True,
            'is_liked': False,
            'is_disliked': False,
            'authenticated': False
        })

    try:
        user_id = request.GET.get('user_id')
        if '__' in video_id:
            user_id, video_id = video_id.split('__', 1)

        try:
            existing_like = VideoLike.objects.get(
                user=request.user,
                video_id=video_id,
                video_owner=user_id
            )
            return JsonResponse({
                'success': True,
                'is_liked': existing_like.is_like,
                'is_disliked': not existing_like.is_like,
                'authenticated': True
            })
        except VideoLike.DoesNotExist:
            return JsonResponse({
                'success': True,
                'is_liked': False,
                'is_disliked': False,
                'authenticated': True
            })
    except Exception as e:
        logger.error(f"Error getting like status: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
    
def channel_view(request, username):
    """
    View for displaying a channel/author page
    
    Args:
        request: HTTP request
        username: The channel's username (with or without @ prefix)
    """
    try:
        # Ensure username has @ prefix for GCS storage
        if not username.startswith('@'):
            username = '@' + username
            
        # Get channel profile information from GCS
        from .gcs_storage import get_user_profile_from_gcs, list_user_videos
        
        # Get channel profile
        channel = get_user_profile_from_gcs(username)
        
        if not channel:
            messages.error(request, f'Канал {username} не найден')
            return redirect('index')
        
        # Get channel videos with pagination
        try:
            offset = int(request.GET.get('offset', 0))
        except (ValueError, TypeError):
            offset = 0
            
        try:
            limit = int(request.GET.get('limit', 20))
        except (ValueError, TypeError):
            limit = 20
            
        # Get videos for the channel
        videos = []
        total_videos = 0
        
        # Get the GCS bucket
        from .gcs_storage import get_bucket, BUCKET_NAME, generate_video_url
        bucket = get_bucket(BUCKET_NAME)
        
        if bucket:
            # Get metadatafiles for the user
            metadata_prefix = f"{username}/metadata/"
            metadata_blobs = list(bucket.list_blobs(prefix=metadata_prefix))
            
            # Process metadata files
            for blob in metadata_blobs:
                if blob.name.endswith('.json'):
                    try:
                        import json
                        from datetime import datetime
                        
                        # Get video metadata
                        metadata = json.loads(blob.download_as_text())
                        
                        # Add user information
                        metadata['user_id'] = username
                        metadata['display_name'] = channel.get('display_name', username.replace('@', ''))
                        
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
                        
                        # Add thumbnail URL
                        if 'thumbnail_path' in metadata:
                            metadata['thumbnail_url'] = generate_video_url(
                                username, 
                                metadata['video_id'], 
                                file_path=metadata['thumbnail_path'], 
                                expiration_time=3600
                            )
                        
                        videos.append(metadata)
                    except Exception as e:
                        logger.error(f"Error processing metadata for {blob.name}: {e}")
            
            # Sort videos by upload date (newest first)
            videos.sort(key=lambda x: x.get('upload_date', ''), reverse=True)
            total_videos = len(videos)
            
            # Apply pagination
            videos = videos[offset:offset + limit]
        
        # Add channel statistics if not present
        if 'stats' not in channel:
            channel['stats'] = {
                'videos_count': total_videos,
                'subscribers': 0  # Placeholder since we don't have real subscriber data
            }
        else:
            # Update videos count
            channel['stats']['videos_count'] = total_videos
        
        return render(request, 'main/channel.html', {
            'channel': channel,
            'videos': videos,
            'total_videos': total_videos
        })
        
    except Exception as e:
        import traceback
        logger.error(f"Error in channel view: {e}")
        logger.error(traceback.format_exc())
        
        messages.error(request, f'Ошибка при загрузке информации о канале: {e}')
        return redirect('index')