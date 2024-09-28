from pathlib import Path

class FlatMappingStrategy():
    """Defines a basic flat mapping strategy. Paths will be stripped and file names kept but all images will simply be stored in the root of the local directory"""
    def __init__(self):
        pass
    
    def map_remote_to_local(self, remote_path):
        path = Path(remote_path)

        # Replace the extension with '.bin'
        return path.with_suffix('.bin').name