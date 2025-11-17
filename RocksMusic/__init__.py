from RocksMusic.core.bot import Rocks
from RocksMusic.core.dir import dirr
from RocksMusic.core.git import git
from RocksMusic.core.userbot import Userbot
from RocksMusic.misc import dbb, heroku

from .logging import LOGGER

dirr()
git()
dbb()
heroku()

app = Rocks()
userbot = Userbot()


from .platforms import *

Apple = AppleAPI()
Carbon = CarbonAPI()
SoundCloud = SoundAPI()
Spotify = SpotifyAPI()
Resso = RessoAPI()
Telegram = TeleAPI()
YouTube = YouTubeAPI()
