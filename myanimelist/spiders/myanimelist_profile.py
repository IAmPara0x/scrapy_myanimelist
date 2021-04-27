import scrapy
import numpy as np
from myanimelist.items import ProfileItem
import json


class MyanimelistProfileSpider(scrapy.Spider):
  name = 'myanimelist_profile'
  allowed_domains = ['myanimelist.net']
  custom_settings = {
  'ROTATING_PROXY_LIST_PATH' : 'proxy-list.txt',
  'CONCURRENT_REQUESTS' : 32,
  'ROTATING_PROXY_BACKOFF_BASE' : 60,
  'DOWNLOADER_MIDDLEWARES' : {
      'scrapy.downloadermiddlewares.useragent.UserAgentMiddleware': None,
      'scrapy_user_agents.middlewares.RandomUserAgentMiddleware': 400,
      'rotating_proxies.middlewares.RotatingProxyMiddleware': 610,
      'rotating_proxies.middlewares.BanDetectionMiddleware': 620,
    }
  }

  def __init__(self, max_depth='', **kwargs):
    self.max_depth = int(max_depth)
    self.current_depth = 0
    super().__init__(**kwargs)

  def start_requests(self):
    yield scrapy.Request("https://myanimelist.net/profile/Akagi-han/", callback=self.parse_profile)


  def parse_profile_friends(self, response):
    current_offset = int(response.url.split("=")[1])

    t_frnds = int(response.css("div.user-profile h4 a::text").get().split("(")[1].split(")")[0])

    frnds_prof = list(set(response.css("div.friendHolder div.friendBlock div a::attr(href)").extract()))

    for frnd_prof in frnds_prof:
      yield scrapy.Request(frnd_prof, callback=self.parse_profile)

    next_offset = (current_offset + 100)
    if next_offset < t_frnds:
      yield scrapy.Request((response.url.split("=")[0]+"="+str(next_offset)))


  def parse_profile(self, response):
    try:
      attr = {}
      attr["link"] = response.url
      attr["profile"] = response.url.split("/")[-1]
      url_favorites = response.css(
          "ul.favorites-list.anime li div.data a ::attr(href)"
      ).extract()
      attr["favorites"] = [self._extract_anime_uid(url) for url in url_favorites]

      user_status = response.css(
          "div.user-profile ul.user-status li.clearfix ::text"
      ).extract()
      user_status = self._list2dict(user_status)

      attr["gender"] = user_status["Gender"] if "Gender" in user_status else ""
      attr["birthday"] = (
          user_status["Birthday"] if "Birthday" in user_status else ""
      )

      if attr["profile"] in PROFILE_NAMES:
        return None

      PROFILE_NAMES[attr["profile"]] = 1

      yield scrapy.Request(
        (
          "https://myanimelist.net/animelist/"
          + attr["profile"]
          + "/load.json?status=1"
        ),
        self.parse_profile_currently_watching_anime,
        meta={"attr": attr},
      )

      yield scrapy.Request((response.url + "/" + "friends?offset=0"), callback=self.parse_profile_friends)
    except Exception as e:
      yield scrapy.Request(response.url, callback=self.parse_profile, dont_filter=True)

  # https://myanimelist.net/animelist/USERNAME/load.json?status=1 to get the JSON DATA of CURRENTLY WATCHING anime
  def parse_profile_currently_watching_anime(self, response):
    """
    get json data of currently watching anime.
    """
    attr = response.meta["attr"]
    try:
      attr["watching"] = json.loads(response.body.decode("utf-8"))

      yield scrapy.Request(
        (
          "https://myanimelist.net/animelist/"
          + attr["profile"]
          + "/load.json?status=2"
        ),
        self.parse_profile_completed_anime,
        meta={"attr": attr},
      )
    except Exception as e:
      yield scrapy.Request(
        response.url,
        self.parse_profile_currently_watching_anime,
        meta={"attr": attr}, dont_filter=True
      )

  # https://myanimelist.net/animelist/USERNAME/load.json?status=2 to get the JSON DATA of COMPLETED anime
  def parse_profile_completed_anime(self, response):
    """
    get json data of completed anime.
    """

    attr = response.meta["attr"]
    try:
      attr["completed"] = json.loads(response.body.decode("utf-8"))
      yield scrapy.Request(
        (
          "https://myanimelist.net/animelist/"
          + attr["profile"]
          + "/load.json?status=3"
        ),
        self.parse_profile_on_hold_anime,
        meta={"attr": attr},
      )
    except Exception as e:
      yield scrapy.Request(response.url, callback=self.parse_profile_completed_anime, meta={"attr": attr},)


  # https://myanimelist.net/animelist/USERNAME/load.json?status=3 to get the JSON DATA of ON HOLD anime
  def parse_profile_on_hold_anime(self, response):
    """
    get json data of on hold anime.
    """
    attr = response.meta["attr"]
    try:
      attr["on_hold"] = json.loads(response.body.decode("utf-8"))
      yield scrapy.Request(
        (
          "https://myanimelist.net/animelist/"
          + attr["profile"]
          + "/load.json?status=4"
        ),
        self.parse_profile_dropped_anime,
        meta={"attr": attr},
      )
    except Exception as e:
      yield scrapy.Request(response.url, callback=self.parse_profile_on_hold_anime,
          meta={"attr":attr}, dont_filter=True)


  # https://myanimelist.net/animelist/USERNAME/load.json?status=4 to get the JSON DATA of DROPPED anime
  def parse_profile_dropped_anime(self, response):
    """
    get json data of dropped anime.
    """
    attr = response.meta["attr"]
    try:
      attr["dropped"] = json.loads(response.body.decode("utf-8"))
      print(ProfileItem)
      yield ProfileItem(**attr)
    except Exception as e:
      yield scrapy.Request(response.url, callback=self.parse_profile_dropped_anime,
        meta={"attr":attr}, dont_filter=True)