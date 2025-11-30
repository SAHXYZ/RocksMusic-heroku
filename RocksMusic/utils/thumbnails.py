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

# --- Exact Cassette Window Coordinates (based on your red marking) ---
TAPE_X1 = 305
TAPE_Y1 = 130
TAPE_X2 = 960
TAPE_Y2 = 480

# Neon color of the tape stroke
NEON_COLOR = (255, 40, 220)


def resize_to_fit(w, h, img):
    return img.resize((w, h), Image.LANCZOS)


def add_neon_border(img, border_size=8, color=(255, 40, 220)):
    """Add neon glowing border around the thumbnail."""
    w, h = img.size
    new_img = Image.new("RGBA", (w + border_size * 2, h + border_size * 2), (0, 0, 0, 0))

    draw = ImageDraw.Draw(new_img)

    # Outer border
    draw.rectangle(
        [0, 0, w + border_size * 2, h + border_size * 2],
        outline=color,
        width=border_size
    )

    # Glow
    glow = new_img.filter(ImageFilter.GaussianBlur(20))
    new_img.alpha_composite(glow)

    # Paste original inside
    new_img.paste(img, (border_size, border_size))

    return new_img


def truncate(text):
    words = text.split(" ")
    t1, t2 = "", ""
    for w in words:
        if len(t1) + len(w) < 30:
            t1 += " " + w
        elif len(t2) + len(w) < 30:
            t2 += " " + w
    return [t1.strip(), t2.strip()]


async def gen_thumb(videoid: str):
    try:
        if os.path.isfile(f"cache/{videoid}_v7.png"):
            return f"cache/{videoid}_v7.png"

        url = f"https://www.youtube.com/watch?v={videoid}"
        results = VideosSearch(url, limit=1)
        result = (await results.next())["result"][0]

        title = result.get("title", "Unsupported Title")
        title = re.sub("\W+", " ", title).title()

        duration = result.get("duration") or "Live"
        thumbnail = result["thumbnails"][0]["url"].split("?")[0]

        views = result.get("viewCount", {}).get("short", "Unknown Views")
        channel = result.get("channel", {}).get("name", "Unknown Channel")

        # --- Download thumbnail ---
        filepath = f"cache/thumb{videoid}.png"
        async with aiohttp.ClientSession() as session:
            async with session.get(thumbnail) as resp:
                data = await resp.read()
        async with aiofiles.open(filepath, "wb") as f:
            await f.write(data)

        youtube_thumb = Image.open(filepath).convert("RGBA")

        # --- Load Template ---
        template = Image.open("RocksMusic/assets/neon_tape.png").convert("RGBA")

        # --- Prepare Thumbnail ---
        tape_w = TAPE_X2 - TAPE_X1
        tape_h = TAPE_Y2 - TAPE_Y1

        resized_thumb = resize_to_fit(tape_w, tape_h, youtube_thumb)
        bordered_thumb = add_neon_border(resized_thumb, border_size=12, color=NEON_COLOR)

        # Paste thumbnail inside the cassette window
        template.paste(bordered_thumb, (TAPE_X1 - 12, TAPE_Y1 - 12), bordered_thumb)

        draw = ImageDraw.Draw(template)

        # --- Fonts ---
        arial = ImageFont.truetype("RocksMusic/assets/font2.ttf", 30)
        main_font = ImageFont.truetype("RocksMusic/assets/font3.ttf", 45)

        # --- Title / Channel ---
        TITLE_X = 80
        TITLE_Y = 620

        t1, t2 = truncate(title)
        draw.text((TITLE_X, TITLE_Y), t1, font=main_font, fill="white")
        draw.text((TITLE_X, TITLE_Y + 55), t2, font=main_font, fill="white")

        draw.text((TITLE_X, TITLE_Y + 120), f"{channel}  |  {views}", font=arial, fill="white")

        # --- Progress Bar ---
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

        # --- Play Icons ---
        play_icons = Image.open("RocksMusic/assets/play_icons.png").convert("RGBA")
        play_icons = play_icons.resize((580, 62))
        template.paste(play_icons, (450, 760), play_icons)

        # --- Save ---
        os.remove(filepath)
        final_path = f"cache/{videoid}_v7.png"
        template.save(final_path)

        return final_path

    except Exception as e:
        logging.error(f"Error generating thumbnail v7: {e}")
        traceback.print_exc()
        return None
