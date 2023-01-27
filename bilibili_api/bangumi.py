"""
bilibili_api.bangumi

番剧相关

概念：
+ media_id: 番剧本身的 ID，有时候也是每季度的 ID，如 https://www.bilibili.com/bangumi/media/md28231846/
+ season_id: 每季度的 ID
+ episode_id: 每集的 ID，如 https://www.bilibili.com/bangumi/play/ep374717

"""

import datetime
from enum import Enum
from typing import Any, Tuple, Union, List
import httpx

import requests

from bilibili_api.utils.Danmaku import Danmaku

from . import settings

from .utils.utils import get_api
from .utils.Credential import Credential
from .utils.network_httpx import get_session, request
from .exceptions.ResponseException import ResponseException
from .exceptions.ApiException import ApiException
from .video import Video

import json
import re

API = get_api("bangumi")


episode_data_cache = {}


class BangumiCommentOrder(Enum):
    """
    短评 / 长评 排序方式

    + DEFAULT: 默认
    + CTIME: 发布时间倒序
    """

    DEFAULT = 0
    CTIME = 1


class BangumiType(Enum):
    """
    番剧类型

    + BANGUMI: 番剧
    + FT: 影视
    + GUOCHUANG: 国创
    """
    BANGUMI = 1
    FT = 3
    GUOCHUANG = 4


async def get_timeline(type_: BangumiType, before: int = 7, after: int = 0) -> dict:
    """
    获取番剧时间线

    Args:
        type_(BangumiType): 番剧类型
        before(int)       : 几天前开始(0~7), defaults to 7
        after(int)        : 几天后结束(0~7), defaults to 0
    """
    api = API["info"]["timeline"]
    params = {
        "types": type_.value,
        "before": before,
        "after": after
    }
    return await request("GET", api["url"], params=params)


