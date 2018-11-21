from typing import List, Optional, Tuple

from lxml.html import fromstring

from sqlalchemy.orm.exc import NoResultFound

from ..shared.cache import JSONCache
from ...api import Attachment, Field
from ...box import box
from ...session import client_session
from ...utils.datetime import now


def get_or_create_cache(name: str, sess) -> JSONCache:
    try:
        cache = sess.query(JSONCache).filter_by(name=name).one()
    except NoResultFound:
        cache = JSONCache()
        cache.name = name
    return cache


def process(
    html: str,
    first_page: Optional[List[str]],
) -> Tuple[List[Attachment], List[str]]:
    h = fromstring(html)
    items = h.cssselect('#search-result-container li.list__item')[::-1]
    attachments: List[Attachment] = []
    if first_page is None:
        first_page = []
    current = []
    for item in items:
        id = item.cssselect('input#commodityCode')[0].get('value').strip()
        current.append(id)
        if id in first_page:
            continue
        thumbnail_container = item.cssselect('.product_img')[0]
        title_link = (
            'https://ec.toranoana.shop' +
            thumbnail_container[0].get('href').strip()
        )
        image_url = thumbnail_container[0][0].get('src').strip()
        title = item.cssselect('.product_title')[0].text_content().strip()
        desc_els = item.cssselect('.product_desc p label')
        category = desc_els[0].text_content().strip()
        author_name = desc_els[1].text_content().strip()
        remain = desc_els[-1].text_content().strip()[-1]
        price = item.cssselect('.product_price')[0].text_content().strip()
        color = '3399ff'

        fields: List[Field] = [
            Field(
                title='호랑이굴',
                value='남성 성인',
                short=True,
            ),
            Field(
                title='카테고리',
                value=category,
                short=True,
            ),
            Field(
                title='가격',
                value=price,
                short=True,
            ),
            Field(
                title='재고',
                value=remain,
                short=True,
            ),
        ]
        attachments.append(Attachment(
            fallback=f'{title} - {title_link}',
            title=title,
            title_link=title_link,
            color=color,
            fields=fields,
            image_url=image_url,
            author_name=author_name,
        ))

    return attachments, current


@box.cron('4,24,44 * * * *')
async def watch(bot, sess):
    url = (
        'https://ec.toranoana.shop/tora/ec/cot/genre/GNRN00001186/all/all'
        '/?indexSummaryResultType=1&indexLocalCode=004a'
    )
    headers = {
        'Cookie': 'adflg=0',
    }
    async with client_session() as session:
        async with session.get(url, headers=headers) as resp:
            html = await resp.text()

    cache = get_or_create_cache('personal-tora-male-all', sess)
    attachments, cache.body = await bot.run_in_other_process(
        process,
        html,
        cache.body,
    )

    if attachments:
        cache.created_at = now()
        with sess.begin():
            sess.add(cache)

        await bot.api.chat.postMessage(
            channel=bot.config.OWNER_ID,
            as_user=True,
            text='토라노아나(남성/전연령)에 소드 아트 온라인 신간이 올라왔어요!',
            attachments=attachments,
        )
