from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .models import UserProfile, ExpertiseArea
import re
from datetime import date
from django.core.exceptions import ValidationError

class UserRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    username = forms.CharField(
        required=True,
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'form-input username-input',
            'placeholder': 'username',
            'autocomplete': 'off'
        }),
        help_text="Латинские буквы и цифры, до 20 символов. Регистр не важен."
    )
    date_of_birth = forms.DateField(
        required=True,
        widget=forms.DateInput(attrs={
            'type': 'text', 
            'class': 'custom-date-picker',
            'placeholder': 'ДД.ММ.ГГГГ'
        }),
        help_text="Ваша дата рождения",
        input_formats=['%d.%m.%Y', '%d/%m/%Y', '%d-%m-%Y', '%Y-%m-%d', '%m/%d/%Y']
    )
    # Добавляем поле для пола
    GENDER_CHOICES = (
        ('M', 'Мужской'),
        ('F', 'Женский'),
    )
    gender = forms.ChoiceField(
        required=True, 
        choices=GENDER_CHOICES,
        widget=forms.RadioSelect(attrs={
            'class': 'gender-radio'
        }),
        label="Пол",
        help_text="Укажите ваш пол"
    )
    
    class Meta:
        model = User
        fields = ['username', 'email', 'date_of_birth', 'gender', 'password1', 'password2']
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('Этот email уже используется')
        return email
    
    def clean_username(self):
        username = self.cleaned_data.get('username')
        if not username:
            raise forms.ValidationError('Имя пользователя обязательно')
            
        # Convert to lowercase automatically
        username = username.lower()
        
        # Check if username contains only allowed characters (latin letters and numbers)
        if not re.match(r'^[a-z0-9]+$', username):
            raise forms.ValidationError('Имя пользователя может содержать только латинские буквы и цифры')
        
        # Check length
        if len(username) > 20:
            raise forms.ValidationError('Имя пользователя не должно превышать 20 символов')
            
        # Check if username already exists
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError('Это имя пользователя уже занято')
            
        # Return with @ prefix
        return '@' + username
        
    def clean_date_of_birth(self):
        dob = self.cleaned_data.get('date_of_birth')
        today = date.today()
        
        # Check if user is at least 13 years old
        age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        if age < 13:
            raise forms.ValidationError('Вам должно быть не менее 13 лет для регистрации')
            
        # Check if date is not in the future
        if dob > today:
            raise forms.ValidationError('Дата рождения не может быть в будущем')
            
        return dob

# Replace UserDetailsForm with DisplayNameForm
class DisplayNameForm(forms.ModelForm):
    display_name = forms.CharField(
        required=True,
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Как к вам обращаться'
        }),
        help_text="Это имя будет отображаться в вашем профиле и комментариях"
    )
    
    class Meta:
        model = UserProfile
        fields = ['display_name']
        
    def clean_display_name(self):
        display_name = self.cleaned_data.get('display_name')
        if not display_name:
            raise forms.ValidationError('Это поле обязательно')
        return display_name

class EmailVerificationForm(forms.Form):
    verification_code = forms.CharField(
        required=True,
        max_length=6,
        min_length=6,
        widget=forms.TextInput(attrs={'placeholder': 'Введите 6-значный код', 'class': 'verification-input'}),
        help_text="Введите 6-значный код, отправленный на вашу почту"
    )
    
    def clean_verification_code(self):
        code = self.cleaned_data.get('verification_code')
        if not code.isdigit():
            raise forms.ValidationError('Код подтверждения должен содержать только цифры')
        return code

class UserLoginForm(forms.Form):
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={'placeholder': 'Имя пользователя (без @)'})
    )
    password = forms.CharField(widget=forms.PasswordInput(attrs={'placeholder': 'Пароль'}))

    def clean_username(self):
        username = self.cleaned_data.get('username', '')
        # Remove @ if user entered it
        if username.startswith('@'):
            username = username[1:]
        # Then add @ back for authentication
        return '@' + username.lower()

class UserProfileForm(forms.ModelForm):
    display_name = forms.CharField(
        required=True,
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Как к вам обращаться'
        })
    )
    
    # Profile picture field is still defined here for form handling but is processed differently
    profile_picture = forms.ImageField(required=False)
    
    class Meta:
        model = UserProfile
        fields = ['display_name', 'bio', 'profile_picture']
        
class AuthorApplicationForm(forms.ModelForm):
    expertise_areas = forms.ModelMultipleChoiceField(
        queryset=ExpertiseArea.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=True
    )
    
    class Meta:
        model = UserProfile
        fields = ['credentials', 'expertise_areas']
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['credentials'].widget.attrs.update({
            'placeholder': 'Расскажите о своем образовании, опыте, сертификатах и почему вы хотите стать автором'
        })