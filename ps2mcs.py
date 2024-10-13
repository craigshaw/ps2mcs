#!/usr/bin/env python3

import argparse
import asyncio
import json
import os
import time
import traceback

from enum import Enum
from datetime import datetime
from pathlib import Path

import aioftp

from progress import print_progress
from mapping.flat import FlatMappingStrategy
from sync_target import SyncTarget

VERSION = "1.0.1"
TARGET_CONFIG = "targets.json"

class SyncOperation(Enum):
    UPLOAD = "upload"
    DOWNLOAD = "download"
    NO_OP = "no_op"

class MissingCredentialError(Exception):
    """ ps2mcs requires MCP2 FTP creds be provided by environment variables. Specifically, MCP2_USER to provide the username and MCP2_PWD to provide the password """
    def __init__(self, message='MCP2 credentials missing. MCP2_USER and MCP2_PWD need to be provided as environment variables'):
        super().__init__(message)

config = {}

def main():
    global config
    try:
        config = configure()

        sync_targets = create_sync_targets(config['sync_files'], config['local_dir'], create_mapping_strategy())

        start_time = time.perf_counter()

        asyncio.run(sync_all(config['ftp_host'], config['uname'], config['pwd'], sync_targets))

        sync_time = (time.perf_counter() - start_time)

        print(f'Finished in {sync_time:.3f}s')
    except Exception as e:
        print(f'Failed to sync: {e}')
        traceback.print_exc()

def create_sync_targets(files_to_sync, sync_root, ms):
    return [SyncTarget(f, sync_root, ms) for f in files_to_sync]

def read_sync_config():
    with open(TARGET_CONFIG, 'r') as f:
        config = json.load(f)

    return config.get('targets', [])

async def sync_all(ftp_host, user, pwd, sync_targets):
    try:
        async with aioftp.Client.context(ftp_host, user=user, password=pwd) as client:
            for i, target in enumerate(sync_targets):
                await sync_file(client, target, i, len(sync_targets))
    except asyncio.CancelledError:
        print()

def prettify_nix_time(nix_time):
    # 'dd/mm/yyyy hh:mm:ss'
    return datetime.fromtimestamp(nix_time).strftime('%d/%m/%Y %H:%M:%S')

async def sync_file(ftp, target, idx, total):
    operation = SyncOperation.NO_OP
    lmt = 0
    rmt = 0

    try:
        # Get remote file's modified time
        rmt = await get_remote_modified_time(ftp, target.remote_path)

        # Check if local file exists
        if os.path.exists(target.local_path):
            lmt = int(os.path.getmtime(target.local_path))

            # Compare times and decide action
            if rmt > lmt:
                operation = SyncOperation.DOWNLOAD
            elif lmt > rmt:
                operation = SyncOperation.UPLOAD
        else:
            operation = SyncOperation.DOWNLOAD

        print_sync_summary(target, idx, total, lmt, rmt, operation)

        if operation == SyncOperation.DOWNLOAD:
            await download_file(ftp, target.remote_path, target.local_path, rmt)
        elif operation == SyncOperation.UPLOAD:
            await upload_file(ftp, target.local_path, target.remote_path)

    except Exception as e:
        print(f'Error syncing file {target.remote_path}: {e}')
        traceback.print_exc()

def print_sync_summary(target, idx, total, lmt, rmt, operation):
    status = f'{current_time()}: [{idx+1}/{total}] {prettify_nix_time(lmt)} {target.local_path.name} <--> {target.remote_path.name} {prettify_nix_time(rmt)} | '
    if operation == SyncOperation.DOWNLOAD:
        if lmt == 0:
            status += f'No local file. Downloading...'
        else:
            status += f'Remote is newer. Downloading...'
    elif operation == SyncOperation.UPLOAD:
        status += f'Local is newer. Uploading...'
    else:
        status += f'Files are in sync'

    print(status)

async def upload_file(ftp, local_path, remote_path):
    total_size = os.path.getsize(local_path)
    uploaded = 0
    
    with open(local_path, "rb") as local_file:
        async with ftp.upload_stream(remote_path) as stream:
            while True:
                block = local_file.read(1024) 
                if not block:
                    break 
                
                await stream.write(block)
                uploaded += len(block)

                if not config['basic']:
                    print_progress(uploaded, total_size)

    summary = '' if not config['basic'] else f'{current_time()}: Uploaded {total_size} bytes to {remote_path}'
    print(summary)

    # Because we can't update the modified time on the MCP2 (no MFMT command support)...
    # lets update the timestamp on our local file to that of the time on the MCP2
    rmt = await get_remote_modified_time(ftp, remote_path)
    os.utime(local_path, (rmt, rmt))

async def download_file(ftp, remote_path, local_path, rmt):
    response = await ftp.command(f'size {remote_path}', '213')
    total_size = int(response[1][0].strip())
    downloaded = 0
    
    with open(local_path, "wb") as local_file:
        async with ftp.download_stream(remote_path) as stream:
            async for block in stream.iter_by_block():
                local_file.write(block)
                downloaded += len(block)

                if not config['basic']:
                    print_progress(downloaded, total_size)

    summary = '' if not config['basic'] else f'{current_time()}: Downloaded {total_size} bytes to {local_path}'
    print(summary)

    # Update local timestamp so it reflects the remote time
    os.utime(local_path, (rmt, rmt))

async def get_remote_modified_time(ftp, filename):
    response = await ftp.command(f'MDTM {filename}', '213') # '213 YYYYMMDDHHMMSS'
    remote_time_str = response[1][0].strip()
    return ftp_time_to_unix_timestamp(remote_time_str)

def current_time():
    return datetime.now().strftime("%d/%m/%y %H:%M:%S:%f")[:-3]

def ftp_time_to_unix_timestamp(ftp_time_str):
    return int(datetime.strptime(ftp_time_str, '%Y%m%d%H%M%S').timestamp())

def create_mapping_strategy():
    return FlatMappingStrategy()

def read_creds():
    uname = os.getenv('MCP2_USER')
    pwd = os.getenv('MCP2_PWD')

    if uname == None or pwd == None:
        raise MissingCredentialError()
    
    return (uname, pwd)

def configure():
    config = {}
    args = read_args()

    config['local_dir'] = Path(args.local).resolve()
    config['ftp_host'] = args.ftp_host
    config['sync_files'] = read_sync_config()
    config['basic'] = args.basic

    (config['uname'], config['pwd']) = read_creds()

    return config

def read_args():
    parser = argparse.ArgumentParser(
        description='''ps2mcs is a command line tool that syncs PS2 memory card images between a MemCard PRO 2 and PC''')
    parser.add_argument('-f', '--ftp_host', type=str, required=True, help='Address of the FTP server')
    parser.add_argument('-l', '--local', type=str, default='.', help='Local directory used as a source to sync memory card images to/from')
    parser.add_argument('-b', '--basic', type=bool, default=False, help='Basic UI mode. Outputs simple summary on sync complete only')
    parser.add_argument('-v', '--version', action='version', version=f'%(prog)s {VERSION}')
    return parser.parse_args()

if __name__ == "__main__":
    main()