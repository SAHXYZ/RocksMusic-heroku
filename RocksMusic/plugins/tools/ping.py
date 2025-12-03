from datetime import datetime

from pyrogram import filters
from pyrogram.types import Message

from RocksMusic import app
from RocksMusic.core.call import Rocks
from RocksMusic.utils import bot_sys_stats
from RocksMusic.utils.decorators.language import language
from RocksMusic.utils.inline import supp_markup
from config import BANNED_USERS, PING_IMG_URL


@app.on_message(filters.command(["ping", "alive"]) & ~BANNED_USERS)
@language
async def ping_com(client, message: Message, _):
    start = datetime.now()

    # Send VIDEO instead of PHOTO
    response = await message.reply_video(
        video=PING_IMG_URL,
        caption=_["ping_1"].format(app.mention),
    )

    pytgping = await Rocks.ping()
    UP, CPU, RAM, DISK = await bot_sys_stats()
    resp = (datetime.now() - start).microseconds / 1000

    # Edit caption instead of text (since it's a video)
    await response.edit_caption(
        _["ping_2"].format(resp, app.mention, UP, RAM, CPU, DISK, pytgping),
        reply_markup=supp_markup(_),
    )
