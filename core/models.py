from django.db import models
from django.contrib.auth.models import User
from django import forms
from django.http import JsonResponse
from django.shortcuts import render


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

class Item(models.Model):
    name = models.CharField(max_length=100)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    description = models.TextField(blank=True, null=True)  # ✅ Include this if needed
    quantity = models.IntegerField(default=0)
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return self.name

    
    
# Model for Sale
class Sale(models.Model):
    date = models.DateField()
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    total_price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"Sale of {self.item.name} on {self.date}"
# Model for SaleItem
class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='items')
    item = models.ForeignKey('Item', on_delete=models.SET_NULL, null=True)  # Use string reference for ForeignKey
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.item.name} x {self.quantity}"


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
