import datetime

import aiohttp

from ...box import box
from ...event import Message
from ...utils import json


@box.command('퐁당')
async def pongdang(bot, event: Message):
    """
    한강 수온 조회

    현재 한강 수온을 조회합니다.

    `{PREFIX}퐁당` (현재 한강 수온 출력)

    """

    url = 'http://hangang.dkserver.wo.tc/'

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            data = json.loads(await resp.text())

    observed_at = datetime.datetime.strptime(data['time'], '%Y-%m-%d %H:%M:%S')
    temperature = float(data['temp'])

    await bot.say(
        event.channel,
        '{} 기준 한강 수온은 {}°C에요!'.format(
            observed_at.strftime('%Y년 %m월 %d일 %H시 %M분'),
            temperature,
        )
    )
