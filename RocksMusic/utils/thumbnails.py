# ATLEAST GIVE CREDITS IF YOU STEALING :(((((((((((((((((((((((((((((((((((((
# ELSE NO FURTHER PUBLIC THUMBNAIL UPDATES

import logging
import traceback

logging.basicConfig(level=logging.INFO)

# No coordinates, no border, no thumbnail insertion.
# Clean final version.


async def gen_thumb(videoid: str):
    """
    FINAL VERSION (v10)
    Always returns the neon_tape.png image exactly as it is.
    No downloads, no text, no YouTube thumbnail, no drawing.
    """
    try:
        # Directly return your neon tape image
        return "RocksMusic/assets/neon_tape.png"

    except Exception as e:
        logging.error(f"Error in v10: {e}")
        traceback.print_exc()
        return "RocksMusic/assets/neon_tape.png"
