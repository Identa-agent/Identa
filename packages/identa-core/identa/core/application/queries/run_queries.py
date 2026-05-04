from typing import Any, Optional, List
from identa.core.domain.models import Run
from identa.core.ports.storage import StoragePort
from identa.core.application.commands.base import Query

class GetRunQuery(Query):
    run_id: str

class ListRunsQuery(Query):
    workspace_id: str

class RunQueryHandler:
    def __init__(self, storage: StoragePort):
        self.storage = storage

    def handle(self, query: Query) -> Any:
        if isinstance(query, GetRunQuery):
            return self.handle_get_run(query)
        elif isinstance(query, ListRunsQuery):
            return self.handle_list_runs(query)
        raise ValueError(f"Unsupported query: {type(query)}")

    def handle_get_run(self, query: GetRunQuery) -> Optional[Run]:
        return self.storage.get_run(query.run_id)

    def handle_list_runs(self, query: ListRunsQuery) -> List[Run]:
        return self.storage.list_runs(query.workspace_id)
