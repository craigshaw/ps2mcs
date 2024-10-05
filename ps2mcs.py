#!/usr/bin/env python3

import argparse
import asyncio
import json
import os
import time

from enum import Enum
from datetime import datetime
from pathlib import Path

import aioftp

from progress import print_progress
from mapping.flat import FlatMappingStrategy
from sync_target import SyncTarget

VERSION = "0.8.1"
TARGET_CONFIG = "targets.json"

class SyncOperation(Enum):
    UPLOAD = "upload"
    DOWNLOAD = "download"
    NO_OP = "no_op"

class MissingCredentialError(Exception):
    """ ps2mcs requires MCP2 FTP creds be provided by environment variables. Specifically, MCP2_USER to provide the username and MCP2_PWD to provide the password """
    def __init__(self, message='MCP2 credentials missing. MCP2_USER and MCP2_PWD need to be provided as environment variables'):
        super().__init__(message)

def main():
    try:
        args = read_args()
        local_sync_path_root = Path(args.local).resolve()

        (uname, pwd) = read_creds()
        
        # Get file mapping strategy
        ms = create_mapping_strategy()

        files_to_sync = load_filenames_to_sync()

        sync_targets = create_sync_targets(files_to_sync, local_sync_path_root, ms)

        start_time = time.perf_counter()

        asyncio.run(sync_all(args.ftp_host, uname, pwd, sync_targets))

        sync_time = (time.perf_counter() - start_time)

        print(f'Finished in {sync_time:.3f}s')
    except Exception as e:
        print(f'Failed to sync: {e}')

def create_sync_targets(files_to_sync, sync_root, ms):
    return [SyncTarget(f, sync_root, ms) for f in files_to_sync]

def load_filenames_to_sync():
    with open(TARGET_CONFIG, 'r') as f:
        config = json.load(f)

    return config.get('targets', [])

async def sync_all(ftp_host, user, pwd, sync_targets):
    try:
        async with aioftp.Client.context(ftp_host, user=user, password=pwd) as client:
            for i, target in enumerate(sync_targets):
                await sync_file(client, target, i, len(sync_targets))
    except asyncio.CancelledError as ce:
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
            await sync_remote_file_to_local_stream(ftp, target.remote_path, target.local_path, rmt)
        elif operation == SyncOperation.UPLOAD:
            await sync_local_file_to_remote_stream(ftp, target.local_path, target.remote_path)

    except Exception as e:
        print(f'Error syncing file {target.remote_path}: {e}')

def print_sync_summary(target, idx, total, lmt, rmt, operation):
    status = f'[{idx+1}/{total}]: {prettify_nix_time(lmt)} {target.local_path.name} <--> {target.remote_path.name} {prettify_nix_time(rmt)} | '
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

async def sync_local_file_to_remote(ftp, local_path, remote_path):
    await ftp.upload(local_path, remote_path, write_into=True)

    # Because we can't update the modified time on the MCP2 (no MFMT command support)...
    # lets update the timestamp on our local file to that of the time on the MCP2
    rmt = await get_remote_modified_time(ftp, remote_path)
    os.utime(local_path, (rmt, rmt))

async def sync_local_file_to_remote_stream(ftp, local_path, remote_path):
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

                print_progress(uploaded, total_size)
    print()

    # Because we can't update the modified time on the MCP2 (no MFMT command support)...
    # lets update the timestamp on our local file to that of the time on the MCP2
    rmt = await get_remote_modified_time(ftp, remote_path)
    os.utime(local_path, (rmt, rmt))

async def sync_remote_file_to_local(ftp, remote_path, local_path, rmt):
    await ftp.download(remote_path, local_path, write_into=True)

    # Update local timestamp so it reflects the remote time
    os.utime(local_path, (rmt, rmt))

async def sync_remote_file_to_local_stream(ftp, remote_path, local_path, rmt):
    response = await ftp.command(f'size {remote_path}', '213')
    total_size = int(response[1][0].strip())
    # total_size = int((await ftp.stat(remote_path))['size']) 
    downloaded = 0
    
    with open(local_path, "wb") as local_file:
        async with ftp.download_stream(remote_path) as stream:
            async for block in stream.iter_by_block():
                local_file.write(block)
                downloaded += len(block)
                
                print_progress(downloaded, total_size)

    print()

    # Update local timestamp so it reflects the remote time
    os.utime(local_path, (rmt, rmt))

async def get_remote_modified_time(ftp, filename):
    response = await ftp.command(f'MDTM {filename}', '213') # '213 YYYYMMDDHHMMSS'
    remote_time_str = response[1][0].strip()
    return ftp_time_to_unix_timestamp(remote_time_str)

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

def read_args():
    parser = argparse.ArgumentParser(
        description='''ps2mcs is a command line tool that syncs PS2 memory card images between a MemCard PRO 2 and PC''')
    parser.add_argument('-f', '--ftp_host', type=str, required=True, help='Address of the FTP server')
    parser.add_argument('-l', '--local', type=str, default='.', help='Local directory used as a source to sync memory card images to/from')
    parser.add_argument('-v', '--version', action='version', version=f'%(prog)s {VERSION}')
    return parser.parse_args()

if __name__ == "__main__":
    main()