# ps2mcs
ps2mcs is a command line tool that syncs PS2 memory card images between an [8BitMods MemCard PRO2](https://8bitmods.com/memcard-pro2-for-ps2-and-ps1-smoke-black/) and PC

### Notes
Created to me help keep memory card images in sync between those on my [8BitMods MemCard PRO2](https://8bitmods.com/memcard-pro2-for-ps2-and-ps1-smoke-black/) and those on my PC that I use with [PCSX2](https://pcsx2.net/). Works in a one time fashion where one execution will sync the target files (configured in targets.json) across both devices and then quit. Can easily be integrated into a higher level cron or scheduled task if you want a more continuous sync.

Leverages the FTP capability of the MemCard PRO2 and relies on the system time of your PS2 being accurate. Provide the credentials in a couple of environment vairables, `MCP2_USER` and `MCP2_PWD`

### Usage Instructions
#### Environment Variables
Make sure that the following two environment variables are set with the credentials of the MCP2 FTP server,
```
MCP2_USER
MCP2_PWD
```
#### Configuration
Add the filenames of the memory card images you want to sync to the targets.json config file. The filenames need to be the filenames as they exist on the MCP2,
```json
{
    "targets": [
        "SLUS-21274-1.mc2",
        "SLPM-62703-1.mc2"
    ]
}
```
#### Usage
```bash
usage: ps2mcs.py [-h] -f FTP_HOST [-l LOCAL] [-v]

ps2mcs is a command line tool that syncs PS2 memory card images between a MemCard PRO 2 and PC

optional arguments:
  -h, --help            show this help message and exit
  -f FTP_HOST, --ftp_host FTP_HOST
                        Address of the FTP server
  -l LOCAL, --local LOCAL
                        Local directory used as a source to sync memory card images to/from   
  -v, --version         show program's version number and exit
  ```
### Examples

To sync the files in targets.json between local directory, `~/PS2/memcards`, and a MemCard PRO 2 at `192.168.36.42`
```
$ ./ps2mcs.py -l ~/PS2/memcards -f 192.168.36.42
...
```