# ATLEAST GIVE CREDITS IF YOU STEALING :(((((((((((((((((((((((((((((((((((((
# ELSE NO FURTHER PUBLIC THUMBNAIL UPDATES

import logging
import os
import re
import traceback
import aiofiles
import aiohttp
from PIL import Image, ImageDraw, ImageFilter
from youtubesearchpython.__future__ import VideosSearch

logging.basicConfig(level=logging.INFO)

# --- EXACT Reel area inside cassette (your final red marking) ---
REEL_X1 = 510
REEL_Y1 = 265
REEL_X2 = 765
REEL_Y2 = 360

# Neon tape border color
NEON_COLOR = (255, 40, 220)


def resize_exact(w, h, img):
    return img.resize((w, h), Image.LANCZOS)


def add_neon_border(img, border=4, color=NEON_COLOR):
    w, h = img.size
    canvas = Image.new("RGBA", (w + border * 2, h + border * 2), (0, 0, 0, 0))

    draw = ImageDraw.Draw(canvas)
    draw.rectangle(
        [0, 0, w + border * 2, h + border * 2],
        outline=color,
        width=border
    )

    glow = canvas.filter(ImageFilter.GaussianBlur(10))
    canvas.alpha_composite(glow, dest=(0, 0))

    canvas.paste(img, (border, border))
    return canvas


async def gen_thumb(videoid: str):
    try:
        if os.path.isfile(f"cache/{videoid}_v8.png"):
            return f"cache/{videoid}_v8.png"

        url = f"https://www.youtube.com/watch?v={videoid}"
        result = (await VideosSearch(url, limit=1).next())["result"][0]

        title = re.sub(r"\W+", " ", result.get("title", "Invalid Title"))
        thumbnail = result["thumbnails"][0]["url"].split("?")[0]

        # --- Download Thumbnail ---
        filepath = f"cache/thumb{videoid}.png"
        async with aiohttp.ClientSession() as session:
            async with session.get(thumbnail) as resp:
                imgdata = await resp.read()

        async with aiofiles.open(filepath, "wb") as f:
            await f.write(imgdata)

        yt_img = Image.open(filepath).convert("RGBA")

        # --- Load template (neon tape background) ---
        base = Image.open("RocksMusic/assets/neon_tape.png").convert("RGBA")

        # --- Insert thumbnail ONLY inside reel area ---
        reel_w = REEL_X2 - REEL_X1
        reel_h = REEL_Y2 - REEL_Y1

        resized = resize_exact(reel_w, reel_h, yt_img)
        bordered = add_neon_border(resized, border=3, color=NEON_COLOR)

        # Paste thumbnail inside cassette reel
        base.paste(bordered, (REEL_X1 - 3, REEL_Y1 - 3), bordered)

        # Save final image
        final_path = f"cache/{videoid}_v8.png"
        base.save(final_path)

        os.remove(filepath)
        return final_path

    except Exception as e:
        logging.error(f"Error in v8: {e}")
        traceback.print_exc()
        return None
