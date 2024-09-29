from pathlib import Path

class FlatMappingStrategy():
    """ Defines a basic flat mapping strategy. Remote paths will be flattened to a filename structured as <mem card dir>_<mem card name>.bin """
    def __init__(self):
        pass
    
    def map_remote_to_local(self, remote_path):
        # Flatten to <mem card dir>_<mem card name>.bin
        return f'{remote_path.parts[len(remote_path.parts)-2]}_{remote_path.stem}.bin'