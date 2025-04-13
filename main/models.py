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
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    bio = models.TextField(max_length=500, blank=True)
    # Removed profile_picture since we're using GCS for storage
    date_joined = models.DateTimeField(auto_now_add=True)
    date_of_birth = models.DateField(null=True, blank=True)
    display_name = models.CharField(max_length=50, blank=True, null=True)  # Added display_name field
    email_verified = models.BooleanField(default=False)
    
    # Author fields
    is_author = models.BooleanField(default=False)
    author_application_pending = models.BooleanField(default=False)
    expertise_areas = models.ManyToManyField('ExpertiseArea', blank=True, related_name='experts')
    credentials = models.TextField(blank=True, help_text="Education, certificates and experience")
    
    def __str__(self):
        return f'{self.user.username} Profile'
        
    def get_absolute_url(self):
        return reverse('profile')


# Add new model for expertise areas
class ExpertiseArea(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    
    def __str__(self):
        return self.name