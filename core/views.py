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
from django.contrib import messages

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from django.utils.text import slugify
from django.http import HttpResponse
from django.utils.dateparse import parse_date
from datetime import datetime, timedelta

from django.core.exceptions import ValidationError
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import logout
from django.views.decorators.csrf import csrf_exempt
from .forms import SupplierForm
from django.template.loader import render_to_string
from django.db.models import Q
from django.utils import timezone
from xhtml2pdf import pisa
from docx import Document
import io
from django.utils.timezone import now



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
def inventory_management(request):
    items = Item.objects.all()
    categories = Category.objects.all()

    # Filters
    category_id = request.GET.get('category')
    search_query = request.GET.get('q')
    date_filter = request.GET.get('date')

    if category_id:
        items = items.filter(category_id=category_id)

    if search_query:
        items = items.filter(name__icontains=search_query)

    if date_filter:
        try:
            parsed_date = parse_date(date_filter)
            if parsed_date:
                items = items.filter(date_added__date=parsed_date)
        except:
            pass

    context = {
        'items': items,
        'categories': categories,
    }
    return render(request, 'inventory_management.html', context)

@login_required
def bulk_delete_items(request):
    selected_ids = request.POST.getlist('selected_items')
    if selected_ids:
        Item.objects.filter(id__in=selected_ids).delete()
        messages.success(request, f"{len(selected_ids)} items deleted successfully.")
    else:
        messages.warning(request, "No items selected for deletion.")
    return redirect('inventory_management')

@login_required
def sales_report(request):
    period = request.GET.get('period', 'today').lower()  # Ensure the period is in lowercase
    
    today = datetime.now().date()  # Get today's date correctly

    # Filter sales based on the selected period
    if period == 'today':
        sales_data = Sale.objects.filter(date=today)
    elif period == 'week':
        start_of_week = today - timedelta(days=today.weekday())  # Get the start of the current week (Monday)
        sales_data = Sale.objects.filter(date__gte=start_of_week)
    elif period == 'month':
        sales_data = Sale.objects.filter(date__month=today.month, date__year=today.year)
    elif period == 'year':
        sales_data = Sale.objects.filter(date__year=today.year)
    else:
        sales_data = Sale.objects.all()  # Fallback for any unexpected 'period' value
    
    # Calculate the total sales
    total_sales = sum(sale.total_price for sale in sales_data)

    # Render the report page with the selected period, sales data, and total sales
    return render(request, 'sales_report.html', {
        'selected_period': period.capitalize(),  # Capitalize the period for display
        'sales_data': sales_data,
        'total_sales': total_sales,
        'today': today.strftime('%Y-%m-%d'),
    })



