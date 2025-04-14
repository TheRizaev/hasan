
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
logger = logging.getLogger(__name__)

def custom_page_not_found(request, exception):
    return render(request, 'main/404.html', status=404)


def index(request):
    categories = Category.objects.all()
    
    try:
        from .gcs_storage import list_user_videos, get_bucket, BUCKET_NAME, generate_video_url, get_user_profile_from_gcs
        import random
        import concurrent.futures
        from datetime import datetime
        
        logger.info("Starting video loading for index page")
        
        # Get the bucket
        bucket = get_bucket(BUCKET_NAME)
        if not bucket:
            logger.error("Failed to get bucket")
            return render(request, 'main/index.html', {'categories': categories, 'gcs_videos': []})
        
        logger.info(f"Connected to bucket: {BUCKET_NAME}")
        
        # Get the list of users by listing top-level directories (FIX: removed 'videos/' prefix)
        blobs = bucket.list_blobs(delimiter='/')
        prefixes = list(blobs.prefixes)
        users = [prefix.replace('/', '') for prefix in prefixes]
        logger.info(f"Found {len(users)} users: {users}")
        
        if not users:
            logger.warning("No users found in GCS")
            return render(request, 'main/index.html', {'categories': categories, 'gcs_videos': []})
        
        # Cache for user profiles
        user_profiles = {}
        all_videos = []
        
        # Function to load videos for a single user
        def load_user_videos_and_profile(user):
            try:
                logger.info(f"Loading profile and videos for user: {user}")
                user_profile = get_user_profile_from_gcs(user)
                user_videos = list_user_videos(user)
                logger.info(f"Loaded {len(user_videos)} videos for user {user}")
                return (user, user_profile, user_videos)
            except Exception as e:
                logger.error(f"Error loading data for user {user}: {e}")
                return (user, None, [])
        
        # Use ThreadPoolExecutor for parallel loading
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(load_user_videos_and_profile, user) for user in users]
            
            for future in concurrent.futures.as_completed(futures):
                try:
                    user, profile, videos = future.result()
                    if profile:
                        user_profiles[user] = profile
                    all_videos.extend([
                        {**video, 'user_id': user, 'display_name': profile.get('display_name', user.replace('@', '')) if profile else user.replace('@', '')}
                        for video in videos
                    ])
                except Exception as e:
                    logger.error(f"Error processing result: {e}")
        
        logger.info(f"Total videos loaded: {len(all_videos)}")
        
        if not all_videos:
            logger.warning("No videos found across all users")
            return render(request, 'main/index.html', {'categories': categories, 'gcs_videos': []})
        
        # Shuffle videos for variety
        random.shuffle(all_videos)
        
        # Limit to 20 videos
        selected_videos = all_videos[:20]
        
        # Add URLs for each video
        for video in selected_videos:
            video_id = video.get('video_id')
            user_id = video.get('user_id')
            if video_id and user_id:
                video['url'] = generate_video_url(user_id, video_id, expiration_time=3600)
                if 'thumbnail_path' in video:
                    video['thumbnail_url'] = generate_video_url(
                        user_id, video_id, file_path=video['thumbnail_path'], expiration_time=3600
                    )
                
                video['channel'] = video.get('display_name', video.get('user_id', ''))
                views = video.get('views', 0)
                if isinstance(views, (int, str)) and str(views).isdigit():
                    views = int(views)
                    video['views_formatted'] = f"{views // 1000}K просмотров" if views >= 1000 else f"{views} просмотров"
                else:
                    video['views_formatted'] = "0 просмотров"
                
                upload_date = video.get('upload_date', '')
                if upload_date:
                    try:
                        upload_datetime = datetime.fromisoformat(upload_date)
                        video['upload_date_formatted'] = upload_datetime.strftime("%d.%m.%Y")
                    except Exception:
                        video['upload_date_formatted'] = upload_date[:10] if upload_date else "Недавно"
        
        logger.info(f"Prepared {len(selected_videos)} videos for display")
        return render(request, 'main/index.html', {
            'categories': categories,
            'gcs_videos': selected_videos
        })
    
    except Exception as e:
        logger.error(f"Error fetching GCS videos: {e}")
        return render(request, 'main/index.html', {'categories': categories, 'gcs_videos': []})

