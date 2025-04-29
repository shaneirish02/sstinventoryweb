# core/templatetags/custom_filters.py
from django import template
from datetime import datetime, date

register = template.Library()

@register.filter
def format_datetime_safe(value):
    if isinstance(value, datetime):
        return value.strftime('%Y-%m-%d %H:%M')
    elif isinstance(value, date):
        return value.strftime('%Y-%m-%d')
    return ''
@register.filter
def multiply(value, arg):
    """Multiplies value by the argument."""
    try:
        return value * arg
    except (TypeError, ValueError):
        return 0
    
@register.filter
def subtract(value, arg):
    """Subtracts the argument from the value."""
    try:
        return value - arg
    except (TypeError, ValueError):
        return 0