def add_item(request):
    if request.method == 'POST':
        form = ItemForm(request.POST, request.FILES)
        if form.is_valid():
            item = form.save(commit=False)

            # Set the quantity directly instead of adding
            quantity_input = int(request.POST.get('quantity', 0))
            item.quantity = quantity_input
            item.save()

            # Record stock transaction (optional)
            StockTransaction.objects.create(
                item=item,
                transaction_type='IN',
                quantity=quantity_input,
                unit=item.unit,
                remarks="Initial stock"
            )

            messages.success(request, f"{item.name} was added with quantity {quantity_input}")
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

            # Check if quantity requested exceeds available stock
            if item.quantity < quantity:
                return JsonResponse({'success': False, 'message': f"Only {item.quantity} items available in stock."})

            # Initialize cart in session if not already
            cart = request.session.get('cart', [])

            # Check if item already exists in the session cart
            for cart_item in cart:
                if cart_item['id'] == item.id:
                    cart_item['quantity'] += quantity
                    break
            else:
                # Add new item with item_id properly set
                cart.append({
                    'id': item.id,  # Ensure 'id' matches the 'item_id' in the database
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


def get_sales_by_period(period):
    today = now().date()
    if period == "today":
        return Sale.objects.filter(date__date=today)
    elif period == "week":
        return Sale.objects.filter(date__date__gte=today - timedelta(days=7))
    elif period == "month":
        return Sale.objects.filter(date__month=today.month, date__year=today.year)
    elif period == "year":
        return Sale.objects.filter(date__year=today.year)
    return Sale.objects.none()

def download_sales_report(request):
    # Get today's date
    today = datetime.now().date()

    # Based on the period selected, filter sales
    period = request.GET.get('period', 'today').lower()

    if period == 'today':
        sales = Sale.objects.filter(date=today)
        period_display = "Today's Sales"
    elif period == 'week':
        start_of_week = today - timedelta(days=today.weekday())
        sales = Sale.objects.filter(date__gte=start_of_week)
        period_display = "This Week's Sales"
    elif period == 'month':
        sales = Sale.objects.filter(date__month=today.month, date__year=today.year)
        period_display = "This Month's Sales"
    elif period == 'year':
        sales = Sale.objects.filter(date__year=today.year)
        period_display = "This Year's Sales"
    else:
        sales = Sale.objects.all()
        period_display = "All Sales"

    # Get the format (PDF or DOCX) from the GET request
    file_format = request.GET.get('format', 'docx')

    # If user requests DOCX (Word document)
    if file_format == 'docx':
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
        response['Content-Disposition'] = f'attachment; filename="{period_display}.docx"'

        # Create a new Document
        doc = Document()

        # Add the title and total sales header
        doc.add_heading(f"{period_display} Report", 0)

        total_sales = 0
        doc.add_paragraph(f"Total Sales: ₱{total_sales:.2f}")

        # Add table headers
        table = doc.add_table(rows=1, cols=5)
        table.style = 'Table Grid'
        hdr_cells = table.rows[0].cells
        hdr_cells[0].text = 'Date'
        hdr_cells[1].text = 'Item Name'
        hdr_cells[2].text = 'Price Per Item'
        hdr_cells[3].text = 'Quantity Sold'
        hdr_cells[4].text = 'Subtotal'

        # Add sale data to the table
        for sale in sales:
            for sale_item in sale.items.all():
                item_name = sale_item.item.name
                item_price = sale_item.price
                item_quantity = sale_item.quantity
                item_subtotal = sale_item.subtotal
                total_sales += item_subtotal

                row_cells = table.add_row().cells
                row_cells[0].text = str(sale.date)
                row_cells[1].text = item_name
                row_cells[2].text = f"₱{item_price:.2f}"
                row_cells[3].text = str(item_quantity)
                row_cells[4].text = f"₱{item_subtotal:.2f}"

        # Add total sales at the end
        doc.add_paragraph(f"\nTotal Sales: ₱{total_sales:.2f}")

        # Save the document to the response
        doc.save(response)

        return response

    # If user requests PDF
    elif file_format == 'pdf':
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{period_display}.pdf"'

        # Create a PDF canvas
        p = canvas.Canvas(response, pagesize=letter)

        # Add title
        p.setFont("Helvetica", 14)
        p.drawString(100, 750, f"{period_display} Report")

        # Add total sales header
        total_sales = 0
        p.setFont("Helvetica", 10)
        p.drawString(100, 730, f"Total Sales: ₱{total_sales:.2f}")

        # Set table headers
        p.setFont("Helvetica-Bold", 10)
        p.drawString(100, 710, "Date")
        p.drawString(200, 710, "Item Name")
        p.drawString(300, 710, "Price Per Item")
        p.drawString(400, 710, "Quantity Sold")
        p.drawString(500, 710, "Subtotal")

        # Add sale data to the table
        y_position = 690
        for sale in sales:
            for sale_item in sale.items.all():
                item_name = sale_item.item.name
                item_price = sale_item.price
                item_quantity = sale_item.quantity
                item_subtotal = sale_item.subtotal
                total_sales += item_subtotal

                p.setFont("Helvetica", 10)
                p.drawString(100, y_position, str(sale.date))
                p.drawString(200, y_position, item_name)
                p.drawString(300, y_position, f"₱{item_price:.2f}")
                p.drawString(400, y_position, str(item_quantity))
                p.drawString(500, y_position, f"₱{item_subtotal:.2f}")

                y_position -= 20

        # Add total sales at the end
        p.setFont("Helvetica-Bold", 10)
        p.drawString(400, y_position - 20, f"Total Sales: ₱{total_sales:.2f}")

        p.showPage()
        p.save()

        return response

    else:
        return HttpResponse("Invalid format selected. Please choose 'docx' or 'pdf'.", status=400)
    
def stock_in(request, item_id):
    # Step 1: Get the item
    item = get_object_or_404(Item, id=item_id)
    
    # Step 2: Get the quantity to add (e.g., from a form)
    if request.method == "POST":
        quantity_to_add = int(request.POST['quantity'])  # You can get this from a form input
        remarks = request.POST.get('remarks', '')  # Optional remarks
        
        # Ensure that quantity is valid
        if quantity_to_add <= 0:
            messages.error(request, "Quantity to add must be greater than 0")
            return redirect('stock_in', item_id=item.id)
        
        # Step 3: Update the item’s stock quantity
        item.update_quantity(quantity_to_add)
        
        # Step 4: Record the stock transaction as "IN"
        StockTransaction.objects.create(
            item=item,
            transaction_type="IN",  # This is a stock-in transaction
            quantity=quantity_to_add,
            remarks=remarks
        )
        
        messages.success(request, f"Successfully added {quantity_to_add} units of {item.name} to the stock.")
        
        return redirect('stock_summary', item_id=item.id)  # Redirect to the stock summary page

    return render(request, 'stock_in.html', {'item': item})