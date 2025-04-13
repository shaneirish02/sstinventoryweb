from django import forms
from .models import Item
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

ACCOUNT_TYPES = (
    ('Admin', 'Admin'),
    ('Cashier', 'Cashier'),
)

class UserForm(UserCreationForm):
    account_type = forms.ChoiceField(choices=ACCOUNT_TYPES)

    class Meta:
        model = User
        fields = ['username', 'password1', 'password2', 'account_type']

class ItemForm(forms.ModelForm):
    class Meta:
        model = Item
        fields = ['name', 'category', 'description', 'quantity', 'price']