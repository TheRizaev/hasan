
from django.shortcuts import render, redirect
from .models import Video, Category
import random
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
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
        # Импортируем только необходимые функции
        from .gcs_storage import get_bucket, BUCKET_NAME
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info("Starting optimized video metadata loading for index page")
        
        # Смотрим, есть ли кэшированные данные в сессии и используем их, если они не устарели
        cached_videos = request.session.get('cached_videos', None)
        cached_timestamp = request.session.get('cached_videos_timestamp', 0)
        current_timestamp = int(datetime.datetime.now().timestamp())
        
        # Используем кэш, если он не старше 5 минут
        if cached_videos and (current_timestamp - cached_timestamp) < 300:
            logger.info(f"Using cached videos data ({len(cached_videos)} videos)")
            return render(request, 'main/index.html', {
                'categories': categories,
                'gcs_videos': cached_videos
            })
        
        # Запрашиваем только метаданные первых 20 видео через API
        # Этот API вызов должен быть оптимизирован в gcs_views.py
        response = requests.get(f"{request.scheme}://{request.get_host()}/api/list-all-videos/?only_metadata=true&limit=20")
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success') and data.get('videos'):
                selected_videos = data.get('videos')
                
                # Кэшируем результаты в сессии для последующих запросов
                request.session['cached_videos'] = selected_videos
                request.session['cached_videos_timestamp'] = current_timestamp
                
                logger.info(f"Successfully loaded {len(selected_videos)} video metadata from API")
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
    Improved search results page that works correctly with front-end
    """
    query = request.GET.get('query', '')
    offset = int(request.GET.get('offset', 0))
    limit = int(request.GET.get('limit', 20))
    json_response = request.GET.get('format') == 'json'
    
    debug_info = {
        'query': query,
        'offset': offset,
        'limit': limit,
        'debug_enabled': True,
        'scan_steps': [],
        'errors': []
    }
    
    if not query:
        if json_response:
            return JsonResponse({'videos': [], 'total': 0})
        return render(request, 'main/search.html', {'query': query, 'videos': []})
    
    # Search implementation using GCS - improved version
    try:
        from .gcs_storage import get_bucket, BUCKET_NAME, generate_video_url
        import logging
        
        logger = logging.getLogger(__name__)
        logger.info(f"Searching for: '{query}' with offset={offset}, limit={limit}")
        
        # Get bucket
        bucket = get_bucket(BUCKET_NAME)
        if not bucket:
            if json_response:
                return JsonResponse({'error': 'Failed to access storage', 'videos': []}, status=500)
            return render(request, 'main/search.html', {'query': query, 'videos': []})
            
        # Get list of users
        blobs = list(bucket.list_blobs(max_results=100))
        users = set()
        for blob in blobs:
            parts = blob.name.split('/')
            if parts and parts[0] and parts[0].startswith('@'):
                users.add(parts[0])
        
        debug_info['scan_steps'].append(f"Найдено пользователей: {len(users)}")
        debug_info['users'] = users[:10]  # Первые 10 пользователей для отладки
        
        # Поиск по всем пользователям и их видео
        search_results = []
        query_lower = query.lower()
        
        # Отдельно создаем список всех найденных видео для отладки
        all_videos_found = []
        
        # Перебираем всех пользователей
        for user_id in users:
            try:
                # Проверяем наличие метаданных
                metadata_prefix = f"{user_id}/metadata/"
                metadata_blobs = list(bucket.list_blobs(prefix=metadata_prefix))
                
                debug_info['scan_steps'].append(f"Пользователь {user_id}: найдено {len(metadata_blobs)} файлов метаданных")
                
                # Проверяем все файлы метаданных для поиска совпадений
                for blob in metadata_blobs:
                    try:
                        if blob.name.endswith('.json'):
                            metadata_text = blob.download_as_text()
                            video_data = json.loads(metadata_text)
                            
                            # Сохраняем название видео для отладки
                            video_title = video_data.get('title', 'Без названия')
                            all_videos_found.append({
                                'user_id': user_id,
                                'video_id': video_data.get('video_id', 'unknown'),
                                'title': video_title
                            })
                            
                            # Проверяем на совпадение в заголовке и описании, учитывая регистр
                            title = (video_data.get('title') or '').lower()
                            description = (video_data.get('description') or '').lower()
                            
                            if query_lower in title or query_lower in description:
                                debug_info['scan_steps'].append(f"СОВПАДЕНИЕ найдено в видео: {video_title}")
                                
                                # Добавляем user_id к видео, если его нет
                                if 'user_id' not in video_data:
                                    video_data['user_id'] = user_id
                                
                                # Форматируем просмотры для отображения
                                views = video_data.get('views', 0)
                                if isinstance(views, (int, str)) and str(views).isdigit():
                                    views = int(views)
                                    video_data['views_formatted'] = f"{views // 1000}K просмотров" if views >= 1000 else f"{views} просмотров"
                                else:
                                    video_data['views_formatted'] = "0 просмотров"
                                
                                # Форматируем дату загрузки
                                upload_date = video_data.get('upload_date', '')
                                if upload_date:
                                    try:
                                        from datetime import datetime
                                        upload_datetime = datetime.fromisoformat(upload_date)
                                        video_data['upload_date_formatted'] = upload_datetime.strftime("%d.%m.%Y")
                                    except Exception as e:
                                        video_data['upload_date_formatted'] = upload_date[:10] if upload_date else "Недавно"
                                        debug_info['errors'].append(f"Ошибка форматирования даты: {str(e)}")
                                
                                # Добавляем в результаты поиска
                                search_results.append(video_data)
                    except Exception as e:
                        error_msg = f"Ошибка при обработке метаданных {blob.name}: {str(e)}"
                        logger.error(error_msg)
                        debug_info['errors'].append(error_msg)
            except Exception as e:
                error_msg = f"Ошибка при обработке пользователя {user_id}: {str(e)}"
                logger.error(error_msg)
                debug_info['errors'].append(error_msg)
        
        # Сохраняем первые 10 видео из всех найденных для отладки
        debug_info['all_videos_sample'] = all_videos_found[:10]
        debug_info['total_videos_found'] = len(all_videos_found)
        
        # Записываем в отладочную информацию, если видео с "CORE" в названии
        core_videos = [v for v in all_videos_found if 'CORE' in v.get('title', '').upper()]
        debug_info['core_videos_count'] = len(core_videos)
        debug_info['core_videos'] = core_videos[:5]  # Первые 5 видео с CORE в названии
        
        # Если результатов нет, логируем это
        if not search_results:
            msg = f"По запросу '{query}' ничего не найдено"
            logger.warning(msg)
            debug_info['scan_steps'].append(msg)
        else:
            debug_info['scan_steps'].append(f"Всего найдено результатов: {len(search_results)}")
        
        # Сортируем результаты по релевантности
        def sort_by_relevance(video):
            title = (video.get('title') or '').lower()
            description = (video.get('description') or '').lower()
            
            if title == query_lower:
                return 0  # Точное совпадение с заголовком
            elif title.startswith(query_lower):
                return 1  # Заголовок начинается с запроса
            elif query_lower in title:
                return 2  # Запрос содержится в заголовке
            elif description == query_lower:
                return 3  # Точное совпадение с описанием
            elif description.startswith(query_lower):
                return 4  # Описание начинается с запроса
            else:
                return 5  # Запрос содержится в описании
                
        search_results.sort(key=sort_by_relevance)
        
        # Применяем пагинацию
        total_results = len(search_results)
        paginated_results = search_results[offset:offset + limit]
        
        debug_info['total_results'] = total_results
        debug_info['results_returned'] = len(paginated_results)
        
        # Формируем ответ в JSON для AJAX
        if json_response:
            return JsonResponse({
                'success': True,
                'videos': paginated_results,
                'total': total_results,
                'debug': debug_info
            })
        
        # Обычный HTML-ответ для страницы
        return render(request, 'main/search.html', {
            'query': query,
            'videos': paginated_results,
            'total': total_results,
            'debug': debug_info
        })
    except Exception as e:
        import traceback
        error_msg = f"Общая ошибка при поиске: {str(e)}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        
        debug_info['errors'].append(error_msg)
        debug_info['traceback'] = traceback.format_exc()
        
        if json_response:
            return JsonResponse({'error': str(e), 'videos': [], 'debug': debug_info}, status=500)
        return render(request, 'main/search.html', {
            'query': query,
            'videos': [],
            'error': str(e),
            'debug': debug_info
        })

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

def base_context_processor(request):
    """
    Context processor for adding profile information for base.html
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
        except Exception as e:
            # Log error but don't break the page
            logger.error(f"Error loading user profile for context: {e}")
    
    return context

