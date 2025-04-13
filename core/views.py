from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login
from .models import Item, Category, Sale, UserProfile
from django.db.models import Sum
from django.contrib.auth.models import User
from .forms import UserForm, ItemForm
from django.http import JsonResponse
import datetime
import json
from .models import Item, CartItem
from django.core.exceptions import ValidationError
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import logout
from django.views.decorators.csrf import csrf_exempt


def logout_view(request):
    logout(request)
    return redirect('user_login')

def checkout(request):
    if request.method == "POST":
        # Get payment data and cart from the request
        data = json.loads(request.body)
        payment_received = float(data['payment_received'])
        cart = data['cart']
        total_amount = sum(item['price'] * item['quantity'] for item in cart)

        if payment_received < total_amount:
            return JsonResponse({'error': 'Insufficient funds'})

        # Record sale in the database
        sale = Sale.objects.create(
            total_price=total_amount,
            date=datetime.today().date()
        )

        for cart_item in cart:
            item = Item.objects.get(name=cart_item['item'])
            sale.items.create(item=item, quantity=cart_item['quantity'], price=item.price, subtotal=cart_item['price'] * cart_item['quantity'])

            # Update item quantity in the inventory
            item.quantity -= cart_item['quantity']
            item.save()

        # Clear the cart
        request.session['cart'] = []
        request.session.modified = True

        change = payment_received - total_amount
        return JsonResponse({'message': 'Transaction successful', 'change': change, 'total_amount': total_amount, 'orderSummary': f"Sale of {len(cart)} items for ${total_amount}"})
    return redirect('cashier_pos')

def user_login(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']

     
        user = authenticate(username=username, password=password)

        if user is not None:
            login(request, user)  

           
            if hasattr(user, 'userprofile'):
               
                print(f"Account type for {user.username}: {user.userprofile.account_type}") 
                
               
                if user.userprofile.account_type == 'Admin':
                    return redirect('admin_dashboard')  
                else:
                    return redirect('cashier_pos') 
            else:
               
                UserProfile.objects.create(user=user, account_type='Cashier')
                return redirect('cashier_pos')  

        else:
           
            return render(request, 'login.html', {'error': 'Invalid credentials'})

    return render(request, 'login.html')  

def homepage(request):
    return redirect('user_login')

@login_required
def inventory_management(request):
   
    items = Item.objects.all()
    return render(request, 'inventory_management.html', {'items': items})

@login_required
def admin_dashboard(request):
    # Query the sales data, ensuring the correct field name is used
    sales_data = Sale.objects.all().order_by('total_price')  # Corrected ordering
    return render(request, 'admin_dashboard.html', {'sales_data': sales_data})

@login_required
def inventory_view(request):
    items = Item.objects.all()
    return render(request, 'inventory_view.html', {'items': items})

@login_required
def sales_report(request):
    # Get the period query parameter (e.g., 'today', 'week', etc.)
    period = request.GET.get('period', 'today')
    
    today = datetime.date.today()

    if period == 'today':
        sales_data = Sale.objects.filter(date=today)
    elif period == 'week':
        sales_data = Sale.objects.filter(date__gte=today - datetime.timedelta(days=7))
    elif period == 'month':
        sales_data = Sale.objects.filter(date__month=today.month)
    elif period == 'year':
        sales_data = Sale.objects.filter(date__year=today.year)

    total_sales = sum(sale.total for sale in sales_data)

    return render(request, 'sales_report.html', {
        'selected_period': period.capitalize(),
        'sales_data': sales_data,
        'total_sales': total_sales,
        'today': today.strftime('%Y-%m-%d'),
    })

@login_required
def add_item(request):
    if request.method == 'POST':
        form = ItemForm(request.POST)
        if form.is_valid():
            form.save()  # Save the item to the database
            return redirect('inventory_management')  # Redirect after successful form submission
    else:
        form = ItemForm()

    return render(request, 'add_item.html', {'form': form})

def cashier_pos(request):
    return render(request, 'cashier_pos.html')

def category_management(request):
    if request.method == 'POST' and 'category_name' in request.POST and 'edit_id' not in request.POST:
        category_name = request.POST.get('category_name')
        if category_name:
            Category.objects.create(name=category_name)
        return redirect('category_management')

    if request.method == 'POST' and 'edit_id' in request.POST:
        category_id = request.POST.get('edit_id')
        category_name = request.POST.get('category_name')
        if category_name:
            category = get_object_or_404(Category, id=category_id)
            category.name = category_name
            category.save()
        return redirect('category_management')

    if request.method == 'GET' and 'delete_id' in request.GET:
        category_id = request.GET.get('delete_id')
        category = get_object_or_404(Category, id=category_id)
        category.delete()
        return redirect('category_management')

    categories = Category.objects.all()
    return render(request, 'category_management.html', {'categories': categories})

@login_required
def user_management(request):
    if request.method == 'POST':
        form = UserForm(request.POST)
        if form.is_valid():
            user = form.save()
            account_type = form.cleaned_data['account_type']
            UserProfile.objects.create(user=user, account_type=account_type)
            return redirect('user_management')
    else:
        form = UserForm()

    users = User.objects.all().select_related('userprofile')  # so we can access user.userprofile.account_type
    return render(request, 'user_management.html', {'form': form, 'users': users})

def update_item(request, item_id):
    item = get_object_or_404(Item, pk=item_id)
    if request.method == 'POST':
        form = ItemForm(request.POST, instance=item)
        if form.is_valid():
            form.save()
            return redirect('inventory_management')
    else:
        form = ItemForm(instance=item)
    
    return render(request, 'update_item.html', {'form': form, 'item': item})

def delete_item(request, id):
    item = get_object_or_404(Item, id=id)
    item.delete()
    return redirect('inventory_management')

def item_autocomplete(request):
    query = request.GET.get('term', '')
    items = Item.objects.filter(name__icontains=query).values('name', 'id')
    return JsonResponse(list(items), safe=False)

@csrf_exempt
def add_to_cart(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        item_name = data.get('item_name')
        quantity = int(data.get('quantity', 1))

        try:
            # Get the item from the database
            item = Item.objects.get(name=item_name)
        except Item.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Item not found'})

        # Ensure the quantity does not exceed stock
        if quantity > item.quantity:
            return JsonResponse({'success': False, 'message': f'Not enough stock for {item_name}. Available quantity: {item.quantity}'})

        subtotal = float(item.price) * quantity
        cart_item = {
            'id': item.id,
            'name': item.name,
            'quantity': quantity,
            'price': float(item.price),
            'subtotal': subtotal
        }

        # Get the current cart from the session
        cart = request.session.get('cart', [])

        # Check if the item is already in the cart
        item_in_cart = False
        for cart_entry in cart:
            if cart_entry['id'] == cart_item['id']:
                cart_entry['quantity'] += quantity  # Increase the quantity
                cart_entry['subtotal'] = cart_entry['quantity'] * cart_entry['price']  # Recalculate the subtotal
                item_in_cart = True
                break

        # If the item isn't already in the cart, add it
        if not item_in_cart:
            cart.append(cart_item)

        # Save the updated cart to session
        request.session['cart'] = cart
        request.session.modified = True

        return JsonResponse({'success': True, 'cart': cart})

    return JsonResponse({'success': False, 'message': 'Invalid request method'})


def checkout(request):
    if request.method == "POST":
        payment_received = float(request.POST.get('payment_received'))
        cart = request.session.get('cart', [])
        total_amount = sum(item['subtotal'] for item in cart)

        if payment_received < total_amount:
            return JsonResponse({'error': 'Insufficient funds'})

        for cart_item in cart:
            item = Item.objects.get(name=cart_item['item'])
            Sale.objects.create(
                item=item,
                quantity=cart_item['quantity'],
                total_price=cart_item['subtotal']
            )

        request.session['cart'] = []
        request.session.modified = True

        change = payment_received - total_amount
        return JsonResponse({'message': 'Transaction successful', 'change': change, 'total_amount': total_amount})

    return redirect('cashier_pos')

def admin_dashboard(request):
    sales = Sale.objects.all().order_by('-date')  # Fetch all sales
    total_sales = sum(sale.total_price for sale in sales)
    return render(request, 'admin_dashboard.html', {'sales': sales, 'total_sales': total_sales})

def search_item(request, item_name):
    if request.method == 'GET':
        items = Item.objects.filter(name__icontains=item_name)[:10]  # limit for performance
        data = []
        for item in items:
            data.append({
                'id': item.id,
                'name': item.name,
                'price': float(item.price),
                'quantity': item.quantity
            })
        return JsonResponse({'items': data})
    
@csrf_exempt  # Exempting CSRF for testing (ensure to use CSRF properly in production)
def update_inventory(request, item_id):
    if request.method == 'POST':
        try:
            # Assuming you've already imported your models
            item = Item.objects.get(id=item_id)
            data = json.loads(request.body)
            quantity_sold = data['quantity']

            # Update stock
            if item.stock >= quantity_sold:
                item.stock -= quantity_sold
                item.save()

                return JsonResponse({'success': True})
            else:
                return JsonResponse({'success': False, 'message': 'Not enough stock.'})
        except Item.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Item not found.'})
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'message': 'Invalid JSON in request.'})
    return JsonResponse({'success': False, 'message': 'Invalid request method.'})

