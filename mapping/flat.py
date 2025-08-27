import re
from pathlib import Path

MCPD2_PS2_ROOT = "PS2"
MCPD2_PS1_ROOT = "PS1"

class InvalidTargetFormatError(Exception):
    """ ps2mcs requires targets for sync to follow this convention <CardName>/<CardName>-<Channel>.<mc2 or mcd> """
    def __init__(self, message='Unsupported target file format encountered. ps2mcs requires targets for sync to follow this convention <CardName>/<CardName>-<Channel>.<mc2 or mcd>'):
        super().__init__(message)

class FlatMappingStrategy():
    """ Defines a basic flat mapping strategy. Remote paths will be flattened to a filename structured as <mem card dir>_<mem card name>.bin """
    def __init__(self):
        pass
    
    def map_to_local(self, filename, local_root):
        filepath = Path(filename)
        ps1pattern = r"([^/]+)-([1-8])\.mcd$"
        ps1match = re.match(ps1pattern, str(filename))

        if ps1match:
        # Flatten to <mem card dir>_<mem card name>.mcd
            return f'{local_root}/{filepath.stem}.mcd'
        else:
        # Flatten to <mem card dir>_<mem card name>.bin
            return f'{local_root}/{filepath.stem}.bin'

    def map_to_remote(self, filename):
        ps2pattern = r"([^/]+)-([1-8])\.mc2$"
        ps2match = re.match(ps2pattern, str(filename))

        ps1pattern = r"([^/]+)-([1-8])\.mcd$"
        ps1match = re.match(ps1pattern, str(filename))

        if ps2match:
            gameid = ps2match.group(1)  # The gameid part (SLUS-21274)

            return f'{MCPD2_PS2_ROOT}/{gameid}/{filename}'
        elif ps1match:
            gameid = ps1match.group(1)  # The gameid part (SLUS-21274)

            return f'{MCPD2_PS1_ROOT}/{gameid}/{filename}'
        else:
            raise InvalidTargetFormatError()
