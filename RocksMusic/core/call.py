import asyncio
import os
import json
import subprocess
from datetime import datetime, timedelta
from typing import Union

from pyrogram import Client
from pyrogram.types import InlineKeyboardMarkup
from pytgcalls import PyTgCalls, StreamType
from pytgcalls.exceptions import AlreadyJoinedError, NoActiveGroupCall, TelegramServerError
from pytgcalls.types import Update
from pytgcalls.types.input_stream import AudioPiped, AudioVideoPiped
from pytgcalls.types.input_stream.quality import HighQualityAudio, MediumQualityVideo
from pytgcalls.types.stream import StreamAudioEnded

import config
from RocksMusic import LOGGER, YouTube, app
from RocksMusic.misc import db
from RocksMusic.utils.database import (
    add_active_chat, add_active_video_chat, get_lang, get_loop, group_assistant,
    is_autoend, music_on, remove_active_chat, remove_active_video_chat, set_loop
)
from RocksMusic.utils.exceptions import AssistantErr
from RocksMusic.utils.formatters import check_duration, seconds_to_min, speed_converter
from RocksMusic.utils.inline.play import stream_markup
from RocksMusic.utils.stream.autoclear import auto_clean
from RocksMusic.utils.thumbnails import gen_thumb
from strings import get_string


# ---------- yt-dlp fallback (used only when normal flow fails) ----------
def _download_audio_strict(source: str) -> str:
    try:
        os.makedirs("downloads", exist_ok=True)
        out = "downloads/%(id)s.%(ext)s"
        cmd = [
            "yt-dlp", "-f", "bestaudio/best", "--no-playlist", "--no-warnings",
            "-x", "--audio-format", "mp3", "--audio-quality", "0",
            "-o", out, source
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        files = sorted(
            [f for f in os.listdir("downloads") if f.endswith(".mp3")],
            key=lambda f: os.path.getmtime(os.path.join("downloads", f))
        )
        if not files:
            raise RuntimeError("yt-dlp produced no file.")
        latest = os.path.join("downloads", files[-1])

        probe = subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type", "-of", "json", latest],
            text=True
        )
        meta = json.loads(probe)
        if not any(s.get("codec_type") == "audio" for s in meta.get("streams", [])):
            raise RuntimeError("Downloaded file has no audio stream.")
        return latest
    except Exception as e:
        raise RuntimeError(f"Audio download failed: {e}")


autoend = {}
counter = {}


async def _clear_(chat_id: int):
    db[chat_id] = []
    await remove_active_video_chat(chat_id)
    await remove_active_chat(chat_id)


