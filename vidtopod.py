from os.path import join, dirname, basename, splitdrive, splitext, isfile
from concurrent.futures.thread import ThreadPoolExecutor
from subprocess import run, DEVNULL, PIPE
from datetime import datetime, timedelta
from anitopy import parse as aniparse
from pysubparser import parser
from os import walk, remove
from shutil import rmtree
from pathlib import Path
from sys import platform
from re import compile


# best girls are mayuri and kaguya.
# by using this program you agree this is fact.

_jp_ep_number_regex = compile(r'第(\d+)話')
_subadub_ep_number_regex = compile(r'S[0-9]+_?E([0-9]+)')
_ep_number_regexes = [_jp_ep_number_regex, _subadub_ep_number_regex]
_name_replace_regex = compile(r'[^\w\-_\. ]')
_ffmpeg_audio_stream_regex = compile(r'Stream #\d+:\d+\((.+?)\): Audio')
_ffmpeg_subtitle_stream_regex = compile(r'Stream #\d+:\d+\((.+?)\): Subtitle: (.+?)\s')

# these apply to subtitles extracted from netflix
# using subadub
_bgm_indicators_regex = compile('(♪[〜|～]|[〜|～]♪)')
_sfx_regex = compile(r'^（(.+)）$')

_valid_sub_exts = list(parser.PARSERS.keys())


def _get_ffmpeg():
    cmd = ''

    if platform == 'win32':
        cmd = f'ffmpeg/ffmpeg.exe'
    elif platform == 'darwin':
        cmd = f'ffmpeg/darwin-ffmpeg'
    elif platform == 'linux':
        cmd = f'ffmpeg'

    return cmd


def _get_episode_no(title):
    for ep_number_regex in _ep_number_regexes:
        ep_match = ep_number_regex.search(title)

        if ep_match is not None:
            return ep_match.group(1)

    parsed_title = aniparse(title)

    if 'episode_number' in parsed_title:
        return parsed_title['episode_number']

    print(f'[video-to-podcast]: failed to extract episode number for {title}, manually enter in the episode number.')
    return input('Episode number: ')


def _get_mkv_streams(video_path):
    file_name, file_ext = splitext(basename(video_path))

    if file_ext != '.mkv':
        return None

    process = run(f'{_get_ffmpeg()} -i "{video_path}"', stdout=PIPE, stderr=PIPE)
    output = process.stderr.decode('utf-8')
    return [_ffmpeg_audio_stream_regex.findall(output), _ffmpeg_subtitle_stream_regex.findall(output)]


def _convert_video_to_audio(storage_location, video_path, lang_code, mkv_streams):
    drive, tail = splitdrive(video_path)
    dir_name = join(storage_location, dirname(tail[1:]))
    file_name, file_ext = splitext(basename(video_path))
    audio_path = join(dir_name, file_name + '.mp3')
    Path(dir_name).mkdir(parents=True, exist_ok=True)

    stream_cmd = f'{_get_ffmpeg()} -i "{video_path}" -y -ab 160k -ac 2 -ar 44100 -vn "{audio_path}"'

    if mkv_streams is not None and len(mkv_streams[0]) > 1:
        track_id = mkv_streams[0].index(lang_code) if lang_code in mkv_streams[0] else None
        if track_id is not None:
            stream_cmd = f'{_get_ffmpeg()} -i "{video_path}" -map 0:a:{track_id} -y -ab 160k -ac 2 -ar 44100 -vn "{audio_path}"'
            print(f'[video-to-podcast]: selected "{lang_code}" audio track for {file_name}')

    print(f'[video-to-podcast]: started converting {file_name} to audio.')
    run(stream_cmd, stdout=DEVNULL, stderr=DEVNULL)
    print(f'[video-to-podcast]: finished converting {file_name} to audio.')

    return audio_path


def _get_raw_subtitles_for_video(video_path, mkv_streams):
    dir_name = dirname(video_path)
    file_name = basename(video_path)
    video_ext = splitext(video_path)[1]
    target_episode_number = float(_get_episode_no(file_name))

    for root, _, file_names in walk(dir_name):
        for file_name in file_names:
            file_ext = splitext(file_name)[1][1:]

            if file_ext not in _valid_sub_exts:
                continue

            episode_number = float(_get_episode_no(file_name))

            if episode_number == target_episode_number:
                subtitle_path = join(root, file_name)
                return parser.parse(subtitle_path)

    if video_ext == '.mkv':
        subtitles = (None, 0)

        for i, (lang, ext) in enumerate(mkv_streams[1]):
            if ext == 'subrip':
                ext = 'srt'

            subtitle_path = join(dir_name, f'({i}) {file_name}.{ext}')
            run(f'{_get_ffmpeg()} -i "{video_path}" -y -map 0:s:{i} "{subtitle_path}"', stdout=PIPE, stderr=PIPE)
            parsed_subtitles = list(parser.parse(subtitle_path))
            no_subtitles = len(parsed_subtitles)
            remove(subtitle_path)

            if no_subtitles > subtitles[1]:
                subtitles = (parsed_subtitles, no_subtitles)

        return subtitles[0]