class Index_Filter:
    """
    番剧索引相关固定参数以及值
    """
    class Type(Enum):
        """
        索引类型
        """
        ANIME = 1
        MOVIE = 2
        DOCUMENTARY = 3
        GUOCHUANG = 4
        TV = 5

    class Version(Enum):
        """
        番剧版本
        """
        ALL = -1
        MAIN = 1
        FILM = 2
        OTHER = 3

    class Spoken_Language(Enum):
        """
        配音
        """
        ALL = -1
        ORIGINAL = 1
        CHINESE = 2

    class Finish_Status(Enum):
        """
        完结状态
        """
        ALL = -1
        FINISHED = 1
        UNFINISHED = 0

    class Copyright(Enum):
        """
        版权方
        """
        ALL = -1
        EXCLUSIVE = 3
        OTHER = "1,2,4"

    class Season(Enum):
        """
        季度
        """
        ALL = -1
        SUMMER = 7
        AUTUMN = 10
        WINTER = 1
        SPRING = 4

    @staticmethod
    def make_time_filter(
        start: Union[datetime.datetime, str, int] = None,
        end: Union[datetime.datetime, str, int] = None,
        include_start: bool = True,
        include_end: bool = False
    ) -> str:
        """
        生成番剧索引所需的时间条件
        番剧、国创直接传入年份
        影视、纪录片、电视剧传入 datetime.datetime
        Args:
            start (datetime, str, int): 开始时间. 如果是 None 则不设置开头.
            end   (datetime, str, int): 结束时间. 如果是 None 则不设置结尾.
            include_start (bool): 是否包含开始时间. 默认为 True.
            include_end   (bool): 是否包含结束时间. 默认为 False.

        Returns:
            str: 年代条件
        """
        start_str = ""
        end_str = ""

        if start != None:
            if isinstance(start, datetime.datetime):
                start_str = start.strftime("%Y-%m-%d %H:%M:%S")
            else:
                start_str = start
        if end != None:
            if isinstance(end, datetime.datetime):
                end_str = end.strftime("%Y-%m-%d %H:%M:%S")
            else:
                end_str = end

        # 是否包含边界
        if include_start:
            start_str = f"[{start_str}"
        else:
            start_str = f"({start_str}"
        if include_end:
            end_str = f"{end_str}]"
        else:
            end_str = f"{end_str})"

        return f"{start_str},{end_str}"

    class Producer(Enum):
        """
        制作方
        """
        ALL = -1
        CCTV = 4
        BBC = 1
        DISCOVERY = 7
        NATIONAL_GEOGRAPHIC = 14
        NHK = 2
        HISTORY = 6
        SATELLITE = 8
        SELF = 9
        ITV = 5
        SKY = 3
        ZDF = 10
        PARTNER = 11
        DOMESTIC_OTHER = 12
        FOREIGN_OTHER = 13

    class Payment(Enum):
        """
        观看条件
        """
        ALL = -1
        FREE = 1
        PAID = "2,6"
        VIP = "4,6"

    class Area(Enum):
        """
        地区
        """
        ALL = "-1"
        CHINA = "1,6,7"
        CHINA_MAINLAND = "1"
        CHINA_HONGKONG_AND_TAIWAN = "6,7"
        JAPAN = "2"
        USA = "3"
        UK = "4"
        SOUTH_KOREA = "8"
        FRANCE = "9"
        THAILAND = "10"
        GERMANY = "15"
        ITALY = "35"
        SPAIN = "13"

        # 各索引的其他地区都不同，不单开枚举类了
        ANIME_OTHER = "1,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50,51,52,53,54,55,56,57,58,59,60,61,62,63,64,65,66,67,68,69,70"
        TV_OTHER = "5,8,9,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50,51,52,53,54,55,56,57,58,59,60,61,62,63,64,65,66,67,68,69,70"
        MOVIE_OTHER = "5,11,12,14,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50,51,52,53,54,55,56,57,58,59,60,61,62,63,64,65,66,67,68,69,70"

    class Style:
        """
        风格
        """
        class Anime(Enum):
            """
            番剧
            """
            ALL = -1
            ORIGINAL = 10010
            COMIC = 10011
            NOVEL = 10012
            GAME = 10013
            TOKUSATSU = 10102
            BUDAIXI = 10015
            WARM = 10016
            TIMEBACK = 10017
            IMAGING = 10018
            WAR = 10020
            FUNNY = 10021
            DAILY = 10022
            SCIENCE_FICTION = 10023
            MOE = 10024
            HEAL = 10025
            SCHOOL = 10026
            CHILDREN = 10027
            NOODLES = 10028
            LOVE = 10029
            GIRLISH = 10030
            MAGIC = 10031
            DISCOVER = 10032
            HISTORY = 10033
            ALTERNATE = 10034
            MACHINE_BATTLE = 10035
            GODS_DEMONS = 10036
            VOICE = 10037
            SPORTS = 10038
            INSPIRATIONAL = 10039
            MUSIC = 10040
            ILLATION = 10041
            SOCIETIES = 10042
            OUTWIT = 10043
            TEAR = 10044
            FOODS = 10045
            IDOL = 10046
            OTOME = 10047
            WORK = 10048

        class Movie(Enum):
            """
            电影
            """
            ALL = -1
            SKETCH = 10104
            PLOT = 10050
            COMEDY = 10051
            ROMANTIC = 10052
            ACTION = 10053
            SCAIRIER = 10054
            SCIENCE_FICTION = 10023
            CRIME = 10055
            TIRILLER = 10056
            SUSPENSE = 10057
            IMAGING = 10018
            WAR = 10058
            ANIME = 10059
            BIOAGRAPHY = 10060
            FAMILY = 10061
            SING_DANCE = 10062
            HISTORY = 10033
            DISCOVER = 10032
            DOCUMENTARY = 10063
            DISATER = 10064
            COMIC = 10011
            MOVEL = 10012

        class GuoChuang(Enum):
            """
            国创
            """
            ALL = -1
            ORIGINAL = 10010
            COMIC = 10011
            NOVEL = 10012
            GAME = 10013
            DYNAMIC = 10014
            BUDAIXI = 10015
            WARM = 10016
            IMAGING = 10018
            FANTASY = 10019
            WAR = 10020
            FUNNY = 10021
            WUXIA = 10078
            DAILY = 10022
            SCIENCE_FICTION = 10023
            MOE = 10024
            HEAL = 10025
            SUSPENSE = 10057
            SCHOOL = 10026
            CHILDREN = 10027
            NOODLES = 10028
            LOVE = 10029
            GIRLISH = 10030
            MAGIC = 10031
            HISTORY = 10033
            MACHINE_BATTLE = 10035
            GODS_DEMONS = 10036
            VOICE = 10037
            SPORTS = 10038
            INSPIRATIONAL = 10039
            MUSIC = 10040
            ILLATION = 10041
            SOCIETIES = 10042
            OUTWIT = 10043
            TEAR = 10044
            FOODS = 10045
            IDOL = 10046
            OTOME = 10047
            WORK = 10048
            ANCIENT = 10049

        class TV(Enum):
            """
            电视剧
            """
            ALL = -1
            FUNNY = 10021
            IMAGING = 10018
            WAR = 10058
            WUXIA = 10078
            YOUTH = 10079
            SKETCH = 10103
            CITY = 10080
            COSTUME = 10081
            SPY = 10082
            CLASSIC = 10083
            EMOTION = 10084
            SUSPENSE = 10057
            INSPIRATIONAL = 10039
            MYTH = 10085
            TIMEBACK = 10017
            YEAR = 10086
            COUNTRYSIDE = 10087
            INVESTIGATION = 10088
            PLOT = 10050
            FAMILY = 10061
            HISTORY = 10033
            ARMY = 10089

        class Documentary(Enum):
            """
            纪录片
            """
            ALL = -1
            HISTORY = 10033
            FOODS = 10045
            HUMANITIES = 10065
            TECHNOLOGY = 10066
            DISCOVER = 10067
            UNIVERSE = 10068
            PETS = 10069
            SOCIAL = 10070
            ANIMALS = 10071
            NATURE = 10072
            MEDICAL = 10073
            WAR = 10074
            DISATER = 10064
            INVESTIGATIONS = 10075
            MYSTERIOUS = 10076
            TRAVEL = 10077
            SPORTS = 10038
            MOVIES = -10

    class Sort(Enum):
        """
        排序方式
        """
        DESC = "0"
        ASC = "1"

    class Order(Enum):
        """
        排序字段
        更新时间 0
        弹幕数量 1
        播放数量 2
        追番人数 3
        最高评分 4
        番剧开播日期 5
        电影上映日期 6
        """
        UPDATE = "0"
        DANMAKU = "1"
        PLAY = "2"
        FOLLOWER = "3"
        SCORE = "4"
        ANIME_RELEASE = "5"
        MOVIE_RELEASE = "6"


