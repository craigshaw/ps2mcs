import re

from pathlib import Path

MCPD2_PS2_ROOT = "PS2"
MCPD2_PS1_ROOT = "PS1"

class InvalidTargetFormatError(Exception):
    """ ps2mcs requires targets for sync to follow this convention <GameId>-<Channel>.<mc2 or mcd> """
    def __init__(self, message='Unsupported target file format encountered. ps2mcs '
    'requires targets for sync to follow this convention `<GameId>-<Channel>.<mc2 or mcd>`'):
        super().__init__(message)

class FlatMappingStrategy():
    """
    A flat mapping strategy for memory card filenames between local storage and the MCP2.

    - **Remote path**: Relative path from the MCP2 FTP root to the target file.  
    - **Local path**: Absolute path on the local filesystem to the target file.  

    Local filenames are mapped as:  
    - PS2: `<GameId>-<Channel>.bin`  
    - PS1: `<GameId>-<Channel>.mcd`  
    """

    def __init__(self):
        pass

    def map_to_local(self, filename, local_root):
        filepath = Path(filename)
        if filepath.suffix.lower() == '.mc2':
            filepath = filepath.with_suffix('.bin')
        return Path(local_root) / filepath.name

    def map_to_remote(self, filename):
        filepath = Path(filename)
        patterns = {
            ".mc2": MCPD2_PS2_ROOT,
            ".mcd": MCPD2_PS1_ROOT,
        }

        for suffix, root in patterns.items():
            match = re.match(rf"([^/]+)-([1-8])\{suffix}$", filepath.name, re.IGNORECASE)
            if match:
                gameid = match.group(1)
                return Path(root) / gameid / filepath.name

        raise InvalidTargetFormatError()
