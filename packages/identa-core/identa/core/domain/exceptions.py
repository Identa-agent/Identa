class IdentaDomainError(Exception):
    """Base exception for all domain-related errors in Identa."""
    pass

class WorkspaceNotFoundError(IdentaDomainError):
    """Raised when a requested workspace does not exist."""
    def __init__(self, workspace_id: str):
        super().__init__(f"Workspace '{workspace_id}' not found.")

class RunAlreadyCompletedError(IdentaDomainError):
    """Raised when an operation is attempted on a run that is already finished or failed."""
    def __init__(self, run_id: str):
        super().__init__(f"Run '{run_id}' is already completed and cannot be modified.")

class InvalidMetricError(IdentaDomainError):
    """Raised when a metric configuration or value is invalid."""
    pass

class StorageError(IdentaDomainError):
    """Raised when a persistence operation fails."""
    pass
