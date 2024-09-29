from pathlib import Path

class FlatMappingStrategy():
    """Defines a basic flat mapping strategy. Paths will be stripped and file names kept but all images will simply be stored in the root of the local directory"""
    def __init__(self):
        pass
    
    def map_remote_to_local(self, remote_path):
        # Flatten to <mem card dir>_<mem_car_name>.bin
        return f'{remote_path.parts[len(remote_path.parts)-2]}_{remote_path.stem}.bin'