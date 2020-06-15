from os.path import isdir, splitext, join
from vidtopod import convert
from sys import platform
from os import walk

# todo: for mkv files always pick the japanese audio track (or give an prompt to specify language track)
    # should be something like: jp
# todo: add support for automatically extracting subtitles from mkv files
    # if there are multiple subtitles in the mkv it should ask which one to pull
    # but allow people to just default to using the first subtitle found (because fuck Judas)
# todo: make it cross-platform so it supports Mac and Linux distros.
# todo: create a github website
    # pictures on the site to demo it
    # explain how to use it
    # change the file names so it's not obvious that you torrented the files


def _prompt_for_dir(prompt):
    location = None
    ok = False

    while not ok:
        location = input(prompt)
        ok = isdir(location)

    return location


def _prompt_for_ms(prompt):
    ms = None
    ok = False

    while not ok:
        ms = input(prompt + ' (ms) (leave blank if none needed): ').strip()
        if ms == '':
            ms = None
            break
        ms, ok = _try_parse_int(ms)

    return ms


def _try_parse_int(value):
    try:
        return int(value), True
    except ValueError:
        return value, False


print('[video-to-podcast] developed by true-zero (discord: Kaguya#1337)')

if platform not in ['win32', 'darwin', 'linux']:
    print('[video-to-podcast]: unsupported platform')
    input('Press enter to exit.')
    exit(0)

storage_location = _prompt_for_dir('location of where to store: ')
animes_location = _prompt_for_dir('location of anime to convert: ')
lang_code = input('audio track language code (leave blank if none needed): ')
if lang_code == '':
    lang_code = None
subtitle_sync_ms = _prompt_for_ms('subtitle offset')
padding_ms = _prompt_for_ms('pad timing')

for root, _, file_names in walk(animes_location): # r'D:\Netflix'
    file_names = list(filter(lambda p: splitext(p)[1] in ['.mp4', '.mkv'], file_names))

    if len(file_names) == 0:
        continue

    for file_name in file_names:
        exit_code = convert(storage_location, join(root, file_name), lang_code, subtitle_sync_ms, padding_ms)

        if exit_code is None:
            continue

        if exit_code == 1:
            print(f'[video-to-podcast] already has been converted {splitext(file_name)[0]}, skipping')
        elif exit_code == 2:
            print(f'[video-to-podcast] no track found with the id "{lang_code}" {splitext(file_name)[0]}, skipping')
        elif exit_code == 3:
            print(f'[video-to-podcast] no subtitles were found for {splitext(file_name)[0]}, skipping')
