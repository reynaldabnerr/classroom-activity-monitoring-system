import json
from django import template

register = template.Library()


@register.filter
def json_loads(value):
    """Convert JSON string to Python dict"""
    if not value:
        return {}
    try:
        if isinstance(value, str):
            return json.loads(value)
        return value
    except (json.JSONDecodeError, TypeError):
        return {}


@register.filter
def multiply(value, arg):
    """Multiply value by arg"""
    try:
        return float(value) * float(arg)
    except (TypeError, ValueError):
        return 0


@register.filter
def divide(value, arg):
    """Divide value by arg"""
    try:
        return float(value) / float(arg)
    except (TypeError, ValueError, ZeroDivisionError):
        return 0


@register.filter
def subtract(value, arg):
    """Subtract arg from value"""
    try:
        return float(value) - float(arg)
    except (TypeError, ValueError):
        return 0


@register.filter
def dict_sum_values(dict_obj):
    """Sum all values in a dictionary"""
    try:
        if isinstance(dict_obj, dict):
            return sum(dict_obj.values())
        return 0
    except (TypeError, ValueError):
        return 0

