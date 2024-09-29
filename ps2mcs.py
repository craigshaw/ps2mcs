#!/usr/bin/env python3

import argparse
import os
import re

from datetime import datetime
from ftplib import FTP
from pathlib import Path

from mapping.flat import FlatMappingStrategy

VERSION = "0.0.1"
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

        print(f'{args.target}')

        target_path = Path(MCPD2_PS2_ROOT) / Path(args.target)
        extract_target_components(target_path)

        # Get creds
        (uname, pwd) = read_creds()
        print(f'{uname},{pwd}')

        # Get file mapping strategy
        ms = create_mapping_strategy()
        local_path = local_root / Path(ms.map_remote_to_local(target_path))
        # Check path to file locally exists, create if not
        local_path.parent.mkdir(parents=True, exist_ok=True)
        print(f'{target_path} ---> {local_path}')

        ftp = create_ftp_connection(args.ftp_host, uname, pwd)
        # print(get_remote_modified_time(ftp, args.target))
        sync_file_down(ftp, local_path, target_path)

    except Exception as e:
        print(f'Failed to sync: {e}')

    print(f'Done')

# TODO - Not sure how to incorporate direction yet - interleaved or strategy ... not sure
def sync_file_down(ftp, local_path, remote_path):
    try:
        # Get remote file's modified time
        remote_modified_time = get_remote_modified_time(ftp, remote_path)
        print(f"Remote file '{remote_path}' last modified: {remote_modified_time}")

        # Check if local file exists
        if os.path.exists(local_path):
            local_modified_time = datetime.fromtimestamp(os.path.getmtime(local_path))
            print(f"Local file '{local_path}' last modified: {local_modified_time}")

            # Compare times and decide action
            if remote_modified_time > local_modified_time:
                print(f"Downloading newer file: {remote_path}")
                with open(local_path, 'wb') as f:
                    ftp.retrbinary(f"RETR {remote_path}", f.write)

                # Update local timestamp so it reflects the remote time
                rmt = int(remote_modified_time.timestamp())
                os.utime(local_path, (rmt, rmt))
            elif local_modified_time > remote_modified_time:
                print(f'LOCAL IS NEWER - WHAT NOW?')
            #     print(f"Uploading newer file: {local_path}")
            #     with open(local_path, 'rb') as f:
            #         ftp.storbinary(f"STOR {remote_path}", f)

            #     set_remote_file_timestamp(ftp, remote_path, local_modified_time)
            else:
                print(f"File '{remote_path}' is already up-to-date.")
        else:
            # Local file doesn't exist, download from server
            print(f"Local file '{local_path}' does not exist. Downloading...")
            with open(local_path, 'wb') as f:
                ftp.retrbinary(f"RETR {remote_path}", f.write)

            # Update local timestamp so it reflects the remote time
            rmt = int(remote_modified_time.timestamp())
            os.utime(local_path, (rmt, rmt))
    except Exception as e:
        print(f"Error syncing file '{remote_path}': {e}")


def extract_target_components(target_path):
    pattern = fr'^{MCPD2_PS2_ROOT}/([^/]+)/([^/]+)-([1-8])\.mc2$'

    match = re.match(pattern, str(target_path))

    if match:
        vmc_dir = match.group(1)
        vmc_file = match.group(2)
        vmc_channel = match.group(3)

        print(f"VMC Dir: {vmc_dir}")
        print(f"VMC File: {vmc_file}")
        print(f"VMC Channel: {vmc_channel}")

        return (vmc_dir, vmc_file, vmc_channel)
    else:
        raise InvalidTargetFormatError()

def get_remote_modified_time(ftp, filename):
    response = ftp.sendcmd(f"MDTM {filename}") # '213 YYYYMMDDHHMMSS'
    remote_time_str = response[4:]
    return parse_ftp_time(remote_time_str)

def parse_ftp_time(ftp_time_str):
    return datetime.strptime(ftp_time_str, '%Y%m%d%H%M%S')

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