class Index_Filter_Meta:
    """
    Index Filter 元数据
    用于传入 get_index_info 方法
    """
    class Anime:
        def __init__(self,
                     version: Index_Filter.Version = Index_Filter.Version.ALL,
                     spoken_language: Index_Filter.Spoken_Language = Index_Filter.Spoken_Language.ALL,
                     area: Index_Filter.Area = Index_Filter.Area.ALL,
                     finish_status: Index_Filter.Finish_Status = Index_Filter.Finish_Status.ALL,
                     copyright: Index_Filter.Copyright = Index_Filter.Copyright.ALL,
                     payment: Index_Filter.Payment = Index_Filter.Payment.ALL,
                     season: Index_Filter.Season = Index_Filter.Season.ALL,
                     year: str = -1,
                     style: Index_Filter.Style.Anime = Index_Filter.Style.Anime.ALL
                     ) -> None:
            """
            Anime Meta
            Args:
                version (Index_Filter.Version): 类型，如正片、电影等
                spoken_language (Index_Filter.Spoken_Language): 配音
                area (Index_Filter.Area): 地区
                finish_status (Index_Filter.Finish_Status): 是否完结
                copyright (Index_Filter.Copryright): 版权
                payment (Index_Filter.Payment): 付费门槛
                season (Index_Filter.Season): 季度
                year (str): 年份，调用 Index_Filter.make_time_filter() 传入年份 (int, str) 获取
                style (Index_Filter.Style.Anime): 风格
            """
            self.season_type = Index_Filter.Type.ANIME
            self.season_version = version
            self.spoken_language_type = spoken_language
            self.area = area
            self.is_finish = finish_status
            self.copyright = copyright
            self.season_status = payment
            self.season_month = season
            self.year = year
            self.style_id = style

    class Movie:
        def __init__(self,
                     area: Index_Filter.Area = Index_Filter.Area.ALL,
                     release_date: str = -1,
                     style: Index_Filter.Style.Movie = Index_Filter.Style.Movie.ALL,
                     payment: Index_Filter.Payment = Index_Filter.Payment.ALL
                     ) -> None:
            """
            Movie Meta
            Args:
                area (Index_Filter.Area): 地区
                payment (Index_Filter.Payment): 付费门槛
                season (Index_Filter.Season): 季度
                release_date (str): 上映时间，调用 Index_Filter.make_time_filter() 传入年份 (datetime.datetime) 获取
                style (Index_Filter.Style.Movie): 风格
            """
            self.season_type = Index_Filter.Type.MOVIE
            self.area = area
            self.release_date = release_date
            self.style_id = style
            self.season_status = payment

    class Documentary:
        def __init__(self,
                     release_date: str = -1,
                     style: Index_Filter.Style.Documentary = Index_Filter.Style.Documentary.ALL,
                     payment: Index_Filter.Payment = Index_Filter.Payment.ALL,
                     producer: Index_Filter.Producer = Index_Filter.Producer.ALL
                     ) -> None:
            """
            Documentary Meta
            Args:
                area (Index_Filter.Area): 地区
                release_date (str): 上映时间，调用 Index_Filter.make_time_filter() 传入年份 (datetime.datetime) 获取
                style (Index_Filter.Style.Documentary): 风格
                producer (Index_Filter.Producer): 制作方
            """
            self.season_type = Index_Filter.Type.DOCUMENTARY
            self.release_date = release_date
            self.style_id = style
            self.season_status = payment
            self.producer_id = producer

    class TV:
        def __init__(self,
                     area: Index_Filter.Area = Index_Filter.Area.ALL,
                     release_date: str = -1,
                     style: Index_Filter.Style.TV = Index_Filter.Style.TV.ALL,
                     payment: Index_Filter.Payment = Index_Filter.Payment.ALL
                     ) -> None:
            """
            TV Meta
            Args:
                area (Index_Filter.Area): 地区
                payment (Index_Filter.Payment): 付费门槛
                release_date (str): 上映时间，调用 Index_Filter.make_time_filter() 传入年份 (datetime.datetime) 获取
                style (Index_Filter.Style.TV): 风格
            """
            self.season_type = Index_Filter.Type.TV
            self.area = area
            self.release_date = release_date
            self.style_id = style
            self.season_status = payment

    class GuoChuang:
        def __init__(self,
                     version: Index_Filter.Version = Index_Filter.Version.ALL,
                     finish_status: Index_Filter.Finish_Status = Index_Filter.Finish_Status.ALL,
                     copyright: Index_Filter.Copyright = Index_Filter.Copyright.ALL,
                     payment: Index_Filter.Payment = Index_Filter.Payment.ALL,
                     year: str = -1,
                     style: Index_Filter.Style.GuoChuang = Index_Filter.Style.GuoChuang.ALL
                     ) -> None:
            """
            Guochuang Meta
            Args:
                version (Index_Filter.VERSION): 类型，如正片、电影等
                finish_status (Index_Filter.Finish_Status): 是否完结
                copyright (Index_Filter.Copyright): 版权
                payment (Index_Filter.Payment): 付费门槛
                year (str): 年份，调用 Index_Filter.make_time_filter() 传入年份 (int, str) 获取
                style (Index_Filter.Style.GuoChuang): 风格
            """
            self.season_type = Index_Filter.Type.GUOCHUANG
            self.season_version = version
            self.is_finish = finish_status
            self.copyright = copyright
            self.season_status = payment
            self.year = year
            self.style_id = style


