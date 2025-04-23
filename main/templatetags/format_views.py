from django import template

register = template.Library()

@register.filter
def format_views(value):
    try:
        value = int(value)
        if value >= 1000000:
            return f"{value // 1000000}M"
        elif value >= 1000:
            return f"{value // 1000}K"
        return str(value)
    except (ValueError, TypeError):
        return "0"