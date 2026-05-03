from pydantic import BaseModel

class Command(BaseModel):
    """Base class for all application commands."""
    pass

class Query(BaseModel):
    """Base class for all application queries."""
    pass
