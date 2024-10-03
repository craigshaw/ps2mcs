#!/usr/bin/env python3

import aioftp
import argparse
import asyncio
import json
import os
import re
import time

from datetime import datetime
from pathlib import Path
from progress import print_progress

from mapping.flat import FlatMappingStrategy

VERSION = "0.6.1"
MCPD2_PS2_ROOT = "PS2"
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

        sync_targets = load_sync_targets()

        vmcs_to_sync = map_file_paths(ms, local_root, sync_targets)

        start_time = time.perf_counter()

        asyncio.run(sync_all(args.ftp_host, uname, pwd, vmcs_to_sync))

        sync_time = (time.perf_counter() - start_time)

        print(f'Finished in {sync_time:.3f}s')
    except Exception as e:
        print(f'Failed to sync: {e}')

def load_sync_targets():
    with open(SYNC_TARGETS, 'r') as f:
        config = json.load(f)

    return config.get('vmcs_to_sync', [])

def map_file_paths(ms, local_root, targets):
    mapped_paths = []

    for vmc in targets:
        # Generate the remote path
        target_path = create_remote_path(vmc)

        # Map to a local path
        local_path = local_root / Path(ms.map_remote_to_local(target_path))
        # Check path to file locally exists, create if not
        local_path.parent.mkdir(parents=True, exist_ok=True)

        mapped_paths.append((target_path, local_path))

    return mapped_paths

async def sync_all(ftp_host, user, pwd, targets):
    try:
        async with aioftp.Client.context(ftp_host, user=user, password=pwd) as client:
            for (lp, rp) in targets:
                await sync_file(client, rp, lp)
    except asyncio.CancelledError as ce:
        print()

async def sync_file(ftp, local_path, remote_path):
    try:
        # Get remote file's modified time
        rmt = await get_remote_modified_time(ftp, remote_path)

        # Check if local file exists
        if os.path.exists(local_path):
            lmt = int(os.path.getmtime(local_path))

            # Compare times and decide action
            if rmt > lmt:
                print(f'Remote file is newer. Downloading {local_path}')
                await sync_remote_file_to_local_stream(ftp, remote_path, local_path, rmt)
            elif lmt > rmt:
                print(f'Local file is newer. Uploading {remote_path}')
                await sync_local_file_to_remote_stream(ftp, local_path, remote_path)
            else:
                print(f'Files are in sync')
        else:
            print(f'Local file doesn\'t exist. Downloading {local_path}')
            await sync_remote_file_to_local_stream(ftp, remote_path, local_path, rmt)
    except Exception as e:
        print(f'Error syncing file {remote_path}: {e}')

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

                await asyncio.sleep(1)

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
    total_size = int((await ftp.stat(remote_path))["size"]) 
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
    response = await ftp.command(f"MDTM {filename}", "213") # '213 YYYYMMDDHHMMSS'
    remote_time_str = response[1][0].strip()
    return ftp_time_to_unix_timestamp(remote_time_str)

def create_remote_path(target_file):
    pattern = r"([^/]+)-([1-8])\.mc2$"

    match = re.match(pattern, str(target_file))

    if match:
        filename = match.group(1)  # The filename part (SLUS-21274)

        return Path(MCPD2_PS2_ROOT) / Path(f'{filename}/{target_file}')
    else:
        raise InvalidTargetFormatError()

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