def search_page(request):
    """
    Dedicated search page with just a search box (Google-like)
    """
    return render(request, 'main/search_page.html')

def debug_storage(request):
    """
    Страница для отладки хранилища GCS
    """
    context = {
        'debug_info': {
            'title': 'Отладка хранилища GCS',
            'storage_name': None,
            'connection_status': 'Неизвестно',
            'users': [],
            'user_count': 0,
            'videos': [],
            'video_count': 0,
            'errors': []
        }
    }
    
    try:
        from .gcs_storage import get_bucket, BUCKET_NAME
        import json
        
        context['debug_info']['storage_name'] = BUCKET_NAME
        
        # Получаем бакет
        bucket = get_bucket(BUCKET_NAME)
        if not bucket:
            context['debug_info']['connection_status'] = 'Ошибка: не удалось подключиться к хранилищу'
            context['debug_info']['errors'].append('Не удалось получить бакет')
            return render(request, 'main/debug_storage.html', context)
        
        context['debug_info']['connection_status'] = 'Подключение установлено'
        
        # Получаем список пользователей
        blobs = bucket.list_blobs(delimiter='/')
        prefixes = list(blobs.prefixes)
        users = [prefix.replace('/', '') for prefix in prefixes if not prefix.startswith('system/')]
        
        context['debug_info']['users'] = users
        context['debug_info']['user_count'] = len(users)
        
        # Получаем информацию о видео в хранилище
        videos_info = []
        videos_with_core = []
        
        for user_id in users[:5]:  # Ограничимся первыми 5 пользователями для скорости
            # Ищем папку metadata для пользователя
            metadata_prefix = f"{user_id}/metadata/"
            metadata_blobs = list(bucket.list_blobs(prefix=metadata_prefix))
            
            for blob in metadata_blobs:
                if blob.name.endswith('.json'):
                    try:
                        metadata_text = blob.download_as_text()
                        metadata = json.loads(metadata_text)
                        video_title = metadata.get('title', 'Без названия')
                        video_id = metadata.get('video_id', 'unknown')
                        
                        video_info = {
                            'user_id': user_id,
                            'video_id': video_id,
                            'title': video_title,
                            'path': blob.name
                        }
                        
                        videos_info.append(video_info)
                        
                        # Проверяем наличие CORE в названии
                        if 'CORE' in video_title.upper():
                            videos_with_core.append(video_info)
                    except Exception as e:
                        context['debug_info']['errors'].append(f"Ошибка при обработке метаданных {blob.name}: {str(e)}")
        
        context['debug_info']['videos'] = videos_info
        context['debug_info']['video_count'] = len(videos_info)
        context['debug_info']['videos_with_core'] = videos_with_core
        context['debug_info']['videos_with_core_count'] = len(videos_with_core)
        
    except Exception as e:
        import traceback
        context['debug_info']['errors'].append(f"Общая ошибка: {str(e)}")
        context['debug_info']['traceback'] = traceback.format_exc()
    
    return render(request, 'main/debug_storage.html', context)