async def get_index_info(filters: Index_Filter_Meta = Index_Filter_Meta.Anime(),
                               order: Index_Filter.Order = Index_Filter.Order.SCORE,
                               sort: Index_Filter.Sort = Index_Filter.Sort.DESC,
                               pn: int = 1,
                               ps: int = 20,
                               ) -> dict:
    """
    查询番剧索引，索引的详细参数信息见 Index_Filter_Meta
    请先通过 Index_Filter_Meta 构造 filters

    Args:
        filters (Index_Filter_Meta, optional): 筛选条件元数据. Defaults to Anime.
        order (BANGUMI_INDEX.ORDER, optional): 排序字段. Defaults to SCORE.
        sort (BANGUMI_INDEX.SORT, optional): 排序方式. Defaults to DESC.
        pn (int, optional): 页数. Defaults to 1.
        ps (int, optional): 每页数量. Defaults to 20.

    Returns:
        dict: 调用 API 返回的结果
    """
    api = API["info"]["index"]
    params = {}

    for key, value in filters.__dict__.items():
        if value is not None:
            if isinstance(value, Enum):
                params[key] = value.value
            else:
                params[key] = value

    if order in params:
        if order == Index_Filter.Order.SCORE.value and sort == Index_Filter.Sort.ASC.value:
            raise ValueError(
                "order 为 Index_Filter.ORDER.SCORE 时，sort 不能为 Index_Filter.SORT.ASC")
    
    # 必要参数 season_type、type
    # 常规参数
    params["order"] = order.value
    params["sort"] = sort.value
    params["page"] = pn
    params["pagesize"] = ps

    # params["st"] 未知参数，暂时不传
    # params["type"] 未知参数，为 1
    params["type"] = 1

    return await request("GET", api["url"], params=params)