def video_detail(request, video_id):
    """
    Показывает подробную информацию о видео из GCS.
    Оптимизированная версия с улучшенной обработкой отображаемых имен.
    
    Args:
        request: HTTP request
        video_id: ID видео (строка в формате gcs_video_id)
    """
    try:
        # Проверяем, содержит ли video_id информацию о пользователе
        # Формат видео ID либо как username__video_id либо просто video_id
        if '__' in video_id:
            # Если ID содержит разделитель, разбиваем его
            user_id, gcs_video_id = video_id.split('__')
        else:
            # Если старый формат или нет пользователя, ищем в метаданных всех видео
            gcs_video_id = video_id
            user_id = None
            
            from .gcs_storage import get_bucket, BUCKET_NAME
            bucket = get_bucket(BUCKET_NAME)
            
            if bucket:
                # Получаем список пользователей
                blobs = bucket.list_blobs(delimiter='/')
                prefixes = list(blobs.prefixes)
                users = [prefix.replace('/', '') for prefix in prefixes]
                
                # Ищем видео среди всех пользователей
                from .gcs_storage import get_video_metadata
                for user in users:
                    metadata = get_video_metadata(user, gcs_video_id)
                    if metadata:  # Если нашли видео, используем этого пользователя
                        user_id = user
                        break
        
        if not user_id:
            logger.error(f"Could not find user for video {gcs_video_id}")
            return render(request, 'main/404.html', status=404)
            
        # Оптимизация: загружаем всю необходимую информацию параллельно
        import concurrent.futures
        from .gcs_storage import get_video_metadata, generate_video_url, get_video_comments, get_user_profile_from_gcs
        
        # Функции для параллельного выполнения
        def fetch_metadata():
            return get_video_metadata(user_id, gcs_video_id)
            
        def fetch_user_profile():
            return get_user_profile_from_gcs(user_id)
            
        def fetch_comments():
            return get_video_comments(user_id, gcs_video_id)
            
        # Выполняем запросы параллельно
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            metadata_future = executor.submit(fetch_metadata)
            profile_future = executor.submit(fetch_user_profile)
            comments_future = executor.submit(fetch_comments)
            
            # Получаем результаты
            metadata = metadata_future.result()
            user_profile = profile_future.result()
            comments_data = comments_future.result()
        
        if not metadata:
            logger.error(f"Could not find metadata for video {gcs_video_id} from user {user_id}")
            return render(request, 'main/404.html', status=404)
        
        # Получаем display_name пользователя для корректного отображения автора
        display_name = user_profile.get('display_name', user_id.replace('@', '')) if user_profile else user_id.replace('@', '')
            
        # Получаем временный URL для видео
        video_url = generate_video_url(user_id, gcs_video_id, expiration_time=3600)
        
        # Получаем URL для превью, если оно есть
        thumbnail_url = None
        if "thumbnail_path" in metadata:
            thumbnail_url = generate_video_url(
                user_id, 
                gcs_video_id, 
                file_path=metadata["thumbnail_path"], 
                expiration_time=3600
            )
        
        # Подготавливаем данные для шаблона
        video_data = {
            'id': f"{user_id}__{gcs_video_id}",  # Составной ID для URL
            'gcs_id': gcs_video_id,              # Оригинальный ID в GCS
            'user_id': user_id,                  # ID пользователя (владельца)
            'title': metadata.get('title', 'Без названия'),
            'description': metadata.get('description', 'Без описания'),
            'channel': display_name,             # Используем display_name из профиля
            'display_name': display_name,        # Явно добавляем display_name
            'views': metadata.get('views', 0),
            'views_formatted': f"{metadata.get('views', 0)} просмотров",
            'likes': metadata.get('likes', 0),
            'dislikes': metadata.get('dislikes', 0),
            'duration': metadata.get('duration', '00:00'),
            'video_url': video_url,
            'thumbnail_url': thumbnail_url,
            # Форматирование даты загрузки
            'upload_date': metadata.get('upload_date', ''),
            'age': metadata.get('age_text', 'Недавно')
        }
        
        # Получаем рекомендуемые видео с помощью оптимизированной функции
        recommended_videos = get_recommended_videos(user_id, gcs_video_id)
        
        return render(request, 'main/video.html', {
            'video': video_data,
            'comments': comments_data.get('comments', []),
            'recommended_videos': recommended_videos
        })
    except Exception as e:
        logger.error(f"Error loading video details: {e}")
        return render(request, 'main/404.html', status=404)
        
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
    query = request.GET.get('query', '')
    
    if not query:
        return render(request, 'main/search.html', {'query': query, 'videos': []})
    
    # Реализация поиска с использованием GCS
    try:
        from .gcs_storage import list_user_videos, get_bucket, BUCKET_NAME, generate_video_url
        
        # Получаем бакет
        bucket = get_bucket(BUCKET_NAME)
        if not bucket:
            return render(request, 'main/search.html', {'query': query, 'videos': []})
            
        # Получаем список пользователей
        blobs = bucket.list_blobs(delimiter='/')
        prefixes = list(blobs.prefixes)
        users = [prefix.replace('/', '') for prefix in prefixes]
        
        # Ищем среди всех видео
        search_results = []
        for user_id in users:
            user_videos = list_user_videos(user_id)
            if user_videos:
                for video in user_videos:
                    # Добавляем user_id к каждому видео
                    if 'user_id' not in video:
                        video['user_id'] = user_id
                    
                    # Проверяем соответствие поисковому запросу
                    title = video.get('title', '').lower()
                    description = video.get('description', '').lower()
                    channel = user_id.lower()  # Поиск по имени пользователя
                    
                    # Если найдено совпадение, добавляем видео в результаты
                    if (query.lower() in title or 
                        query.lower() in description or 
                        query.lower() in channel):
                        
                        # Добавляем URL для видео
                        video_id = video.get('video_id')
                        video['url'] = f"/video/{user_id}__{video_id}/"
                        
                        # Добавляем URL для миниатюры
                        if 'thumbnail_path' in video:
                            video['thumbnail_url'] = generate_video_url(
                                user_id, 
                                video_id, 
                                file_path=video['thumbnail_path'], 
                                expiration_time=3600
                            )
                            
                        # Форматируем данные для отображения
                        views = video.get('views', 0)
                        if isinstance(views, int) or (isinstance(views, str) and views.isdigit()):
                            views = int(views)
                            if views >= 1000:
                                video['views_formatted'] = f"{views // 1000}K просмотров"
                            else:
                                video['views_formatted'] = f"{views} просмотров"
                        else:
                            video['views_formatted'] = "0 просмотров"
                            
                        # Отображаемое имя канала
                        if 'channel' not in video:
                            video['channel'] = user_id
                            
                        search_results.append(video)
        
        return render(request, 'main/search.html', {
            'query': query,
            'videos': search_results
        })
    except Exception as e:
        logger.error(f"Error during search: {e}")
        return render(request, 'main/search.html', {
            'query': query,
            'videos': []
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
def studio_view(request):
    """
    View for the creator studio page.
    Only authenticated users who are approved authors can access this page.
    """
    # Проверяем, является ли пользователь автором
    if not request.user.profile.is_author:
        messages.error(request, 'У вас нет доступа к Студии. Вы должны стать автором, чтобы получить доступ.')
        return redirect('become_author')
        
    # Для демонстрации, мы будем использовать пустой список видео
    videos = []
    
    return render(request, 'studio/studio.html', {
        'videos': videos
    })

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