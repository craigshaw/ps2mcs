#!/usr/bin/env python3

import platform
import sys
import time

PROGRESS_BAR_LENGTH = 75

class ProgressPrinter():
    def __init__(self, total, bar_length=PROGRESS_BAR_LENGTH):
        self.total = total
        self.bar_length = bar_length
        self.block = '\u2588' if not is_windows() else '#'
        self.shade = '\u2591' if not is_windows() else '-'
        self.progress = 0

    def update_progress(self, progress):
        self.progress = progress
        
    def print_progress(self):
        completed = int((self.bar_length * self.progress) // self.total)
        bar = self.block * completed + self.shade * (self.bar_length - completed)
        percent = round((100 * self.progress) / self.total)

        sys.stdout.write(f'\r{bar} {percent}%')

def is_windows():
    return platform.system() == "Windows"

def print_progress(progress, total):
    length = PROGRESS_BAR_LENGTH
    block = '\u2588' if not is_windows() else '#'
    shade = '\u2591' if not is_windows() else '-'
    completed = int((length * progress) // total)
    bar = block * completed + shade * (length - completed)
    percent = round((100*progress) / total)

    sys.stdout.write(f'\r{bar} {percent}%')

def main():
    total = 500
    p = ProgressPrinter(total)
    for i in range(total + 1):
        time.sleep(0.01)
        p.update_progress(i)
        p.print_progress()

if __name__ == "__main__":
    main()