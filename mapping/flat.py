import re
from pathlib import Path

MCPD2_PS2_ROOT = "PS2"

class InvalidTargetFormatError(Exception):
    """ ps2mcs requires targets for sync to follow this convention <CardName>/<CardName>-<Channel>.mc2 """
    def __init__(self, message='Unsupported target file format encountered. ps2mcs requires targets for sync to follow this convention <CardName>/<CardName>-<Channel>.mc2'):
        super().__init__(message)

class FlatMappingStrategy():
    """ Defines a basic flat mapping strategy. Remote paths will be flattened to a filename structured as <mem card dir>_<mem card name>.bin """
    def __init__(self):
        pass
    
    def map_to_local(self, filename, local_root):
        filepath = Path(filename)
        # Flatten to <mem card dir>_<mem card name>.bin
        return f'{local_root}/{filepath.stem}.bin'

    def map_to_remote(self, filename):
        pattern = r"([^/]+)-([1-8])\.mc2$"

        match = re.match(pattern, str(filename))

        if match:
            gameid = match.group(1)  # The gameid part (SLUS-21274)

            return f'{MCPD2_PS2_ROOT}/{gameid}/{filename}'
        else:
            raise InvalidTargetFormatError()
