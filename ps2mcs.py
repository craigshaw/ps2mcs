#!/usr/bin/env python3

import argparse
import os

VERSION = "0.0.1"

class MissingCredentialError(Exception):
    """ ps2mcs requires MCP2 FTP creds be provided by environment variables. Specifically, MCP2_USER to provide the username and MCP2_PWD to rpovide the password """
    def __init__(self, message='MCP2 credentials missing. MCP2_USER and MCP2_PWD need to be provided as environment variables'):
        super().__init__(message)

def main():
    try:
        args = read_args()
        print(f'Syncing {args.direction}')

        # Get creds
        (uname, pwd) = read_creds()
    
        print(uname)
        print(pwd)

    except Exception as e:
        print(f'Failed to sync: {e}')

    print(f'Done')

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
    parser.add_argument('-v', '--version', action='version', version=f'%(prog)s {VERSION}')
    return parser.parse_args()

if __name__ == "__main__":
    main()