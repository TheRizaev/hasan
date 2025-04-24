from django.urls import path
from . import views
from . import gcs_views 
from django.conf import settings

urlpatterns = [
    path('', views.index, name='index'),  # Main page
    path('video/<str:video_id>/', views.video_detail, name='video_detail_gcs'),  # Video detail page
    path('channel/<str:username>/', views.channel_view, name='channel'),  # Channel/Author page
    path('search/', views.search_results, name='search_results'),  # Search results page
    path('search-page/', views.search_page, name='search_page'),  # Google-like search page
    path('register/', views.register_view, name='register'),  # Registration page
    path('verify-email/', views.verify_email_view, name='verify_email'),  # Email verification page
    path('user-details/', views.user_details_view, name='user_details'),  # New user details page
    path('login/', views.login_view, name='login'),  # Login page
    path('logout/', views.logout_view, name='logout'),  # Logout handler
    path('profile/', views.profile_view, name='profile'),  # User profile
    path('profile/settings/', views.profile_settings_view, name='profile_settings'),  # Profile settings

    path('studio/', gcs_views.studio_view, name='studio'),  # Uses the new GCS-integrated view

    path('become-author/', views.author_application, name='become_author'),  # Author application
    
    # API endpoints for Google Cloud Storage
    path('api/upload-video/', gcs_views.upload_video_to_gcs, name='upload_video_to_gcs'),
    path('api/list-user-videos/', gcs_views.list_user_videos, name='list_user_videos'),
    path('api/list-user-videos/<str:username>/', gcs_views.list_user_videos, name='list_user_videos_for_user'),
    path('api/list-all-videos/', gcs_views.list_all_videos, name='list_all_videos'),
    path('api/delete-video/<str:video_id>/', gcs_views.delete_video_from_gcs, name='delete_video_from_gcs'),
    path('api/get-video-url/<str:video_id>/', gcs_views.get_video_url, name='get_video_url'),
    path('api/get-thumbnail-url/<str:video_id>/', gcs_views.get_thumbnail_url, name='get_thumbnail_url'),
    path('api/add-comment/', gcs_views.add_comment, name='add_comment'),
    path('api/add-reply/', gcs_views.add_reply, name='add_reply'),
    path('api/track-view/', gcs_views.track_video_view, name='track_video_view'),
    
    # New endpoint for getting user profiles with avatar
    path('api/get-user-profile/', views.get_user_profile, name='get_user_profile'),
    
    # New endpoints for like/dislike functionality
    path('api/toggle-video-like/', views.toggle_video_like, name='toggle_video_like'),
    path('api/toggle-video-dislike/', views.toggle_video_dislike, name='toggle_video_dislike'),
    path('api/video-like-status/<str:video_id>/', views.get_video_like_status, name='get_video_like_status'),
    
    path('api/toggle-subscription/', views.toggle_subscription, name='toggle_subscription'),
    path('api/check-subscription/<str:channel_id>/', views.check_subscription, name='check_subscription'),
    path('api/get-subscriptions/', views.get_subscriptions, name='get_subscriptions'),
]

if settings.DEBUG:
    from django.views.defaults import page_not_found
    urlpatterns.append(path('404/', lambda request: page_not_found(request, None)))