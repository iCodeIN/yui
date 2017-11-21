import datetime

import aiohttp

from lxml import etree

import ujson

from ..box import box
from ..event import Message
from ..util import static_vars

COOLTIME = datetime.timedelta(minutes=15)


async def get_cat_image_url() -> str:
    api_url = 'http://thecatapi.com/api/images/get'
    async with aiohttp.ClientSession() as session:
        while True:
            async with session.get(api_url, params={
                'format': 'xml',
                'type': 'jpg,png',
            }) as res:
                xml_result = await res.read()
                tree = etree.fromstring(xml_result)
                url = tree.find('data/images/image/url').text
            async with session.get(url) as res:
                if res.status == 200:
                    return url


async def get_dog_image_url() -> str:
    api_url = 'https://dog.ceo/api/breeds/image/random'
    async with aiohttp.ClientSession() as session:
        while True:
            async with session.get(api_url) as res:
                data = await res.json(loads=ujson.loads)
                url = data['message']
            async with session.get(url) as res:
                if res.status == 200:
                    return url


@box.command('cat')
@static_vars(last_call=None)
async def cat(bot, event: Message, sess):
    """
    냥냥이 짤을 수급합니다.
    쿨타임은 15분입니다.

    `{PREFIX}cat`: 냐짤 수급

    """

    now = datetime.datetime.utcnow()
    if cat.last_call is not None and now - cat.last_call < COOLTIME:
        await bot.say(
            event.channel,
            '아직 쿨타임이다냥'
        )
        return

    cat.last_call = now

    url = await get_cat_image_url()
    await bot.say(
        event.channel,
        url
    )


@box.command('dog')
@static_vars(last_call=None)
async def dog(bot, event: Message, sess):
    """
    멍멍이 짤을 수급합니다.
    쿨타임은 15분입니다.

    `{PREFIX}dog`: 멍짤 수급

    """

    now = datetime.datetime.utcnow()
    if dog.last_call is not None and now - dog.last_call < COOLTIME:
        await bot.say(
            event.channel,
            '아직 쿨타임이다멍'
        )
        return

    dog.last_call = now

    url = await get_dog_image_url()
    await bot.say(
        event.channel,
        url
    )