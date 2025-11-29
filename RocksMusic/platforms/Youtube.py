import asyncio
import os
import re
import json
from typing import Union

import requests
import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from youtubesearchpython.__future__ import VideosSearch

from RocksMusic.utils.database import is_on_off
from RocksMusic.utils.formatters import time_to_seconds

import glob
import random
import logging
import aiohttp
import config
from config import API_URL, API_KEY


# =========================
# TgMusicBot-style Cookies
# =========================

COOKIES_FILES = None  # cached list of cookies file paths


def _init_cookies_dir() -> str:
    """
    Ensure the cookies directory exists and return its path.
    We use ./cookies (same as your previous code).
    """
    cookie_dir = os.path.join(os.getcwd(), "cookies")
    try:
        os.makedirs(cookie_dir, exist_ok=True)
    except Exception as e:
        logging.error(f"Failed to create cookies directory {cookie_dir}: {e}")
    return cookie_dir


def _fetch_content(url: str) -> str:
    """
    Mirror the Go fetchContent(url) logic:

    - Treat URLs as Pastebin or Batbin links.
    - Convert to raw endpoints:
        pastebin.com -> https://pastebin.com/raw/<id>
        batbin.me    -> https://batbin.me/raw/<id>
    - Download and return text content.
    """
    url = url.strip().strip("/")
    if not url:
        raise ValueError("Empty cookie URL")

    parts = url.split("/")
    id_part = parts[-1]

    if "pastebin.com" in url:
        raw_url = f"https://pastebin.com/raw/{id_part}"
    else:
        # Default to batbin raw as in your Go code (batbin.me/raw/<id>)
        raw_url = f"https://batbin.me/raw/{id_part}"

    try:
        resp = requests.get(raw_url, timeout=20)
    except Exception as e:
        raise RuntimeError(f"Failed to GET {raw_url}: {e}") from e

    if resp.status_code != 200:
        raise RuntimeError(f"Unexpected status {resp.status_code} for {raw_url}")

    return resp.text


def _save_content(url: str, content: str, cookie_dir: str) -> str:
    """
    Mirror Go saveContent(url, content):

    - Use last path segment as filename.
    - If empty, build a fallback name from the URL.
    - Always ensure .txt at the end.
    - Save into cookie_dir and return full path.
    """
    url_stripped = url.strip().strip("/")
    parts = url_stripped.split("/")
    filename = parts[-1] if parts and parts[-1] else ""

    if not filename:
        # fallback similar to Go: "file_" + sanitized URL
        safe = url_stripped.replace("/", "_").split("?")[0].replace("#", "")
        filename = f"file_{safe}"

    if not filename.endswith(".txt"):
        filename += ".txt"

    file_path = os.path.join(cookie_dir, filename)
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception as e:
        raise RuntimeError(f"Failed to write cookies file {file_path}: {e}") from e

    return file_path


def _save_all_cookies(urls):
    """
    Python version of Go's saveAllCookies(urls []string):
    - For each URL, fetch raw content and save as .txt in cookies dir.
    - Return list of file paths that were successfully saved.
    """
    cookie_dir = _init_cookies_dir()
    saved_paths = []
    for url in urls:
        if not url:
            continue
        try:
            text = _fetch_content(url)
        except Exception as e:
            logging.error(f"Error fetching cookies from {url}: {e}")
            continue

        try:
            path = _save_content(url, text, cookie_dir)
        except Exception as e:
            logging.error(f"Error saving cookies from {url}: {e}")
            continue

        saved_paths.append(path)

    return saved_paths


