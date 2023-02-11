from bilibili_api import video_tag

tag = video_tag.Tag(tag_name="真白花音")

async def test_a_get_tag_info():
    return await tag.get_tag_info()


async def test_b_get_similar_tags():
    return await tag.get_similar_tags()


async def test_c_get_cards():
    return await tag.get_cards()

async def test_d_subscribe_tag():
    return await tag.subscribe_tag()

async def test_e_unsubscribe_tag():
    return await tag.unsubscribe_tag()

async def after_all():
    await tag.subscribe_tag()
