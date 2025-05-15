from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Item, Sale, Category, Supplier, StockTransaction

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'role']  # Add fields according to your User model

class ItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = Item
        fields = '__all__'
        
class SaleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sale
        fields = ['id', 'product', 'quantity', 'total_price', 'date']  # Adjust fields as needed

class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = '__all__' 
        
        
class StockTransactionSerializer(serializers.ModelSerializer):
    item = serializers.CharField(source='item.name')
    value = serializers.FloatField()

    class Meta:
        model = StockTransaction
        fields = ['date', 'item', 'transaction_type', 'quantity', 'unit', 'value', 'remarks']