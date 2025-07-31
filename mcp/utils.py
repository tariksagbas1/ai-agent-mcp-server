import re
from typing import Any, Dict, Type
from pydantic import create_model, BaseModel, Field

def split_by_capitals(s):
    # Use regular expression to split the string based on capital letters
    words = re.findall(r'[A-Z][a-z]+|ID|[A-Z](?=[A-Z][a-z])', s)
    return ' '.join(words)

def rename_columns(df):
    # Rename each column in the DataFrame by splitting on capital letters
    new_columns = {col: split_by_capitals(col) for col in df.columns}
    df.rename(columns=new_columns, inplace=True)

def convert_to_builtin_type(type_str):
    # Define regex patterns for each built-in type

    if type_str == 'text':
        type_str = 'string'

    elif type_str == 'datetime':
        type_str = 'string'

    elif type_str == 'real':
        type_str = 'float'

    type_patterns = {
        int: re.compile(r'^(int(eger)?(64)?)$', re.IGNORECASE),
        float: re.compile(r'^(float|decimal)$', re.IGNORECASE),
        str: re.compile(r'^(str(ing)?)$', re.IGNORECASE)
    }
    
    # Match type_str against each pattern
    for builtin_type, pattern in type_patterns.items():
        if pattern.match(type_str):
            return builtin_type
    
    # Return None if no match is found
    return None

def remove_spaces(s: str) -> str:
    """Remove spaces from string."""
    return s.replace(' ', '')