#!/usr/bin/env python3

import argparse
import os

from datetime import datetime
from ftplib import FTP
from pathlib import Path

from mapping.flat import FlatMappingStrategy

VERSION = "0.0.1"

class MissingCredentialError(Exception):
    """ ps2mcs requires MCP2 FTP creds be provided by environment variables. Specifically, MCP2_USER to provide the username and MCP2_PWD to rpovide the password """
    def __init__(self, message='MCP2 credentials missing. MCP2_USER and MCP2_PWD need to be provided as environment variables'):
        super().__init__(message)

def main():
    try:
        args = read_args()
        local_path = Path(args.local).resolve()

        print(f'{args.target}')

        # Get creds
        (uname, pwd) = read_creds()
        print(f'{uname},{pwd}')

        # Get file mapping strategy
        ms = create_mapping_strategy()

        ftp = create_ftp_connection(args.ftp_host, uname, pwd)

        print(get_remote_modified_time(ftp, args.target))

    except Exception as e:
        print(f'Failed to sync: {e}')

    print(f'Done')

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