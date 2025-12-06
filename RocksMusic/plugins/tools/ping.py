from datetime import datetime

from pyrogram import filters
from pyrogram.types import Message

from RocksMusic import app
from RocksMusic.core.call import Rocks
from RocksMusic.utils import bot_sys_stats
from RocksMusic.utils.decorators.language import language
from RocksMusic.utils.inline import supp_markup
from config import BANNED_USERS


@app.on_message(filters.command(["ping", "alive"]) & ~BANNED_USERS)
@language
async def ping_com(client, message: Message, _):
    start = datetime.now()

    # Send Local Video (Assets)
    response = await message.reply_video(
        video="RocksMusic/assets/ping.mp4",
        caption=_["ping_1"].format(app.mention),
        supports_streaming=True
    )

    # Calculate bot stats
    ping_time = await Rocks.ping()
    UP, CPU, RAM, DISK = await bot_sys_stats()
    resp = (datetime.now() - start).microseconds / 1000

    # Edit caption after video loads
    await response.edit_caption(
        _["ping_2"].format(resp, app.mention, UP, RAM, CPU, DISK, ping_time),
        reply_markup=supp_markup(_),
    )