def _load_cookies_files():
    """
    Load cookies files from:

    1) Remote URLs defined via COOKIES_URL (converted to COOKIES_URLS in config.py),
       treated as Pastebin/Batbin IDs (TgMusicBot style).
    2) Any existing *.txt files under ./cookies.

    Always returns at least one path by creating an empty cookies.txt
    if no files exist.
    """
    global COOKIES_FILES

    cookie_dir = _init_cookies_dir()
    files = []

    # 1) Download from URLs (TgMusicBot-style COOKIES_URL)
    urls = getattr(config, "COOKIES_URLS", []) or []
    if urls:
        saved = _save_all_cookies(urls)
        files.extend(saved)

    # 2) Collect any existing *.txt cookies under ./cookies (backwards compat)
    try:
        for fname in os.listdir(cookie_dir):
            if fname.endswith(".txt"):
                full = os.path.join(cookie_dir, fname)
                if os.path.isfile(full) and full not in files:
                    files.append(full)
    except FileNotFoundError:
        pass

    # If still no cookies, create one empty cookies.txt so yt-dlp always gets a path
    if not files:
        logging.warning(
            "No cookies .txt files found in ./cookies. "
            "You can configure COOKIES_URL to point to one or more pastebin/batbin IDs."
        )
        empty_path = os.path.join(cookie_dir, "cookies.txt")
        try:
            with open(empty_path, "a", encoding="utf-8"):
                pass
            files.append(empty_path)
        except Exception as e:
            logging.error(f"Failed to create empty cookies.txt at {empty_path}: {e}")

    COOKIES_FILES = files
    return COOKIES_FILES


def cookie_txt_file():
    """
    Return a random cookies.txt file path for yt-dlp usage.

    This is the Python equivalent of TgMusicBot's cookies system:
    - Uses COOKIES_URL env (split into COOKIES_URLS).
    - Downloads from Pastebin/Batbin as raw text.
    - Saves into ./cookies as .txt files.
    - Randomly selects one for each call.

    IMPORTANT: always returns a valid path (file exists).
    """
    global COOKIES_FILES

    if COOKIES_FILES is None:
        COOKIES_FILES = _load_cookies_files()

    if not COOKIES_FILES:
        # Failsafe: try again to ensure at least one file exists.
        COOKIES_FILES = _load_cookies_files()

    # At this point, COOKIES_FILES should contain at least one path.
    return random.choice(COOKIES_FILES)


# =========================
# Rest of original logic
# =========================


async def download_song(link: str):
    video_id = link.split("v=")[-1].split("&")[0]

    download_folder = "downloads"
    for ext in ["mp3", "m4a", "webm"]:
        file_path = f"{download_folder}/{video_id}.{ext}"
        if os.path.exists(file_path):
            # print(f"File already exists: {file_path}")
            return file_path

    song_url = f"{API_URL}/song/{video_id}?api={API_KEY}"
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                async with session.get(song_url) as response:
                    if response.status != 200:
                        raise Exception(
                            f"API request failed with status code {response.status}"
                        )
                    data = await response.json()
                    status = data.get("status", "").lower()
                    if status == "downloading":
                        await asyncio.sleep(2)
                        continue
                    elif status == "error":
                        error_msg = (
                            data.get("error")
                            or data.get("message")
                            or "Unknown error"
                        )
                        raise Exception(f"API error: {error_msg}")
                    elif status == "done":
                        download_url = data.get("link")
                        if not download_url:
                            raise Exception(
                                "API response did not provide a download URL."
                            )
                        break
                    else:
                        raise Exception(f"Unexpected status '{status}' from API.")
            except Exception as e:
                print(f"Error while checking API status: {e}")
                return None

        try:
            file_format = data.get("format", "mp3")
            file_extension = file_format.lower()
            file_name = f"{video_id}.{file_extension}"
            download_folder = "downloads"
            os.makedirs(download_folder, exist_ok=True)
            file_path = os.path.join(download_folder, file_name)

            async with session.get(download_url) as file_response:
                with open(file_path, "wb") as f:
                    while True:
                        chunk = await file_response.content.read(8192)
                        if not chunk:
                            break
                        f.write(chunk)
                return file_path
        except aiohttp.ClientError as e:
            print(f"Network or client error occurred while downloading: {e}")
            return None
        except Exception as e:
            print(f"Error occurred while downloading song: {e}")
            return None
    return None


