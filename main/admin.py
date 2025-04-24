# В main/admin.py
from django.contrib import admin
from .models import Category, Channel, Video, UserProfile, ExpertiseArea, Subscription

class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'is_author', 'author_application_pending', 'date_joined')
    list_filter = ('is_author', 'author_application_pending')
    search_fields = ('user__username', 'user__email')
    filter_horizontal = ('expertise_areas',)
    
    actions = ['approve_author', 'reject_author']
    
    def approve_author(self, request, queryset):
        for profile in queryset:
            profile.is_author = True
            profile.author_application_pending = False
            profile.save()
            
            # Можно добавить отправку уведомления пользователю
            
        self.message_user(request, f"{queryset.count()} заявок на авторство одобрено")
    approve_author.short_description = "Одобрить выбранные заявки на авторство"
    
    def reject_author(self, request, queryset):
        queryset.update(author_application_pending=False)
        self.message_user(request, f"{queryset.count()} заявок на авторство отклонено")
    reject_author.short_description = "Отклонить выбранные заявки на авторство"

class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('subscriber', 'channel_id', 'subscribed_at')
    list_filter = ('subscribed_at',)
    search_fields = ('subscriber__username', 'channel_id')
    date_hierarchy = 'subscribed_at'

admin.site.register(UserProfile, UserProfileAdmin)
admin.site.register(ExpertiseArea)
admin.site.register(Category)
admin.site.register(Channel)
admin.site.register(Video)
admin.site.register(Subscription, SubscriptionAdmin)