class Bangumi:
    """
    番剧类

    Attributes:
        credential (Credential): 凭据类
    """

    def __init__(
        self,
        media_id: int = -1,
        ssid: int = -1,
        epid: int = -1,
        oversea: bool = False,
        credential: Union[Credential, None] = None,
    ) -> None:
        """
        Args:
            media_id   (int, optional)              : 番剧本身的 ID. Defaults to -1.
            ssid       (int, optional)              : 每季度的 ID. Defaults to -1.
            epid       (int, optional)              : 每集的 ID. Defaults to -1.
            oversea    (bool, optional)             : 是否要采用兼容的港澳台Api,用于仅限港澳台地区番剧的信息请求. Defaults to False.
            credential (Credential | None, optional): 凭据类. Defaults to None.
        """
        if media_id == -1 and ssid == -1 and epid == -1:
            raise ValueError("需要 Media_id 或 Season_id 或 epid 中的一个 !")
        self.credential = credential if credential else Credential()
        # 处理极端情况
        params = {}
        self.__ssid = ssid
        if self.__ssid == -1 and epid == -1:
            api = API["info"]["meta"]
            params = {"media_id": media_id}
            meta = requests.get(
                url=api["url"], params=params, cookies=self.credential.get_cookies()
            )
            meta.raise_for_status()
            # print(meta.json())
            self.__ssid = meta.json()["result"]["media"]["season_id"]
            params["media_id"] = media_id
        # 处理正常情况
        if self.__ssid != -1:
            params["season_id"] = self.__ssid
        if epid != -1:
            params["ep_id"] = epid
        self.oversea = oversea
        if oversea:
            api = API["info"]["collective_info_oversea"]
        else:
            api = API["info"]["collective_info"]
        req = requests.get(
            url=api["url"], params=params, cookies=self.credential.get_cookies()
        )
        req.raise_for_status()
        self.__raw = req.json()
        self.__epid = epid
        if not self.__raw.get("result"):
            raise ApiException("Api没有返回预期的结果")
        # 确认有结果后，取出数据
        self.__ssid = req.json()["result"]["season_id"]
        self.__media_id = req.json()["result"]["media_id"]
        if "up_info" in req.json()["result"]:
            self.__up_info = req.json()["result"]["up_info"]
        else:
            self.__up_info = {}
        # 获取剧集相关
        self.ep_list = req.json()["result"].get("episodes")
        self.ep_item = [{}]
        # 出海 Api 和国内的字段有些不同
        if self.ep_list:
            if self.oversea:
                self.ep_item = [
                    item for item in self.ep_list if item["ep_id"] == self.__epid
                ]
            else:
                self.ep_item = [
                    item for item in self.ep_list if item["id"] == self.__epid
                ]

    def get_media_id(self) -> int:
        return self.__media_id

    def get_season_id(self) -> int:
        return self.__ssid

    def get_up_info(self) -> dict:
        """
        番剧上传者信息 出差或者原版

        Returns:
            Api 相关字段
        """
        return self.__up_info

    def get_raw(self) -> Tuple[dict, bool]:
        """
        原始初始化数据

        Returns:
            Api 相关字段
        """
        return self.__raw, self.oversea

    def set_media_id(self, media_id: int) -> None:
        self.__init__(media_id=media_id, credential=self.credential)

    def set_ssid(self, ssid: int) -> None:
        self.__init__(ssid=ssid, credential=self.credential)

    async def get_meta(self) -> dict:
        """
        获取番剧元数据信息（评分，封面 URL，标题等）

        Returns:
            dict: 调用 API 返回的结果
        """
        credential = self.credential if self.credential is not None else Credential()

        api = API["info"]["meta"]
        params = {"media_id": self.__media_id}
        return await request("GET", api["url"], params, credential=credential)

    async def get_short_comment_list(
        self, order: BangumiCommentOrder = BangumiCommentOrder.DEFAULT, next: Union[str, None] = None
    ) -> dict:
        """
        获取短评列表

        Args:
            order      (BangumiCommentOrder, optional): 排序方式。Defaults to BangumiCommentOrder.DEFAULT
            next       (str | None, optional)         : 调用返回结果中的 next 键值，用于获取下一页数据。Defaults to None

        Returns:
            dict: 调用 API 返回的结果
        """
        credential = self.credential if self.credential is not None else Credential()

        api = API["info"]["short_comment"]
        params = {"media_id": self.__media_id, "ps": 20, "sort": order.value}
        if next is not None:
            params["cursor"] = next

        return await request("GET", api["url"], params, credential=credential)

    async def get_long_comment_list(
        self, order: BangumiCommentOrder = BangumiCommentOrder.DEFAULT, next: Union[str, None] = None
    ) -> dict:
        """
        获取长评列表

        Args:
            order      (BangumiCommentOrder, optional): 排序方式。Defaults to BangumiCommentOrder.DEFAULT
            next       (str | None, optional)         : 调用返回结果中的 next 键值，用于获取下一页数据。Defaults to None

        Returns:
            dict: 调用 API 返回的结果
        """
        credential = self.credential if self.credential is not None else Credential()

        api = API["info"]["long_comment"]
        params = {"media_id": self.__media_id, "ps": 20, "sort": order.value}
        if next is not None:
            params["cursor"] = next

        return await request("GET", api["url"], params, credential=credential)

    async def get_episode_list(self) -> dict:
        """
        获取季度分集列表，自动转换出海Api的字段，适配部分，但是键还是有不同

        Returns:
            dict: 调用 API 返回的结果
        """
        if self.oversea:
            # 转换 ep_id->id ，index_title->longtitle ，index->title
            fix_ep_list = []
            for item in self.ep_list:
                item["id"] = item.get("ep_id")
                item["longtitle"] = item.get("index_title")
                item["title"] = item.get("index")
                fix_ep_list.append(item)
            return {"main_section": {"episodes": fix_ep_list}}
        else:
            credential = (
                self.credential if self.credential is not None else Credential()
            )
            api = API["info"]["episodes_list"]
            params = {"season_id": self.__ssid}
            return await request("GET", api["url"], params, credential=credential)

    async def get_episodes(self) -> List["Episode"]:
        """
        获取番剧所有的剧集，自动生成类。
        """
        global episode_data_cache
        episode_list = await self.get_episode_list()
        if len(episode_list["main_section"]["episodes"]) == 0:
            return []
        first_epid = episode_list["main_section"]["episodes"][0]["id"]

        async def get_episode_info(epid: int):
            credential = self.credential if self.credential else Credential()
            session = get_session()

            try:
                resp = await session.get(
                    f"https://www.bilibili.com/bangumi/play/ep{epid}",
                    cookies=credential.get_cookies(),
                    headers={"User-Agent": "Mozilla/5.0"},
                )
            except Exception as e:
                raise ResponseException(str(e))
            else:
                content = resp.text

                pattern = re.compile(r"window.__INITIAL_STATE__=(\{.*?\});")
                match = re.search(pattern, content)
                if match is None:
                    raise ApiException("未找到番剧信息")
                try:
                    content = json.loads(match.group(1))
                except json.JSONDecodeError:
                    raise ApiException("信息解析错误")

                return content
        bangumi_meta = await get_episode_info(first_epid)
        bangumi_meta["media_id"] = self.get_media_id()

        episodes = []
        for ep in episode_list["main_section"]["episodes"]:
            episode_data_cache[ep["id"]] = {
                "bangumi_meta": bangumi_meta,
                "bangumi_class": self,
            }
            episodes.append(Episode(
                epid=ep["id"],
                credential=self.credential
            ))
        return episodes

    async def get_stat(self) -> dict:
        """
        获取番剧播放量，追番等信息

        Returns:
            dict: 调用 API 返回的结果
        """
        credential = self.credential if self.credential is not None else Credential()

        api = API["info"]["season_status"]
        params = {"season_id": self.__ssid}
        return await request("GET", api["url"], params, credential=credential)

    async def get_overview(self) -> dict:
        """
        获取番剧全面概括信息，包括发布时间、剧集情况、stat 等情况

        Returns:
            dict: 调用 API 返回的结果
        """
        credential = self.credential if self.credential is not None else Credential()
        if self.oversea:
            api = API["info"]["collective_info_oversea"]
        else:
            api = API["info"]["collective_info"]
        params = {"season_id": self.__ssid}
        return await request("GET", api["url"], params, credential=credential)


