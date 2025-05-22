from django.db import models
from django.contrib.auth.models import User
from django import forms
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone

def some_function():
    from .models import Item



# Model for UserProfile
class UserProfile(models.Model):
    ACCOUNT_TYPES = (
        ('Admin', 'admin'),
        ('Cashier', 'cashier'),
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    account_type = models.CharField(max_length=10, choices=ACCOUNT_TYPES)

    def __str__(self):
        return f"{self.user.username} ({self.account_type})"



# Model for Category
class Category(models.Model):
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name


class Supplier(models.Model):
    name = models.CharField(max_length=255)
    contact_person = models.CharField(max_length=255, blank=True, null=True)
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    company = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

from django.db import models

class Item(models.Model):
    # Define the choices for the 'unit' field
    UNIT_CHOICES = [
        ('each', 'Each'),
        ('pack', 'Pack'),
        ('case', 'Case'),
        ('pieces', 'Pieces'),
        ('meter', 'Meter'),
        ('liter', 'Liter'),
        ('kilograms', 'Kilograms'),
        ('pound', 'Pound'),
        ('gallons', 'Gallons'),
    ]

    name = models.CharField(max_length=255)
    category = models.ForeignKey('Category', on_delete=models.CASCADE)
    description = models.TextField()
    quantity = models.IntegerField(default=0)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    supplier = models.ForeignKey('Supplier', on_delete=models.SET_DEFAULT, default=1)
    unit = models.CharField(max_length=100, choices=UNIT_CHOICES)  # Unit field with choices
    image = models.ImageField(upload_to='items_images/', blank=True, null=True)
    date_added = models.DateTimeField(default=timezone.now)
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


# Model for Sale
class Sale(models.Model):
    date = models.DateField()
    timestamp = models.DateTimeField(auto_now_add=True)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"Sale on {self.date} for ₱{self.total_price}"

    @property
    def subtotal(self):
        # Sum all related sale items' subtotals
        return sum(item.subtotal for item in self.items.all())
    
    
# Model for SaleItem
class SaleItem(models.Model):
    sale = models.ForeignKey('core.Sale', on_delete=models.CASCADE, related_name='items')
    item = models.ForeignKey('Item', on_delete=models.SET_NULL, null=True)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)

def save(self, *args, **kwargs):
    # Calculate the subtotal
    self.subtotal = self.quantity * self.price
    super(SaleItem, self).save(*args, **kwargs)

    # Now that the SaleItem is saved, update the parent sale's total_price
    if self.sale:
        total = sum(item.subtotal for item in self.sale.items.all())
        self.sale.total_price = total
        self.sale.save(update_fields=['total_price'])

    


def cashier_pos(request):
    items = Item.objects.all()
    return render(request, 'cashier_pos.html', {'items': items})


def add_to_cart(request):
    import json

    if request.method == 'POST':
        data = json.loads(request.body)
        item_name = data.get('item_name')
        quantity = int(data.get('quantity', 1))

        try:
            item = Item.objects.get(name=item_name)
        except Item.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Item not found'})

        subtotal = float(item.price) * quantity
        cart_item = {
            'name': item.name,
            'quantity': quantity,
            'price': float(item.price),
            'subtotal': subtotal
        }

        if 'cart' not in request.session:
            request.session['cart'] = []

        request.session['cart'].append(cart_item)
        request.session.modified = True

        return JsonResponse({'success': True, 'cart': request.session['cart']})
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})

def checkout(request):
    if request.method == "POST":
        payment_received = float(request.POST.get('payment_received'))
        cart = request.session.get('cart', [])
        total_amount = sum(item['subtotal'] for item in cart)

        if payment_received < total_amount:
            return JsonResponse({'error': 'Insufficient funds'})

        # Record sale in the database
        for cart_item in cart:
            item = Item.objects.get(name=cart_item['item'])
            Sale.objects.create(
                item=item,
                quantity=cart_item['quantity'],
                total_price=cart_item['subtotal']
            )

        # Clear cart
        request.session['cart'] = []
        request.session.modified = True

        change = payment_received - total_amount
        return JsonResponse({'message': 'Transaction successful', 'change': change, 'total_amount': total_amount})
    return redirect('cashier_pos')

def sales_report(request):
    period = request.GET.get('period', 'today')

    if period == 'today':
        start_date = datetime.today().date()
        end_date = start_date
    elif period == 'week':
        start_date = datetime.today() - timedelta(days=7)
        end_date = datetime.today()
    elif period == 'month':
        start_date = datetime.today() - timedelta(days=30)
        end_date = datetime.today()
    elif period == 'year':
        start_date = datetime.today() - timedelta(days=365)
        end_date = datetime.today()

    sales_data = Sale.objects.filter(date__range=[start_date, end_date])
    total_sales = sales_data.aggregate(Sum('total_price'))['total_price__sum'] or 0.00

    return render(request, 'sales_report.html', {
        'sales_data': sales_data,
        'total_sales': total_sales,
        'selected_period': period
    })
    
    
    
class CartItem(models.Model):
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    quantity = models.IntegerField(default=1)

    def __str__(self):
        return f'{self.item.name} (x{self.quantity})'
    
def search_item(request, name):
    try:
        items = Item.objects.filter(name__icontains=name)
        item_list = [{
            'id': item.id,
            'name': item.name,
            'price': float(item.price),
            'quantity': item.quantity
        } for item in items]
        return JsonResponse({'items': item_list})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def remove_from_cart(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            item_id = data.get('item_id')
            # Assuming cart is stored in session
            cart = request.session.get('cart', [])
            cart = [item for item in cart if item['id'] != item_id]  # Remove the item with the given ID
            request.session['cart'] = cart  # Save the updated cart back to the session
            return JsonResponse({'success': True})
        except Exception as e:
            print("Error while removing item:", e)
            return JsonResponse({'success': False, 'message': 'Error removing item from cart'})


    

class StockTransaction(models.Model):
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='stock_transactions')
    transaction_type = models.CharField(max_length=10, choices=[('IN', 'In'), ('OUT', 'Out')])
    quantity = models.IntegerField()
    unit = models.CharField(max_length=20, default="pcs")
    date = models.DateTimeField(auto_now_add=True)
    remarks = models.TextField(blank=True, null=True)

    @property
    def value(self):
        return self.quantity * self.item.price  # Assuming `price` is a field in the Item model

