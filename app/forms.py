import re
from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from .models import *
from django.utils import timezone
import datetime

User = get_user_model()

PHONE_VALIDATOR = RegexValidator(
    regex=r'^\d{10}$',
    message='Phone number must be exactly 10 digits.'
)

class RegistrationForm(forms.ModelForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'placeholder': 'email@example.com',
            'autocomplete': 'email'
        })
    )
    phone_number = forms.CharField(
        required=True,
        validators=[PHONE_VALIDATOR],
        max_length=10,
        widget=forms.TextInput(attrs={
            'type': 'tel',
            'maxlength': '10',
            'pattern': '\\d{10}',
            'inputmode': 'numeric',
            'placeholder': '10 digits'
        })
    )
    password = forms.CharField(widget=forms.PasswordInput, min_length=8)
    confirm_password = forms.CharField(widget=forms.PasswordInput, min_length=8)

    class Meta:
        model = User
        fields = ['username', 'email', 'phone_number', 'password', 'confirm_password']
        widgets = {
            'user_type': forms.Select(),
        }

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("A user with that email already exists.")
        return email

    def clean_password(self):
        password = self.cleaned_data.get('password')
        if password:
            errors = []
            if len(password) < 8:
                errors.append("Password must contain at least 8 characters.")
            if not re.search(r'[A-Z]', password):
                errors.append("Password must contain at least one uppercase letter.")
            if not re.search(r'[a-z]', password):
                errors.append("Password must contain at least one lowercase letter.")
            if not re.search(r'\d', password):
                errors.append("Password must contain at least one digit.")
            if not re.search(r'[!@#$%^&*()_+\-=[\]{};:\"\\|,.<>/?]', password):
                errors.append("Password must contain at least one special character.")
            if errors:
                raise ValidationError(errors)
        return password

    def clean(self):
        cleaned = super().clean()
        pw = cleaned.get('password')
        cpw = cleaned.get('confirm_password')
        if pw and cpw and pw != cpw:
            raise ValidationError({"confirm_password": "Passwords do not match."})
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        # set_password will hash the password
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
        return user


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product

        exclude = ['seller',"product_type"]  # seller auto set

class QuantityPriceForm(forms.ModelForm):
    class Meta:
        model = ProductQuantityPrice
        fields = ['quantity', 'price', 'stock']

class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class ProductImageForm(forms.ModelForm):
    image = forms.FileField(
        widget=MultipleFileInput(attrs={'multiple': True}),
        required=False
    )

    class Meta:
        model = ProductImage
        fields = ['image']

class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ['rating', 'comment']
        widgets = {
            'rating': forms.Select(choices=[(i, f"{i} Star") for i in range(1, 6)]),
            'comment': forms.Textarea(attrs={'rows': 3}),
        }
class CheckoutForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ['full_name', 'phone', 'address', 'city', 'postal_code', 'payment_method']
        widgets = {
            'payment_method': forms.RadioSelect(choices=[
                ('COD', 'Cash on Delivery'),
                ('ONLINE', 'Online Payment (Currently Disabled)'),
            ])
        }

