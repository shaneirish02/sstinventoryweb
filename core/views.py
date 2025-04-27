from django.shortcuts import render, get_object_or_404, redirect
from .models import Item, Category, Sale, UserProfile, Supplier, CartItem, StockTransaction
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login
from django.db.models import Sum
from django.contrib.auth.models import User
from .forms import UserForm, ItemForm
from django.http import JsonResponse
import datetime
import json
from django.core.exceptions import ValidationError
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import logout
from django.views.decorators.csrf import csrf_exempt
from .forms import SupplierForm
from django.template.loader import render_to_string
from django.db.models import Q
from django.utils import timezone

def logout_view(request):
    logout(request)
    return redirect('user_login')

@csrf_exempt
def checkout(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)

            payment_received = float(data.get('payment_received', 0))
            cart = request.session.get('cart', [])

            if not cart:
                return JsonResponse({'success': False, 'message': 'Cart is empty.'})

            total_amount = sum(item['price'] * item['quantity'] for item in cart)

            if payment_received < total_amount:
                return JsonResponse({'success': False, 'message': 'Insufficient funds.'})

            # Create Sale record
            sale = Sale.objects.create(
                total_price=total_amount,
                date=timezone.now().date()
            )

            print("Cart in session:", cart)

            for cart_item in cart:
                print("Cart item:", cart_item)
                item_id = cart_item.get('id')
                if not item_id:
                    return JsonResponse({'success': False, 'message': 'Missing item ID in cart.', 'cart_item': cart_item})

            try:
                item = Item.objects.get(id=item_id)
            except Item.DoesNotExist:
                return JsonResponse({'success': False, 'message': f'Item with ID {item_id} not found.'})

            sale.items.create(
                item=item,
                quantity=cart_item['quantity'],
                price=item.price,
                subtotal=item.price * cart_item['quantity']
            )

            StockTransaction.objects.create(
                item=item,
                transaction_type='OUT',
                quantity=cart_item['quantity'],
                unit=item.unit,
                date=timezone.now(),
                remarks='Checked out via POS'
            )

            # Deduct stock
            item.quantity -= cart_item['quantity']
            item.save()


            # Clear cart after successful checkout
            request.session['cart'] = []
            request.session.modified = True

            change = payment_received - total_amount

            return JsonResponse({
                'success': True,
                'message': 'Transaction successful',
                'change': change,
                'total_amount': total_amount,
                'order_summary': f"Sale of {len(cart)} items for ${total_amount:.2f}"
            })

        except Exception as e:
            return JsonResponse({'success': False, 'message': f'Error: {str(e)}'})

    return JsonResponse({'success': False, 'message': 'Invalid request method.'})

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

    total_sales = sum(sale.total_price for sale in sales_data)


    return render(request, 'sales_report.html', {
        'selected_period': period.capitalize(),
        'sales_data': sales_data,
        'total_sales': total_sales,
        'today': today.strftime('%Y-%m-%d'),
    })

@login_required
def add_item(request):
    if request.method == 'POST':
        form = ItemForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()  
            return redirect('inventory_management')  
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


def item_list(request):
    query = request.GET.get('q', '')
    items = Item.objects.all()

    if query:
        items = items.filter(
            Q(name__icontains=query) |
            Q(description__icontains=query) |
            Q(category__name__icontains=query)
        )

    context = {
        'items': items,
    }
    return render(request, 'inventory_management.html', context)



def item_autocomplete(request):
    query = request.GET.get('term', '')
    items = Item.objects.filter(name__icontains=query).values('name', 'id')
    return JsonResponse(list(items), safe=False)

@csrf_exempt
def add_to_cart(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            item_name = data.get('item_name')
            quantity = int(data.get('quantity', 1))

            # Get item from database
            try:
                item = Item.objects.get(name__iexact=item_name)
            except Item.DoesNotExist:
                return JsonResponse({'success': False, 'message': 'Item not found.'})

            # Initialize cart in session if not already
            cart = request.session.get('cart', [])

            # Check if item already exists in the session cart
            for cart_item in cart:
                if cart_item['id'] == item.id:
                    cart_item['quantity'] += quantity
                    break
            else:
                # Add new item
                cart.append({
                    'id': item.id,
                    'name': item.name,
                    'price': float(item.price),  # Make sure it's JSON serializable
                    'quantity': quantity
                })

            # Save updated cart in session
            request.session['cart'] = cart
            request.session.modified = True

            return JsonResponse({'success': True, 'cart': cart})

        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})

    return JsonResponse({'success': False, 'message': 'Invalid request method'})

@csrf_exempt
def remove_from_cart(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            item_id = data.get('item_id')

            cart = request.session.get('cart', [])
            cart = [item for item in cart if item['id'] != item_id]

            request.session['cart'] = cart
            request.session.modified = True

            return JsonResponse({'success': True, 'cart': cart})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
    return JsonResponse({'success': False, 'message': 'Invalid request method'})



def live_search_items(request):
    query = request.GET.get('q', '')
    items = Item.objects.filter(name__icontains=query)
    html = render_to_string('item_rows.html', {'items': items})
    return JsonResponse({'html': html})


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


def supplier_list(request):
    suppliers = Supplier.objects.all()
    return render(request, 'supplier_list.html', {'suppliers': suppliers})

def supplier_create(request):
    if request.method == 'POST':
        form = SupplierForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('supplier_list')  # Redirect to the supplier list after saving
    else:
        form = SupplierForm()  # Create a blank form for GET requests

    return render(request, 'supplier_form.html', {'form': form, 'form_title': 'Add Supplier'})

def supplier_update(request, pk):
    supplier = get_object_or_404(Supplier, pk=pk)
    form = SupplierForm(request.POST or None, instance=supplier)
    if form.is_valid():
        form.save()
        return redirect('supplier_list')
    return render(request, 'supplier_form.html', {'form': form, 'form_title': 'Edit Supplier'})

def supplier_detail(request, pk):
    supplier = get_object_or_404(Supplier, pk=pk)
    return render(request, 'supplier_detail.html', {'supplier': supplier})

def supplier_confirm_delete(request, pk):
    supplier = get_object_or_404(Supplier, pk=pk)
    if request.method == 'POST':
        supplier.delete()
        return redirect('supplier_list')
    return render(request, 'supplier_confirm_delete.html', {'supplier': supplier})

def stock_card(request, item_id):
    item = get_object_or_404(Item, id=item_id)
    transactions = item.stock_transactions.all().order_by('-date')  # using the correct related_name
    return render(request, 'stock_card.html', {'item': item, 'transactions': transactions})


def search_items(request):
    query = request.GET.get('q', '')
    items = Item.objects.filter(name__icontains=query)[:10]
    results = [{'name': item.name, 'price': float(item.price), 'description': item.description} for item in items]
    return JsonResponse(results, safe=False)