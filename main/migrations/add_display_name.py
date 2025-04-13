from django.db import migrations, models

def set_default_display_names(apps, schema_editor):
    """Устанавливает display_name для существующих пользователей, копируя его из username"""
    UserProfile = apps.get_model('main', 'UserProfile')
    for profile in UserProfile.objects.all():
        # Если username начинается с '@', берем его без '@'
        username = profile.user.username
        if username.startswith('@'):
            display_name = username[1:]
        else:
            display_name = username
            
        profile.display_name = display_name
        profile.save()

class Migration(migrations.Migration):

    dependencies = [
        ('main', '0006_auto_20250410_2320'),  # Замените на последнюю миграцию в вашем проекте
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='display_name',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.RunPython(set_default_display_names),
    ]