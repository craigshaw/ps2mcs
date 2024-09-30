#!/usr/bin/env python3

import argparse
import json
import os
import re

from datetime import datetime
from ftplib import FTP
from pathlib import Path

from mapping.flat import FlatMappingStrategy

VERSION = "0.3.0"
MCPD2_PS2_ROOT = "files/PS2"
SYNC_TARGETS = "targets.json"

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

        (uname, pwd) = read_creds()
        
        # Get file mapping strategy
        ms = create_mapping_strategy()

        vmcs_to_sync = get_vmcs_to_sync()
        
        ftp = create_ftp_connection(args.ftp_host, uname, pwd)

        for i in range(len(vmcs_to_sync)):
            vmc_path = vmcs_to_sync[i]
            local_path = local_root / Path(ms.map_remote_to_local(vmc_path))
            print(f'[{i+1}/{len(vmcs_to_sync)}]> {vmc_path} <---> {local_path}')

            # Check path to file locally exists, create if not
            local_path.parent.mkdir(parents=True, exist_ok=True)
        
            sync_file(ftp, local_path, vmc_path)
    except Exception as e:
        print(f'Failed to sync: {e}')

def get_vmcs_to_sync():
    with open(SYNC_TARGETS, 'r') as f:
        config = json.load(f)

    vmcs_to_sync = config.get('vmcs_to_sync', [])

    vmc_paths = []

    for vmc in vmcs_to_sync:
        target_path = Path(MCPD2_PS2_ROOT) / Path(vmc)
        validate_remote_path(target_path)
        vmc_paths.append(target_path)

    return vmc_paths

def sync_file(ftp, local_path, remote_path):
    try:
        # Get remote file's modified time
        rmt = get_remote_modified_time(ftp, remote_path)

        # Check if local file exists
        if os.path.exists(local_path):
            lmt = int(os.path.getmtime(local_path))

            # Compare times and decide action
            if rmt > lmt:
                print(f'Remote file is newer. Downloading {local_path}')
                sync_remote_file_to_local(ftp, remote_path, local_path, rmt)
            elif lmt > rmt:
                print(f'Local file is newer. Uploading {remote_path}')
                sync_local_file_to_remote(ftp, local_path, remote_path)
            else:
                print(f'Files are in sync')
        else:
            print(f'Local file doesn\'t exist. Downloading {local_path}')
            sync_remote_file_to_local(ftp, remote_path, local_path, rmt)
    except Exception as e:
        print(f'Error syncing file {remote_path}: {e}')

def sync_local_file_to_remote(ftp, local_path, remote_path):
    with open(local_path, 'rb') as f:
        ftp.storbinary(f'STOR {remote_path}', f)

    # Because we can't update the modified time on the MCP2 (no MFMT command support)...
    # lets update the timestamp on our local file to that of the time on the MCP2
    rmt = get_remote_modified_time(ftp, remote_path)
    os.utime(local_path, (rmt, rmt))

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
    parser.add_argument('-f', '--ftp_host', type=str, required=True, help='Address of the FTP server')
    parser.add_argument('-l', '--local', type=str, default='.', help='Local directory used as a source to sync memory card images to/from')
    parser.add_argument('-v', '--version', action='version', version=f'%(prog)s {VERSION}')
    return parser.parse_args()

if __name__ == "__main__":
    main()