async def check_file_size(link):
    async def get_format_info(link):
        proc = await asyncio.create_subprocess_exec(
            "yt-dlp",
            "--cookies",
            cookie_txt_file(),
            "-J",
            link,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            print(f"Error:\n{stderr.decode()}")
            return None
        return json.loads(stdout.decode())

    def parse_size(formats):
        total_size = 0
        for format in formats:
            if "filesize" in format:
                total_size += format["filesize"]
        return total_size

    info = await get_format_info(link)
    if info is None:
        return None

    formats = info.get("formats", [])
    if not formats:
        print("No formats found.")
        return None

    total_size = parse_size(formats)
    return total_size


async def shell_cmd(cmd):
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, errorz = await proc.communicate()
    if errorz:
        if "unavailable videos are hidden" in (errorz.decode("utf-8")).lower():
            return out.decode("utf-8")
        else:
            return errorz.decode("utf-8")
    return out.decode("utf-8")


class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"
        self.status = "https://www.youtube.com/oembed?url="
        self.listbase = "https://youtube.com/playlist?list="
        self.reg = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

    async def exists(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if re.search(self.regex, link):
            return True
        else:
            return False

    async def url(self, message_1: Message) -> Union[str, None]:
        messages = [message_1]
        if message_1.reply_to_message:
            messages.append(message_1.reply_to_message)
        text = ""
        offset = None
        length = None
        for message in messages:
            if offset:
                break
            if message.entities:
                for entity in message.entities:
                    if entity.type == MessageEntityType.URL:
                        text = message.text or message.caption
                        offset, length = entity.offset, entity.length
                        break
            elif message.caption_entities:
                for entity in message.caption_entities:
                    if entity.type == MessageEntityType.TEXT_LINK:
                        return entity.url
        if offset in (None,):
            return None
        return text[offset : offset + length]

    async def details(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            title = result["title"]
            duration_min = result["duration"]
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
            vidid = result["id"]
            if str(duration_min) == "None":
                duration_sec = 0
            else:
                duration_sec = int(time_to_seconds(duration_min))
        return title, duration_min, duration_sec, thumbnail, vidid

    async def title(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            title = result["title"]
        return title

    async def duration(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            duration = result["duration"]
        return duration

    async def thumbnail(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
        return thumbnail

    async def video(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        proc = await asyncio.create_subprocess_exec(
            "yt-dlp",
            "--cookies",
            cookie_txt_file(),
            "-g",
            "-f",
            "best[height<=?720][width<=?1280]",
            f"{link}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if stdout:
            return 1, stdout.decode().split("\n")[0]
        else:
            return 0, stderr.decode()

    async def playlist(self, link, limit, user_id, videoid: Union[bool, str] = None):
        if videoid:
            link = self.listbase + link
        if "&" in link:
            link = link.split("&")[0]
        playlist = await shell_cmd(
            f"yt-dlp -i --get-id --flat-playlist --cookies {cookie_txt_file()} "
            f"--playlist-end {limit} --skip-download {link}"
        )
        try:
            result = playlist.split("\n")
            for key in result:
                if key == "":
                    result.remove(key)
        except Exception:
            result = []
        return result

    async def track(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            title = result["title"]
            duration_min = result["duration"]
            vidid = result["id"]
            yturl = result["link"]
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
        track_details = {
            "title": title,
            "link": yturl,
            "vidid": vidid,
            "duration_min": duration_min,
            "thumb": thumbnail,
        }
        return track_details, vidid

    async def formats(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        ytdl_opts = {"quiet": True, "cookiefile": cookie_txt_file()}
        ydl = yt_dlp.YoutubeDL(ytdl_opts)
        with ydl:
            formats_available = []
            r = ydl.extract_info(link, download=False)
            for format in r["formats"]:
                try:
                    str(format["format"])
                except Exception:
                    continue
                if "dash" not in str(format["format"]).lower():
                    try:
                        format["format"]
                        format["filesize"]
                        format["format_id"]
                        format["ext"]
                        format["format_note"]
                    except Exception:
                        continue
                    formats_available.append(
                        {
                            "format": format["format"],
                            "filesize": format["filesize"],
                            "format_id": format["format_id"],
                            "ext": format["ext"],
                            "format_note": format["format_note"],
                            "yturl": link,
                        }
                    )
        return formats_available, link

    async def slider(
        self,
        link: str,
        query_type: int,
        videoid: Union[bool, str] = None,
    ):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        a = VideosSearch(link, limit=10)
        result = (await a.next()).get("result")
        title = result[query_type]["title"]
        duration_min = result[query_type]["duration"]
        vidid = result[query_type]["id"]
        thumbnail = result[query_type]["thumbnails"][0]["url"].split("?")[0]
        return title, duration_min, thumbnail, vidid

    async def download(
        self,
        link: str,
        mystic,
        video: Union[bool, str] = None,
        videoid: Union[bool, str] = None,
        songaudio: Union[bool, str] = None,
        songvideo: Union[bool, str] = None,
        format_id: Union[bool, str] = None,
        title: Union[bool, str] = None,
    ) -> str:
        if videoid:
            link = self.base + link
        loop = asyncio.get_running_loop()

        def audio_dl():
            ydl_optssx = {
                "format": "bestaudio/best",
                "outtmpl": "downloads/%(id)s.%(ext)s",
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "cookiefile": cookie_txt_file(),
                "no_warnings": True,
            }
            x = yt_dlp.YoutubeDL(ydl_optssx)
            info = x.extract_info(link, False)
            xyz = os.path.join("downloads", f"{info['id']}.{info['ext']}")
            if os.path.exists(xyz):
                return xyz
            x.download([link])
            return xyz

        def video_dl():
            ydl_optssx = {
                "format": "(bestvideo[height<=?720][width<=?1280][ext=mp4])"
                "+(bestaudio[ext=m4a])",
                "outtmpl": "downloads/%(id)s.%(ext)s",
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "cookiefile": cookie_txt_file(),
                "no_warnings": True,
            }
            x = yt_dlp.YoutubeDL(ydl_optssx)
            info = x.extract_info(link, False)
            xyz = os.path.join("downloads", f"{info['id']}.{info['ext']}")
            if os.path.exists(xyz):
                return xyz
            x.download([link])
            return xyz

        def song_video_dl():
            formats = f"{format_id}+140"
            fpath = f"downloads/{title}"
            ydl_optssx = {
                "format": formats,
                "outtmpl": fpath,
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "no_warnings": True,
                "cookiefile": cookie_txt_file(),
                "prefer_ffmpeg": True,
                "merge_output_format": "mp4",
            }
            x = yt_dlp.YoutubeDL(ydl_optssx)
            x.download([link])

        def song_audio_dl():
            fpath = f"downloads/{title}.%(ext)s"
            ydl_optssx = {
                "format": format_id,
                "outtmpl": fpath,
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "no_warnings": True,
                "cookiefile": cookie_txt_file(),
                "prefer_ffmpeg": True,
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }
                ],
            }
            x = yt_dlp.YoutubeDL(ydl_optssx)
            x.download([link])

        if songvideo:
            await download_song(link)
            fpath = f"downloads/{link}.mp3"
            return fpath
        elif songaudio:
            await download_song(link)
            fpath = f"downloads/{link}.mp3"
            return fpath
        elif video:
            if await is_on_off(1):
                direct = True
                downloaded_file = await download_song(link)
            else:
                proc = await asyncio.create_subprocess_exec(
                    "yt-dlp",
                    "--cookies",
                    cookie_txt_file(),
                    "-g",
                    "-f",
                    "best[height<=?720][width<=?1280]",
                    f"{link}",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await proc.communicate()
                if stdout:
                    downloaded_file = stdout.decode().split("\n")[0]
                    direct = False
                else:
                    file_size = await check_file_size(link)
                    if not file_size:
                        print("None file Size")
                        return
                    total_size_mb = file_size / (1024 * 1024)
                    if total_size_mb > 250:
                        print(
                            f"File size {total_size_mb:.2f} MB exceeds the 100MB limit."
                        )
                        return None
                    direct = True
                    downloaded_file = await loop.run_in_executor(None, video_dl)
        else:
            direct = True
            downloaded_file = await download_song(link)
        return downloaded_file, direct
