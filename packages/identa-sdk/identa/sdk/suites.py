import toml
from typing import List, Dict, Any

def load_suite(path: str) -> List[Dict[str, Any]]:
    """Loads a test suite from a TOML file."""
    data = toml.load(path)
    
    # Expecting a format like:
    # [[tests]]
    # id = "test1"
    # input = "hello"
    # expected = "hi"
    
    if "tests" in data:
        return data["tests"]
    
    # If it's a list at the top level (rare in TOML) or another format
    if isinstance(data, list):
        return data
        
    return [data] # Fallback for single test defined at top level