def _apply_ms_delta(time, ms):
    return (datetime.strptime(time.strftime('%H:%M:%S.%f'), '%H:%M:%S.%f') + timedelta(milliseconds=ms)).time()


def _calculate_delta(a, b):
    return (datetime.strptime(b.strftime('%H:%M:%S.%f'), '%H:%M:%S.%f') - datetime.strptime(a.strftime('%H:%M:%S.%f'), '%H:%M:%S.%f')).total_seconds()


def _merge_nearby_subtitles(subtitles):
    i = 0

    for _ in range(len(subtitles)):
        while i < len(subtitles) - 1:
            end_of_current_sub = subtitles[i].end
            start_of_next_sub = subtitles[i + 1].start

            if _calculate_delta(end_of_current_sub, start_of_next_sub) > 1:
                break

            subtitles[i].end = subtitles.pop(i + 1).end

        i += 1

    return subtitles


def _get_subtitles_for_file(video_path, mkv_streams, subtitle_sync_ms=None, padding_ms=None):
    file_name = basename(video_path)
    print(f'[video-to-podcast]: getting subtitles for {file_name}.')
    subtitles = []

    for subtitle in _get_raw_subtitles_for_video(video_path, mkv_streams):
        if _bgm_indicators_regex.match(subtitle.text) is not None or len(_sfx_regex.sub('', subtitle.text)) == 0:
            continue

        if subtitle_sync_ms is not None:
            subtitle.start = _apply_ms_delta(subtitle.start, subtitle_sync_ms)
            subtitle.end = _apply_ms_delta(subtitle.end, subtitle_sync_ms)

        if padding_ms is not None:
            subtitle.start = _apply_ms_delta(subtitle.start, -padding_ms)
            subtitle.end = _apply_ms_delta(subtitle.start, padding_ms)

        subtitles.append(subtitle)

    print(f'[video-to-podcast]: got {len(subtitles)} subtitles for {file_name}.')

    return _merge_nearby_subtitles(subtitles)


def _split_audio_by_subs(audio_path, subtitles):
    dir_name = dirname(audio_path)
    file_name, file_ext = splitext(basename(audio_path))
    dir_name = join(dir_name, file_name)
    Path(dir_name).mkdir(parents=True, exist_ok=True)

    executor = ThreadPoolExecutor(max_workers=10)

    for subtitle in subtitles:
        clip_name = _name_replace_regex.sub('_', f'{subtitle.start}_{subtitle.end}')
        cmd = f'{_get_ffmpeg()} -i "{audio_path}" -y -ss {subtitle.start} -to {subtitle.end} -c copy "{join(dir_name, clip_name + file_ext)}"'
        executor.submit(run, cmd, stdout=DEVNULL, stderr=DEVNULL)

    print(f'[video-to-podcast]: started splitting {file_name} by subtitles.')
    executor.shutdown()
    print(f'[video-to-podcast]: finished splitting {file_name} by subtitles.')

    remove(audio_path)
    return dir_name


def _merge_clips(clips_path, audio_path):
    file_name = splitext(basename(audio_path))[0]
    print(f'[video-to-podcast]: started merging {file_name} audio clips.')

    cmd = ''

    if platform == 'win32':
        cmd = f'mp3cat/mp3cat.exe --dir "{clips_path}" -o "{audio_path}"'
    elif platform == 'darwin':
        cmd = f'mp3cat/darwin-mp3cat --dir "{clips_path}" -o "{audio_path}"'
    elif platform == 'linux':
        cmd = f'mp3cat/linux-mp3cat --dir "{clips_path}" -o "{audio_path}"'

    run(cmd, stdout=DEVNULL, stderr=DEVNULL)
    rmtree(clips_path)
    print(f'[video-to-podcast]: finished merging {file_name} audio clips.')


def _validate(storage_location, video_path, lang_code, mkv_streams):
    drive, tail = splitdrive(video_path)
    dir_name = join(storage_location, dirname(tail[1:]))
    file_name = splitext(basename(video_path))[0]
    audio_path = join(dir_name, file_name + '.mp3')

    if isfile(audio_path):
        return 1

    if mkv_streams is not None and len(mkv_streams[0]) > 1:
        track_id = mkv_streams[0].index(lang_code) if lang_code in mkv_streams[0] else None
        if track_id is None:
            return 2

    subtitles = _get_raw_subtitles_for_video(video_path, mkv_streams)

    if subtitles is None:
        return 3


def convert(storage_location, video_path, lang_code, subtitle_sync_ms=None, padding_ms=None):
    mkv_streams = _get_mkv_streams(video_path)
    valid_response = _validate(storage_location, video_path, lang_code, mkv_streams)

    if valid_response is not None:
        return valid_response

    audio_path = _convert_video_to_audio(storage_location, video_path, lang_code,  mkv_streams)
    subtitles = _get_subtitles_for_file(video_path, mkv_streams, subtitle_sync_ms, padding_ms)
    clips_path = _split_audio_by_subs(audio_path, subtitles)
    _merge_clips(clips_path, audio_path)