async def set_follow(
    bangumi: Bangumi, status: bool = True, credential: Union[Credential, None] = None
) -> dict:
    """
    追番状态设置

    Args:
        bangumi    (Bangumi)                    : 番剧类
        status     (bool, optional)             : 追番状态. Defaults to True.
        credential (Credential | None, optional): 凭据. Defaults to None.

    Returns:
        dict: 调用 API 返回的结果
    """
    credential = credential if credential is not None else Credential()
    credential.raise_for_no_sessdata()

    api = API["operate"]["follow_add"] if status else API["operate"]["follow_del"]
    data = {"season_id": bangumi.get_season_id()}
    return await request("POST", api["url"], data=data, credential=credential)


async def update_follow_status(
    bangumi: Bangumi, status: int, credential: Union[Credential, None] = None
) -> dict:
    """
    更新追番状态

    Args:
        bangumi    (Bangumi)                    : 番剧类
        credential (Credential | None, optional): 凭据. Defaults to None.
        status     (int)                        : 追番状态 1 想看 2 在看 3 已看
    Returns:
        dict: 调用 API 返回的结果
    """
    credential = credential if credential is not None else Credential()
    credential.raise_for_no_sessdata()

    api = API["operate"]["follow_status"]
    data = {"season_id": bangumi.get_season_id(), "status": status}
    return await request("POST", api["url"], data=data, credential=credential)


