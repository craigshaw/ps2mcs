from pathlib import Path

class SyncTarget():
    def __init__(self, filename, sync_root, ms) -> None:
        self.filename = filename
        self.remote_path = Path(ms.map_to_remote(filename))
        self.local_path = Path(ms.map_to_local(filename, sync_root)).resolve()
        self._assert_local_path()

    def _assert_local_path(self):
        # Check path to file locally exists, create if not
        self.local_path.parent.mkdir(parents=True, exist_ok=True)