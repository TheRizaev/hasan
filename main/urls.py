from django.urls import path
from . import views
from . import gcs_views 
from django.conf import settings

urlpatterns = [
    path('', views.index, name='index'),  # Main page
    path('video/<str:video_id>/', views.video_detail, name='video_detail_gcs'),  # New GCS video detail page
    path('search/', views.search_results, name='search_results'),  # Search results page
    path('register/', views.register_view, name='register'),  # Registration page
    path('verify-email/', views.verify_email_view, name='verify_email'),  # Email verification page
    path('user-details/', views.user_details_view, name='user_details'),  # New user details page
    path('login/', views.login_view, name='login'),  # Login page
    path('logout/', views.logout_view, name='logout'),  # Logout handler
    path('profile/', views.profile_view, name='profile'),  # User profile
    path('profile/settings/', views.profile_settings_view, name='profile_settings'),  # Profile settings

    path('studio/', gcs_views.studio_view, name='studio'),  # Uses the new GCS-integrated view

    path('become-author/', views.author_application, name='become_author'),  # Author application
    
    # API для Google Cloud Storage
    path('api/upload-video/', gcs_views.upload_video_to_gcs, name='upload_video_to_gcs'),
    # path('api/list-videos/', gcs_views.list_videos_from_gcs, name='list_videos_from_gcs'),
    path('api/list-all-videos/', gcs_views.list_all_videos, name='list_all_videos'),
    path('api/delete-video/<str:video_id>/', gcs_views.delete_video_from_gcs, name='delete_video_from_gcs'),
    path('api/get-video-url/<str:video_id>/', gcs_views.get_video_url, name='get_video_url'),
    # Новый маршрут для получения URL миниатюры
    path('api/get-thumbnail-url/<str:video_id>/', gcs_views.get_thumbnail_url, name='get_thumbnail_url'),
    # Маршрут для обновления кэша метаданных
    path('api/refresh-metadata-cache/', gcs_views.refresh_metadata_cache, name='refresh_metadata_cache'),
]

if settings.DEBUG:
    from django.views.defaults import page_not_found
    urlpatterns.append(path('404/', lambda request: page_not_found(request, None)))