from django import template

register = template.Library()

@register.filter
def get_range(value):
    """
    Returns a range object for use in templates to generate numbered loops
    Usage: {% for i in placeholder_count|get_range %}...{% endfor %}
    """
    return range(value)