def record_sale(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            sale = Sale.objects.create(
                total_amount=data['totalAmount'],
                received_money=data['receivedMoney'],
                change=data['change']
            )

            for item in data['items']:
                SaleItem.objects.create(
                    sale=sale,
                    item=Item.objects.get(id=item['id']),
                    quantity=item['quantity'],
                    price=item['price']
                )

            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
    return JsonResponse({'success': False, 'message': 'Invalid request method.'})



def checkout_view(request):
    # Example: Fetching the cart from the session (adjust based on your logic)
    cart = request.session.get('cart', [])
    
    # Calculate total and other necessary info
    total_amount = sum(item['price'] * item['quantity'] for item in cart)

    return render(request, 'checkout.html', {'cart': cart, 'total_amount': total_amount})

@csrf_exempt
def remove_from_cart(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            item_id = data.get('item_id')

            # Get the cart from session
            cart = request.session.get('cart', [])
            
            # Remove the item completely from the cart
            updated_cart = [item for item in cart if item['id'] != item_id]

            # Save the updated cart in session
            request.session['cart'] = updated_cart
            request.session.modified = True

            return JsonResponse({'success': True, 'cart': updated_cart})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})

    return JsonResponse({'success': False, 'message': 'Invalid request method'})

@csrf_exempt  # Disable CSRF for testing (use CSRF protection in production)
def clear_cart(request):
    if request.method == 'POST':
        try:
            # Clear the cart by resetting the session cart to an empty list
            request.session['cart'] = []  
            request.session.modified = True  # Mark the session as modified

            return JsonResponse({'success': True, 'message': 'Cart has been cleared successfully.'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})

    return JsonResponse({'success': False, 'message': 'Invalid request method'})

@csrf_exempt  # Disable CSRF for testing (use CSRF protection in production)
def clear_cart(request):
    if request.method == 'POST':
        try:
            # Clear the cart by resetting the session cart to an empty list
            request.session['cart'] = []  
            request.session.modified = True  # Mark the session as modified

            return JsonResponse({'success': True, 'message': 'Cart has been cleared successfully.'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})

    return JsonResponse({'success': False, 'message': 'Invalid request method'})