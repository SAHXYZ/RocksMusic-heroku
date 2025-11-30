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

# Full cassette area (OPTION C)
TAPE_X1 = 270
TAPE_Y1 = 80
TAPE_X2 = 1010
TAPE_Y2 = 570


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

        # LOAD FINAL TEMPLATE
        template = Image.open("RocksMusic/assets/neon_tape.png").convert("RGBA")

        # Resize YT thumb to cassette window
        tape_w = TAPE_X2 - TAPE_X1
        tape_h = TAPE_Y2 - TAPE_Y1
        resized_thumb = resize_to_fit(tape_w, tape_h, youtube_thumb)

        # Paste thumbnail into cassette
        template.paste(resized_thumb, (TAPE_X1, TAPE_Y1), resized_thumb)

        draw = ImageDraw.Draw(template)

        # Text fonts
        arial = ImageFont.truetype("RocksMusic/assets/font2.ttf", 30)
        main_font = ImageFont.truetype("RocksMusic/assets/font3.ttf", 45)

        # Title / channel text
        TITLE_X = 80
        TITLE_Y = 620

        title_lines = truncate(title)
        draw.text((TITLE_X, TITLE_Y), title_lines[0], font=main_font, fill="white")
        draw.text((TITLE_X, TITLE_Y + 55), title_lines[1], font=main_font, fill="white")

        draw.text((TITLE_X, TITLE_Y + 120), f"{channel}  |  {views}", font=arial, fill="white")

        # Progress bar
        BAR_X = 80
        BAR_Y = 700
        BAR_LEN = 1120

        if duration != "Live":
            pct = random.uniform(0.15, 0.85)
            filled = int(BAR_LEN * pct)
            draw.line((BAR_X, BAR_Y, BAR_X + filled, BAR_Y), fill=(255, 120, 190), width=10)
            draw.line((BAR_X + filled, BAR_Y, BAR_X + BAR_LEN, BAR_Y), fill="white", width=8)
        else:
            draw.line((BAR_X, BAR_Y, BAR_X + BAR_LEN, BAR_Y), fill="red", width=10)

        draw.text((BAR_X, BAR_Y + 20), "00:00", font=arial, fill="white")
        draw.text((1170, BAR_Y + 20), duration, font=arial, fill="white")

        # Play icons
        play_icons = Image.open("RocksMusic/assets/play_icons.png").convert("RGBA")
        play_icons = play_icons.resize((580, 62))
        template.paste(play_icons, (450, 760), play_icons)

        os.remove(filepath)

        final_path = f"cache/{videoid}_v5.png"
        template.save(final_path)

        return final_path

    except Exception as e:
        logging.error(f"Error generating thumbnail for video {videoid}: {e}")
        traceback.print_exc()
        return None
