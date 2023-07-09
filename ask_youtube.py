#!/usr/bin/env python3
import csv
import yt_dlp
import sys

levels: list
with open('config/levels.csv') as levels_csv:
    reader = csv.DictReader(levels_csv, skipinitialspace=True)
    levels = [row['name'] for row in reader]

writer = csv.writer(sys.stdout, delimiter='|')
opts = { "quiet": True, "simulate": True }
with yt_dlp.YoutubeDL(opts) as ydl:
    for level in levels:
        search = f'"spacechem - {level}"'
        videos = ydl.extract_info(f"ytsearchdateall:{search}", process=False, download=False)['entries']
        for v in videos:
            writer.writerow([v['url'], v['uploader'], v['title']])
