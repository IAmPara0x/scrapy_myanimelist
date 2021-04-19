import scrapy
import numpy as np
from myanimelist.items import ProfileItem
import json


class MyanimelistProfileSpider(scrapy.Spider):
  name = 'myanimelist_profile'
  allowed_domains = ['myanimelist.net']
  custom_settings = {
  'DOWNLOAD_DELAY': 60/60,
  'ROTATING_PROXY_LIST_PATH' : 'proxy-list.txt',
  'DOWNLOADER_MIDDLEWARES' : {
      'scrapy.downloadermiddlewares.useragent.UserAgentMiddleware': None,
      'scrapy_user_agents.middlewares.RandomUserAgentMiddleware': 400,
      'scrapy.downloadermiddlewares.httpproxy.HttpProxyMiddleware': 1,
      'rotating_proxies.middlewares.RotatingProxyMiddleware': 610,
      'rotating_proxies.middlewares.BanDetectionMiddleware': 620,
    }
  }

  def __init__(self, max_depth='', **kwargs):
    self.max_depth = int(max_depth)
    self.current_depth = 0
    super().__init__(**kwargs)

  def start_requests(self):
    yield scrapy.Request("https://myanimelist.net/profile/Akagi-han/friends")

  def parse(self, response):
    # self.current_depth += 1
    yield scrapy.Request("")

  def parse_profile(self, response):
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
      yield scrapy.Request(
          (
              "https://myanimelist.net/animelist/"
              + attr["profile"]
              + "/load.json?status=1"
          ),
          self.parse_profile_currently_watching_anime,
          meta={"attr": attr},
      )

  # https://myanimelist.net/animelist/USERNAME/load.json?status=1 to get the JSON DATA of CURRENTLY WATCHING anime
  def parse_profile_currently_watching_anime(self, response):
      """
      get json data of currently watching anime.
      """
      attr = response.meta["attr"]
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

  # https://myanimelist.net/animelist/USERNAME/load.json?status=2 to get the JSON DATA of COMPLETED anime
  def parse_profile_completed_anime(self, response):
      """
      get json data of completed anime.
      """

      attr = response.meta["attr"]

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

  # https://myanimelist.net/animelist/USERNAME/load.json?status=3 to get the JSON DATA of ON HOLD anime
  def parse_profile_on_hold_anime(self, response):
      """
      get json data of on hold anime.
      """
      attr = response.meta["attr"]

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

  # https://myanimelist.net/animelist/USERNAME/load.json?status=4 to get the JSON DATA of DROPPED anime
  def parse_profile_dropped_anime(self, response):
    """
    get json data of dropped anime.
    """
    attr = response.meta["attr"]
    attr["dropped"] = json.loads(response.body.decode("utf-8"))
    print(ProfileItem)
    yield ProfileItem(**attr)
