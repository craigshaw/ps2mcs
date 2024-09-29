#!/usr/bin/env python3

import argparse
import os
import re

from datetime import datetime
from ftplib import FTP
from pathlib import Path

from mapping.flat import FlatMappingStrategy

VERSION = "0.1.0"
MCPD2_PS2_ROOT = "files/PS2"

class MissingCredentialError(Exception):
    """ ps2mcs requires MCP2 FTP creds be provided by environment variables. Specifically, MCP2_USER to provide the username and MCP2_PWD to rpovide the password """
    def __init__(self, message='MCP2 credentials missing. MCP2_USER and MCP2_PWD need to be provided as environment variables'):
        super().__init__(message)

class InvalidTargetFormatError(Exception):
    """ ps2mcs requires targets for sync to follow this convention <CardName>/<CardName>-<Channel>.mc2 """
    def __init__(self, message='Unsupported target file format encountered. ps2mcs requires targets for sync to follow this convention <CardName>/<CardName>-<Channel>.mc2'):
        super().__init__(message)

def main():
    try:
        args = read_args()
        local_root = Path(args.local).resolve()

        target_path = Path(MCPD2_PS2_ROOT) / Path(args.target)
        validate_remote_path(target_path)

        (uname, pwd) = read_creds()
        print(f'{uname},{pwd}')
        
        # Get file mapping strategy
        ms = create_mapping_strategy()

        local_path = local_root / Path(ms.map_remote_to_local(target_path))
        print(f'{target_path} ---> {local_path}')

        ftp = create_ftp_connection(args.ftp_host, uname, pwd)

        if args.direction == 'down':
            # Check path to file locally exists, create if not
            local_path.parent.mkdir(parents=True, exist_ok=True)
        
            sync_file_down(ftp, local_path, target_path)
        else:
            sync_file_up(ftp, local_path, target_path)

    except Exception as e:
        print(f'Failed to sync: {e}')

    print(f'Done')

# TODO - Not sure how to incorporate direction yet - interleaved or strategy ... not sure
def sync_file_down(ftp, local_path, remote_path):
    try:
        # Get remote file's modified time
        rmt = get_remote_modified_time(ftp, remote_path)

        # Check if local file exists
        if os.path.exists(local_path):
            lmt = int(os.path.getmtime(local_path))

            # Compare times and decide action
            if rmt > lmt:
                sync_remote_file_to_local(ftp, remote_path, local_path, rmt)
            elif lmt > rmt:
                print(f'LOCAL IS NEWER - WHAT NOW?')
            else:
                print(f'{local_path} is already up-to-date')
        else:
            # Local file doesn't exist, download from server
            sync_remote_file_to_local(ftp, remote_path, local_path, rmt)
    except Exception as e:
        print(f'Error syncing file {remote_path}: {e}')

def sync_file_up(ftp, local_path, remote_path):
    try:
        if not os.path.exists(local_path):
            raise FileNotFoundError(f'{local_path} does not exist. Sync it down, first')

        # Get remote file's modified time
        rmt = get_remote_modified_time(ftp, remote_path)
        lmt = int(os.path.getmtime(local_path))

        # Compare times and decide action
        if lmt > rmt:
            sync_local_file_to_remote(ftp, local_path, remote_path)
        elif rmt > lmt:
            print(f'Remote file is newer')
        else:
            print(f'{remote_path} is already up-to-date')
    except Exception as e:
        print(f'Error syncing file {remote_path}: {e}')

def sync_local_file_to_remote(ftp, local_path, remote_path):
    with open(local_path, 'rb') as f:
        ftp.storbinary(f'STOR {remote_path}', f)

    # Can't update the time on the MCP2 ... it doesn't support the MFMT command

def sync_remote_file_to_local(ftp, remote_path, local_path, rmt):
    with open(local_path, 'wb') as f:
        ftp.retrbinary(f'RETR {remote_path}', f.write)

    # Update local timestamp so it reflects the remote time
    os.utime(local_path, (rmt, rmt))

def validate_remote_path(target_path):
    pattern = fr'^{MCPD2_PS2_ROOT}/([^/]+)/([^/]+)-([1-8])\.mc2$'

    match = re.match(pattern, str(target_path))

    if match is None:
        raise InvalidTargetFormatError()

def get_remote_modified_time(ftp, filename):
    response = ftp.sendcmd(f"MDTM {filename}") # '213 YYYYMMDDHHMMSS'
    remote_time_str = response[4:]
    return ftp_time_to_unix_timestamp(remote_time_str)

def ftp_time_to_unix_timestamp(ftp_time_str):
    return int(datetime.strptime(ftp_time_str, '%Y%m%d%H%M%S').timestamp())

def create_ftp_connection(ftp_host, uname, pwd):
    ftp = FTP(ftp_host)
    ftp.login(uname, pwd)
    return ftp

def create_mapping_strategy():
    return FlatMappingStrategy()

def read_creds():
    uname = os.getenv('MCP2_USER')
    pwd = os.getenv('MCP2_PWD')

    if uname == None or pwd == None:
        raise MissingCredentialError()
    
    return (uname, pwd)

def read_args():
    parser = argparse.ArgumentParser(
        description='''ps2mcs is a command line tool that syncs PS2 memory card images between a MemCard PRO 2 and PC''')
    parser.add_argument('-d', '--direction', choices=['up', 'down'], required=True, help="Direction of sync: 'up' (PC -> MCP2) or 'down' (PC <- MCP2)")
    parser.add_argument('-t', '--target', type=str, required=True, help='Target file to sync')
    parser.add_argument('-f', '--ftp_host', type=str, required=True, help='Address of the FTP server')
    parser.add_argument('-l', '--local', type=str, default='.', help='Local directory used as a source to sync memory card images to/from')
    parser.add_argument('-v', '--version', action='version', version=f'%(prog)s {VERSION}')
    return parser.parse_args()

if __name__ == "__main__":
    main()