class Episode(Video):
    """
    番剧剧集类

    Attributes:
        credential  (Credential): 凭据类
        video_class (Video)     : 视频类
        bangumi     (Bangumi)   : 所属番剧
    """

    def __init__(self, epid: int, credential: Union[Credential, None] = None):
        """
        Args:
            epid       (int)                 : 番剧 epid
            credential (Credential, optional): 凭据. Defaults to None.
        """
        global episode_data_cache
        self.credential = credential if credential else Credential()
        self.__epid = epid

        if not epid in episode_data_cache.keys():
            try:
                resp = httpx.get(
                    f"https://www.bilibili.com/bangumi/play/ep{self.__epid}",
                    cookies=self.credential.get_cookies(),
                    headers={"User-Agent": "Mozilla/5.0"},
                )
            except Exception as e:
                raise ResponseException(str(e))
            content = resp.text
            pattern = re.compile(r"window.__INITIAL_STATE__=(\{.*?\});")
            match = re.search(pattern, content)
            if match is None:
                raise ApiException("未找到番剧信息")
            try:
                content = json.loads(match.group(1))
            except json.JSONDecodeError:
                raise ApiException("信息解析错误")
        else:
            content = episode_data_cache[epid]["bangumi_meta"]

        bvid = content["epInfo"]["bvid"]
        if not epid in episode_data_cache.keys():
            self.bangumi = Bangumi(ssid=content["mediaInfo"]["season_id"])
        else:
            self.bangumi = episode_data_cache[epid]["bangumi_class"]

        self.video_class = Video(bvid=bvid, credential=self.credential)
        super().__init__(bvid=bvid)
        self.set_aid = self.set_aid_e
        self.set_bvid = self.set_bvid_e

    def get_epid(self) -> int:
        """
        获取 epid
        """
        return self.__epid

    def set_aid_e(self, aid: int) -> None:
        print("Set aid is not allowed in Episode")

    def set_bvid_e(self, bvid: str) -> None:
        print("Set bvid is not allowed in Episode")

    async def get_cid(self) -> int:
        """
        获取稿件 cid

        Returns:
            int: cid
        """
        return (await self.get_episode_info())["epInfo"]["cid"]

    def get_bangumi(self) -> "Bangumi":
        """
        获取对应的番剧

        Returns:
            Bangumi: 番剧类
        """
        return self.bangumi  # type: ignore

    def set_epid(self, epid: int) -> None:
        self.__init__(epid, self.credential)

    async def get_episode_info(self) -> dict:
        """
        获取番剧单集信息

        Returns:
            HTML 中的数据
        """
        credential = self.credential if self.credential else Credential()
        session = get_session()

        try:
            resp = await session.get(
                f"https://www.bilibili.com/bangumi/play/ep{self.__epid}",
                cookies=credential.get_cookies(),
                headers={"User-Agent": "Mozilla/5.0"},
            )
        except Exception as e:
            raise ResponseException(str(e))
        else:
            content = resp.text

            pattern = re.compile(r"window.__INITIAL_STATE__=(\{.*?\});")
            match = re.search(pattern, content)
            if match is None:
                raise ApiException("未找到番剧信息")
            try:
                content = json.loads(match.group(1))
            except json.JSONDecodeError:
                raise ApiException("信息解析错误")

            return content

    async def get_bangumi_from_episode(self) -> "Bangumi":
        """
        获取剧集对应的番剧

        Returns:
            Bangumi: 输入的集对应的番剧类
        """
        info = await self.get_episode_info()
        ssid = info["mediaInfo"]["season_id"]
        return Bangumi(ssid=ssid)

    async def get_download_url(self) -> dict:
        """
        获取番剧剧集下载信息。

        Returns:
            dict: 调用 API 返回的结果。
        """
        url = API["info"]["playurl"]["url"]
        if True:
            params = {
                "avid": self.get_aid(),
                "ep_id": self.get_epid(),
                "qn": "127",
                "otype": "json",
                "fnval": 4048,
                "fourk": 1,
            }
        return await request("GET", url, params=params, credential=self.credential)

    async def get_danmaku_xml(self) -> str:
        """
        获取所有弹幕的 xml 源文件（非装填）

        Returns:
            str: 文件源
        """
        cid = await self.get_cid()
        url = f"https://comment.bilibili.com/{cid}.xml"
        sess = get_session()
        config: dict[str, Any] = {"url": url}
        # 代理
        if settings.proxy:
            config["proxies"] = {"all://", settings.proxy}
        resp = await sess.get(**config)
        return resp.content.decode("utf-8")

    async def get_danmaku_view(self) -> dict:
        """
        获取弹幕设置、特殊弹幕、弹幕数量、弹幕分段等信息。

        Returns:
            dict: 二进制流解析结果
        """
        return await self.video_class.get_danmaku_view(0)

    async def get_danmakus(self, date: Union[datetime.date, None] = None) -> List["Danmaku"]:
        """
        获取弹幕

        Args:
            date (datetime.date | None, optional): 指定某一天查询弹幕. Defaults to None. (不指定某一天)

        Returns:
            dict[Danmaku]: 弹幕列表
        """
        return await self.video_class.get_danmakus(0, date)

    async def get_history_danmaku_index(self, date: Union[datetime.date, None] = None) -> Union[None, List[str]]:
        """
        获取特定月份存在历史弹幕的日期。

        Args:
            date (datetime.date | None, optional): 精确到年月. Defaults to None。

        Returns:
            None | List[str]: 调用 API 返回的结果。不存在时为 None。
        """
        return await self.video_class.get_history_danmaku_index(0, date)
