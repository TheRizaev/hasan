from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse

class Category(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

class Channel(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

class Video(models.Model):
    title = models.CharField(max_length=200)
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    views = models.CharField(max_length=20)
    upload_date = models.DateTimeField(auto_now_add=True)
    age_text = models.CharField(max_length=50)  # "1 неделя назад", и т.д.
    duration = models.CharField(max_length=10)
    # Removed thumbnail field since we're using GCS for storage
    
    def __str__(self):
        return self.title
    
    
class UserProfile(models.Model):
    GENDER_CHOICES = (
        ('M', 'Мужской'),
        ('F', 'Женский'),
    )
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    bio = models.TextField(max_length=500, blank=True)
    # Removed profile_picture since we're using GCS for storage
    date_joined = models.DateTimeField(auto_now_add=True)
    date_of_birth = models.DateField(null=True, blank=True)
    display_name = models.CharField(max_length=50, blank=True, null=True)  # Added display_name field
    email_verified = models.BooleanField(default=False)
    # Добавляем поле для пола
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, blank=True, null=True)
    
    # Author fields
    is_author = models.BooleanField(default=False)
    author_application_pending = models.BooleanField(default=False)
    expertise_areas = models.ManyToManyField('ExpertiseArea', blank=True, related_name='experts')
    credentials = models.TextField(blank=True, help_text="Education, certificates and experience")
    
    def __str__(self):
        return f'{self.user.username} Profile'
        
    def get_absolute_url(self):
        return reverse('profile')

class VideoLike(models.Model):
    """
    Model to store video likes and dislikes
    
    This model tracks user interactions with videos (likes/dislikes)
    and ensures each user can only have one interaction per video.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='video_likes')
    video_id = models.CharField(max_length=255)
    video_owner = models.CharField(max_length=255)  # Video owner's user_id (renamed from user_id)
    is_like = models.BooleanField()  # True for like, False for dislike
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('user', 'video_id', 'video_owner')
        verbose_name = 'Video Like'
        verbose_name_plural = 'Video Likes'
        
    def __str__(self):
        action = "liked" if self.is_like else "disliked"
        return f"{self.user.username} {action} video {self.video_id} by {self.video_owner}"
    
class VideoView(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)  # Null для неавторизованных
    video_id = models.CharField(max_length=255)  # ID видео в GCS
    video_owner = models.CharField(max_length=255)  # Владелец видео (user_id)
    session_id = models.CharField(max_length=255, null=True, blank=True)  # Для неавторизованных пользователей
    viewed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [
            ('user', 'video_id', 'video_owner'),  # Уникальность для авторизованных
            ('session_id', 'video_id', 'video_owner'),  # Уникальность для неавторизованных
        ]
    
class Subscription(models.Model):
    """
    Model to track user subscriptions to channels
    """
    subscriber = models.ForeignKey(User, on_delete=models.CASCADE, related_name='subscriptions')
    channel_id = models.CharField(max_length=255)  # User ID (with @ prefix) of the channel/author
    subscribed_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('subscriber', 'channel_id')
        verbose_name = 'Subscription'
        verbose_name_plural = 'Subscriptions'
        
    def __str__(self):
        return f"{self.subscriber.username} subscribed to {self.channel_id}"    

# Add new model for expertise areas
class ExpertiseArea(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    
    def __str__(self):
        return self.name
    
