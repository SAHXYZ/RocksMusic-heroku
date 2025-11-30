# ATLEAST GIVE CREDITS IF YOU STEALING :(((((((((((((((((((((((((((((((((((((
# ELSE NO FURTHER PUBLIC THUMBNAIL UPDATES

import random
import logging
import os
import re
import traceback
import aiofiles
import aiohttp
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont
from youtubesearchpython.__future__ import VideosSearch

logging.basicConfig(level=logging.INFO)


# tape window coordinates (inside neon cassette)
TAPE_X1 = 350
TAPE_Y1 = 140
TAPE_X2 = 930
TAPE_Y2 = 500


def resize_to_fit(w, h, img):
    return img.resize((w, h), Image.LANCZOS)


def truncate(text):
    words = text.split(" ")
    t1 = ""
    t2 = ""
    for w in words:
        if len(t1) + len(w) < 30:
            t1 += " " + w
        elif len(t2) + len(w) < 30:
            t2 += " " + w
    return [t1.strip(), t2.strip()]


async def gen_thumb(videoid: str):
    try:
        if os.path.isfile(f"cache/{videoid}_v5.png"):
            return f"cache/{videoid}_v5.png"

        url = f"https://www.youtube.com/watch?v={videoid}"
        results = VideosSearch(url, limit=1)

        for result in (await results.next())["result"]:
            title = result.get("title")
            if title:
                title = re.sub("\W+", " ", title).title()
            else:
                title = "Unsupported Title"

            duration = result.get("duration") or "Live"

            thumbnail_data = result.get("thumbnails")
            thumbnail = thumbnail_data[0]["url"].split("?")[0] if thumbnail_data else None

            views_data = result.get("viewCount")
            views = views_data.get("short") if views_data else "Unknown Views"

            channel_data = result.get("channel")
            channel = channel_data.get("name") if channel_data else "Unknown Channel"

        # DOWNLOAD YOUTUBE THUMBNAIL
        async with aiohttp.ClientSession() as session:
            async with session.get(thumbnail) as resp:
                content = await resp.read()
                if resp.status != 200:
                    return None
                filepath = f"cache/thumb{videoid}.png"
                async with aiofiles.open(filepath, "wb") as f:
                    await f.write(content)

        youtube_thumb = Image.open(filepath).convert("RGBA")

        # LOAD YOUR TEMPLATE
        template = Image.open("RocksMusic/assets/neon_tape.png").convert("RGBA")

        # Extract tape area size
        tape_w = TAPE_X2 - TAPE_X1
        tape_h = TAPE_Y2 - TAPE_Y1

        # Resize YT thumb into cassette area
        resized_thumb = resize_to_fit(tape_w, tape_h, youtube_thumb)

        # Paste the thumbnail inside the tape window
        template.paste(resized_thumb, (TAPE_X1, TAPE_Y1), resized_thumb)

        draw = ImageDraw.Draw(template)

        # Load fonts
        arial = ImageFont.truetype("RocksMusic/assets/font2.ttf", 30)
        font = ImageFont.truetype("RocksMusic/assets/font.ttf", 30)
        title_font = ImageFont.truetype("RocksMusic/assets/font3.ttf", 45)

        # TEXT POSITIONS
        TITLE_X = 80
        TITLE_Y = 540

        title1 = truncate(title)
        draw.text((TITLE_X, TITLE_Y), title1[0], font=title_font, fill="white")
        draw.text((TITLE_X, TITLE_Y + 50), title1[1], font=title_font, fill="white")

        draw.text((TITLE_X, TITLE_Y + 120), f"{channel}  |  {views}", font=arial, fill="white")

        # Progress bar
        BAR_X = 80
        BAR_Y = 650
        BAR_LEN = 1120

        # Color progress
        if duration != "Live":
            pct = random.uniform(0.15, 0.85)
            fill_len = int(BAR_LEN * pct)
            draw.line((BAR_X, BAR_Y, BAR_X + fill_len, BAR_Y), fill=(255, 100, 150), width=10)
            draw.line((BAR_X + fill_len, BAR_Y, BAR_X + BAR_LEN, BAR_Y), fill="white", width=8)
        else:
            draw.line((BAR_X, BAR_Y, BAR_X + BAR_LEN), fill="red", width=10)

        draw.text((BAR_X, BAR_Y + 20), "00:00", font=arial, fill="white")
        draw.text((1170, BAR_Y + 20), duration, font=arial, fill="white")

        # PLAY ICONS
        play_icons = Image.open("RocksMusic/assets/play_icons.png").convert("RGBA")
        play_icons = play_icons.resize((580, 62))
        template.paste(play_icons, (450, 720), play_icons)

        # CLEANUP
        os.remove(filepath)

        final_path = f"cache/{videoid}_v5.png"
        template.save(final_path)

        return final_path

    except Exception as e:
        logging.error(f"Error generating thumbnail for video {videoid}: {e}")
        traceback.print_exc()
        return None
