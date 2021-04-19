# -*- coding: utf-8 -*-
import scrapy
import numpy as np
from myanimelist.items import AnimeItem, ReviewItem, ProfileItem
import json
import random
from urllib.parse import unquote
import os
import pickle


# https://myanimelist.net/topanime.php?limit=<limit>
#
# scrapy runspider myanimelist/spiders/MyAnimeList.py -a start_limit=1 -a end_limit=20000 -s MONGODB_URL=mongodb://127.0.0.1:27017
#

class MyAnimeList(scrapy.Spider):
    name = "myanimelist"

    allowed_domains = ["myanimelist.net"]

    def start_requests(self):
        yield scrapy.Request(
            f"https://myanimelist.net/topanime.php?limit={self.start_limit}",
            meta={"proxy": "http://165.225.77.42:80"},
            callback=self.parse,
        )

    def parse(self, response):
      url = response.css(
          "td.title.al.va-t.word-break a::attr(href)"
      ).extract_first()
      print("================================")
      print(url)
      print("================================")
      yield scrapy.Request(
          url,
          callback=self.parse_anime,
      )

    def parse_anime(self, response):
        attr = {}
        attr["link"] = response.url
        attr["uid"] = self._extract_anime_uid(response.url)
        attr["title"] = response.css(
            "h1 span[itemprop='name'] ::text"
        ).extract_first()
        attr["synopsis"] = " ".join(response.css("p[itemprop='description']::text").extract()[:-1])
        attr["score"] = response.css("div.score ::Text").extract_first()
        attr["ranked"] = response.css("span.ranked strong ::Text").extract_first()
        attr["popularity"] = response.css(
            "span.popularity strong ::Text"
        ).extract_first()
        attr["members"] = response.css("span.members strong ::Text").extract_first()
        attr["genre"] = response.css("div span[itemprop='genre'] ::text").extract()

        status = response.css("td.borderClass div.spaceit::text").extract()
        status = [i.replace("\n", "").strip() for i in status]

        attr["episodes"] = status[1]
        attr["aired"] = status[3]

        print(AnimeItem)

        yield AnimeItem(**attr)

        yield response.follow(
            "{}/{}".format(response.url, "reviews?p=1"),
            self.parse_list_review,
        )

    def parse_list_review(self, response):
        p = response.url.split("p=")[1]

        reviews = response.css("div.borderDark")
        for review in reviews:
            link = review.css("div.clearfix a::attr(href)").extract_first()
            yield response.follow(
                link,
                self.parse_review,
            )

        # None, First Page and not last page
        next_page = response.css("div.mt4 a::attr(href)").extract()
        if (
            next_page is not None
            and len(reviews) > 0
            and len(next_page) > 0
            and (p == "1" or len(next_page) > 1)
        ):
            next_page = next_page[0] if p == "1" else next_page[1]
            yield response.follow(
                next_page,
                self.parse_list_review,
            )

    def parse_review(self, response):
        attr = {}
        attr["link"] = response.url
        attr["uid"] = response.url.split("id=")[1]
        attr["anime_uid"] = self._extract_anime_uid(
            response.css("a.hoverinfo_trigger ::attr(href)").extract_first()
        )
        attr["uid"] = response.url.split("id=")[1]
        attr["helpful"] = int(
            response.css("div.lightLink.spaceit strong span::text").extract_first()
        )

        url_profile = response.css(
            "td a[href*=profile] ::attr(href)"
        ).extract_first()
        attr["profile"] = url_profile.split("/")[-1]

        # Parses the Number of Helpful
        if attr["helpful"] >= self._helpful_threshold():
            attr["text"] = " ".join(
                response.css("div.textReadability ::text").extract()
            )
        else:
            attr["text"] = np.nan

        scores = np.array(response.css("div.textReadability td ::text").extract())
        scores = dict(
            zip(
                scores[[i for i in range(12) if (i % 2) == 0]],
                scores[[i for i in range(12) if (i % 2) == 1]],
            )
        )
        attr["scores"] = scores
        attr["score"] = scores["Overall"]

        # /review
        print(ReviewItem)
        yield ReviewItem(**attr)

        # /profile
        yield response.follow(
            url_profile,
            self.parse_profile,
        )


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

    def _extract_anime_uid(self, url):
        return url.split("/")[4]

    def _list2dict(self, attrs):
        attrs = np.array(attrs)
        attrs = dict(
            zip(
                attrs[[i for i in range(len(attrs)) if (i % 2) == 0]],
                attrs[[i for i in range(len(attrs)) if (i % 2) == 1]],
            )
        )
        return attrs

    def _helpful_threshold(self):
        return 45

    def _handle_request(self, response, success_callback, failure_callback):
        if response.status == 200 or respone.status == 404:
            return success_callback(response)
        else:
            try:
                self.proxy_pool.remove(response.meta["proxy"])
                return scrapy.Request(response.url, callback=failure_callback)
            except Exception as _:
                pass

    def _create_proxy_pool(self, proxy_list_file="myanimelist/spiders/proxy-list.txt"):
        self.proxy_pool = []

        with open(proxy_list_file, "r") as f:
            lines = f.readlines()
            for line in lines:
                self.proxy_pool.append("http://{}".format(line.split("\n")[0]))

        print(self.proxy_pool)