class Call(PyTgCalls):
    def __init__(self):
        # up to 5 assistants supported by your config
        self.userbot1 = Client("RocksAss1", api_id=config.API_ID, api_hash=config.API_HASH, session_string=str(config.STRING1))
        self.one   = PyTgCalls(self.userbot1, cache_duration=100)
        self.userbot2 = Client("RocksAss2", api_id=config.API_ID, api_hash=config.API_HASH, session_string=str(config.STRING2))
        self.two   = PyTgCalls(self.userbot2, cache_duration=100)
        self.userbot3 = Client("RocksAss3", api_id=config.API_ID, api_hash=config.API_HASH, session_string=str(config.STRING3))
        self.three = PyTgCalls(self.userbot3, cache_duration=100)
        self.userbot4 = Client("RocksAss4", api_id=config.API_ID, api_hash=config.API_HASH, session_string=str(config.STRING4))
        self.four  = PyTgCalls(self.userbot4, cache_duration=100)
        self.userbot5 = Client("RocksAss5", api_id=config.API_ID, api_hash=config.API_HASH, session_string=str(config.STRING5))
        self.five  = PyTgCalls(self.userbot5, cache_duration=100)

    # -------- basic controls --------
    async def pause_stream(self, chat_id: int):
        (await group_assistant(self, chat_id)).pause_stream(chat_id)

    async def resume_stream(self, chat_id: int):
        (await group_assistant(self, chat_id)).resume_stream(chat_id)

    async def stop_stream(self, chat_id: int):
        assistant = await group_assistant(self, chat_id)
        try:
            await _clear_(chat_id)
            await assistant.leave_group_call(chat_id)
        except:
            pass

    async def stop_stream_force(self, chat_id: int):
        for client in (getattr(self, n) for n in ("one","two","three","four","five")):
            try:
                await client.leave_group_call(chat_id)
            except:
                pass
        await _clear_(chat_id)

    # -------- join_call (restored) --------
    async def join_call(
        self,
        chat_id: int,
        original_chat_id: int,
        link: str,
        video: Union[bool, str] = None,
        image: Union[bool, str] = None,
    ):
        assistant = await group_assistant(self, chat_id)
        _ = get_string(await get_lang(chat_id))

        stream = (
            AudioVideoPiped(link, audio_parameters=HighQualityAudio(), video_parameters=MediumQualityVideo())
            if video else
            AudioPiped(link, audio_parameters=HighQualityAudio())
        )
        try:
            await assistant.join_group_call(chat_id, stream, stream_type=StreamType().pulse_stream)
        except NoActiveGroupCall:
            raise AssistantErr(_["call_8"])
        except AlreadyJoinedError:
            raise AssistantErr(_["call_9"])
        except TelegramServerError:
            raise AssistantErr(_["call_10"])

        await add_active_chat(chat_id)
        await music_on(chat_id)
        if video:
            await add_active_video_chat(chat_id)

        if await is_autoend():
            counter[chat_id] = {}
            users = len(await assistant.get_participants(chat_id))
            if users == 1:
                autoend[chat_id] = datetime.now() + timedelta(minutes=1)

    # -------- seek/speed/skip helpers (unchanged logic) --------
    async def seek_stream(self, chat_id, file_path, to_seek, duration, mode):
        assistant = await group_assistant(self, chat_id)
        stream = (
            AudioVideoPiped(file_path, audio_parameters=HighQualityAudio(), video_parameters=MediumQualityVideo(),
                            additional_ffmpeg_parameters=f"-ss {to_seek} -to {duration}")
            if mode == "video"
            else AudioPiped(file_path, audio_parameters=HighQualityAudio(),
                            additional_ffmpeg_parameters=f"-ss {to_seek} -to {duration}")
        )
        await assistant.change_stream(chat_id, stream)

    async def speedup_stream(self, chat_id: int, file_path, speed, playing):
        assistant = await group_assistant(self, chat_id)
        if str(speed) != "1.0":
            base = os.path.basename(file_path)
            chatdir = os.path.join(os.getcwd(), "playback", str(speed))
            os.makedirs(chatdir, exist_ok=True)
            out = os.path.join(chatdir, base)
            if not os.path.isfile(out):
                vs = {"0.5": 2.0, "0.75": 1.35, "1.5": 0.68, "2.0": 0.5}.get(str(speed), 1.0)
                proc = await asyncio.create_subprocess_shell(
                    f'ffmpeg -i "{file_path}" -filter:v setpts={vs}*PTS -filter:a atempo={speed} "{out}"',
                    stdin=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                )
                await proc.communicate()
        else:
            out = file_path

        dur = int(await asyncio.get_event_loop().run_in_executor(None, check_duration, out))
        played, con_seconds = speed_converter(playing[0]["played"], speed)
        duration = seconds_to_min(dur)

        stream = (
            AudioVideoPiped(out, audio_parameters=HighQualityAudio(), video_parameters=MediumQualityVideo(),
                            additional_ffmpeg_parameters=f"-ss {played} -to {duration}")
            if playing[0]["streamtype"] == "video"
            else AudioPiped(out, audio_parameters=HighQualityAudio(),
                            additional_ffmpeg_parameters=f"-ss {played} -to {duration}")
        )
        if str(db[chat_id][0]["file"]) == str(file_path):
            await assistant.change_stream(chat_id, stream)
            exis = (playing[0]).get("old_dur")
            if not exis:
                db[chat_id][0]["old_dur"] = db[chat_id][0]["dur"]
                db[chat_id][0]["old_second"] = db[chat_id][0]["seconds"]
            db[chat_id][0]["played"] = con_seconds
            db[chat_id][0]["dur"] = duration
            db[chat_id][0]["seconds"] = dur
            db[chat_id][0]["speed_path"] = out
            db[chat_id][0]["speed"] = speed

    async def skip_stream(self, chat_id: int, link: str, video: Union[bool, str] = None, image: Union[bool, str] = None):
        assistant = await group_assistant(self, chat_id)
        stream = (
            AudioVideoPiped(link, audio_parameters=HighQualityAudio(), video_parameters=MediumQualityVideo())
            if video else AudioPiped(link, audio_parameters=HighQualityAudio())
        )
        await assistant.change_stream(chat_id, stream)

    # -------- queue advance --------
    async def change_stream(self, client, chat_id):
        check = db.get(chat_id)
        loop = await get_loop(chat_id)
        try:
            if loop == 0:
                popped = check.pop(0)
            else:
                await set_loop(chat_id, loop - 1)
            await auto_clean(popped)
            if not check:
                await _clear_(chat_id)
                return await client.leave_group_call(chat_id)
        except Exception:
            try:
                await _clear_(chat_id)
                return await client.leave_group_call(chat_id)
            except:
                return

        queued = check[0]["file"]
        language = await get_lang(chat_id)
        _ = get_string(language)
        title = (check[0]["title"]).title()
        user = check[0]["by"]
        original_chat_id = check[0]["chat_id"]
        streamtype = check[0]["streamtype"]
        videoid = check[0]["vidid"]
        db[chat_id][0]["played"] = 0

        video = True if str(streamtype) == "video" else False

        # live/index/telegram/soundcloud handled as before
        if "live_" in queued:
            n, link = await YouTube.video(videoid, True)
            if n == 0:
                return await app.send_message(original_chat_id, text=_["call_6"])
            stream = AudioVideoPiped(link, audio_parameters=HighQualityAudio(), video_parameters=MediumQualityVideo()) if video \
                     else AudioPiped(link, audio_parameters=HighQualityAudio())
            try:
                await client.change_stream(chat_id, stream)
            except Exception:
                return await app.send_message(original_chat_id, text=_["call_6"])
            img = await gen_thumb(videoid)
            button = stream_markup(_, chat_id)
            run = await app.send_photo(
                chat_id=original_chat_id, photo=img,
                caption=_["stream_1"].format(f"https://t.me/{app.username}?start=info_{videoid}", title[:23], check[0]["dur"], user),
                reply_markup=InlineKeyboardMarkup(button),
            )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "tg"

        elif "vid_" in queued:
            mystic = await app.send_message(original_chat_id, _["call_7"])
            try:
                file_path, direct = await YouTube.download(videoid, mystic, videoid=True, video=video)
            except Exception:
                try:
                    file_path = _download_audio_strict(f"https://www.youtube.com/watch?v={videoid}")
                except Exception as e:
                    return await mystic.edit_text(f"{_['call_6']}\n\n<code>{e}</code>", disable_web_page_preview=True)
            stream = AudioVideoPiped(file_path, audio_parameters=HighQualityAudio(), video_parameters=MediumQualityVideo()) if video \
                     else AudioPiped(file_path, audio_parameters=HighQualityAudio())
            try:
                await client.change_stream(chat_id, stream)
            except Exception:
                return await app.send_message(original_chat_id, text=_["call_6"])
            await mystic.delete()
            img = await gen_thumb(videoid)
            button = stream_markup(_, chat_id)
            run = await app.send_photo(
                chat_id=original_chat_id, photo=img,
                caption=_["stream_1"].format(f"https://t.me/{app.username}?start=info_{videoid}", title[:23], check[0]["dur"], user),
                reply_markup=InlineKeyboardMarkup(button),
            )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "stream"

        elif "index_" in queued:
            src = videoid
            stream = AudioVideoPiped(src, audio_parameters=HighQualityAudio(), video_parameters=MediumQualityVideo()) if video \
                     else AudioPiped(src, audio_parameters=HighQualityAudio())
            try:
                await client.change_stream(chat_id, stream)
            except Exception:
                return await app.send_message(original_chat_id, text=_["call_6"])
            button = stream_markup(_, chat_id)
            run = await app.send_photo(
                chat_id=original_chat_id, photo=config.STREAM_IMG_URL,
                caption=_["stream_2"].format(user), reply_markup=InlineKeyboardMarkup(button)
            )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "tg"

        else:
            src = queued
            stream = AudioVideoPiped(src, audio_parameters=HighQualityAudio(), video_parameters=MediumQualityVideo()) if video \
                     else AudioPiped(src, audio_parameters=HighQualityAudio())
            try:
                await client.change_stream(chat_id, stream)
            except Exception:
                return await app.send_message(original_chat_id, text=_["call_6"])

            if videoid == "telegram":
                button = stream_markup(_, chat_id)
                run = await app.send_photo(
                    chat_id=original_chat_id,
                    photo=config.TELEGRAM_AUDIO_URL if str(streamtype) == "audio" else config.TELEGRAM_VIDEO_URL,
                    caption=_["stream_1"].format(config.SUPPORT_GROUP, title[:23], check[0]["dur"], user),
                    reply_markup=InlineKeyboardMarkup(button),
                )
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "tg"

            elif videoid == "soundcloud":
                button = stream_markup(_, chat_id)
                run = await app.send_photo(
                    chat_id=original_chat_id, photo=config.SOUNCLOUD_IMG_URL,
                    caption=_["stream_1"].format(config.SUPPORT_GROUP, title[:23], check[0]["dur"], user),
                    reply_markup=InlineKeyboardMarkup(button),
                )
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "tg"

            else:
                img = await gen_thumb(videoid)
                button = stream_markup(_, chat_id)
                run = await app.send_photo(
                    chat_id=original_chat_id, photo=img,
                    caption=_["stream_1"].format(f"https://t.me/{app.username}?start=info_{videoid}", title[:23], check[0]["dur"], user),
                    reply_markup=InlineKeyboardMarkup(button),
                )
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "stream"

    # -------- ping/start/hooks --------
    async def ping(self):
        p = []
        if config.STRING1: p.append(await self.one.ping)
        if config.STRING2: p.append(await self.two.ping)
        if config.STRING3: p.append(await self.three.ping)
        if config.STRING4: p.append(await self.four.ping)
        if config.STRING5: p.append(await self.five.ping)
        return str(round(sum(p) / len(p), 3))

    async def start(self):
        LOGGER(__name__).info("Starting PyTgCalls Client...\n")
        if config.STRING1: await self.one.start()
        if config.STRING2: await self.two.start()
        if config.STRING3: await self.three.start()
        if config.STRING4: await self.four.start()
        if config.STRING5: await self.five.start()

    async def decorators(self):
        @self.one.on_stream_end()
        @self.two.on_stream_end()
        @self.three.on_stream_end()
        @self.four.on_stream_end()
        @self.five.on_stream_end()
        async def _on_end(client, update: Update):
            if isinstance(update, StreamAudioEnded):
                await self.change_stream(client, update.chat_id)


Rocks = Call()
