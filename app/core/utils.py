"""Utility functions for the application."""

import re


def clean_quantity(value: float | int | str) -> str:
    """
    Format a quantity cleanly without unnecessary decimal places.
    
    Examples:
        250.000 -> "250"
        1.5 -> "1.5"
        "250.000 g" -> "250 g"
        "1.000 pcs" -> "1 pcs"
    """
    if isinstance(value, str):
        # Handle string amounts like "250.000 g"
        # Match number with optional decimals followed by optional unit
        match = re.match(r'^([\d.]+)\s*(.*)$', value.strip())
        if match:
            num_str, unit = match.groups()
            try:
                num = float(num_str)
                clean_num = format_number(num)
                return f"{clean_num} {unit}".strip() if unit else clean_num
            except ValueError:
                return value
        return value
    else:
        return format_number(value)


def format_number(num: float | int) -> str:
    """
    Format a number without trailing zeros.
    
    Examples:
        250.0 -> "250"
        250.5 -> "250.5"
        250.123 -> "250.1"
    """
    if num == int(num):
        return str(int(num))
    else:
        # Round to 1 decimal place
        rounded = round(num, 1)
        if rounded == int(rounded):
            return str(int(rounded))
        return str(rounded)
