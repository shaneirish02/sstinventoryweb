from django import forms
from .models import Item
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django import forms
from .models import Supplier

ACCOUNT_TYPES = (
    ('admin', 'Admin'),
    ('cashier', 'Cashier'),
)


class UserForm(UserCreationForm):
    account_type = forms.ChoiceField(choices=ACCOUNT_TYPES)

    class Meta:
        model = User
        fields = ['username', 'password1', 'password2', 'account_type']

class ItemForm(forms.ModelForm):
    class Meta:
        model = Item
        fields = ['name', 'category', 'description', 'quantity', 'price', 'supplier', 'unit', 'image']



class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = ['name', 'contact_person', 'phone', 'email', 'address', 'company']
