# -*- coding: utf-8 -*-

# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: http://doc.scrapy.org/en/latest/topics/item-pipeline.html

import json
import os
import numpy as np
from myanimelist.items import AnimeItem, ReviewItem, ProfileItem
from pymongo import MongoClient
import pickle

class ProcessPipeline(object):

    def open_spider(self, spider):
      pass

    def close_spider(self, spider):
      pass

    def process_item(self, item, spider):
      item_class = item.__class__.__name__

      if item_class == "AnimeItem":
        item = self.process_anime(item)
      elif item_class == "ReviewItem":
        item = self.process_review(item)
      elif item_class == "ProfileItem":
        item = self.process_profile(item)

      return item

    def process_anime(self, item):
      if 'N/A' in item['score']:
        item['score'] = np.nan
      else:
        item['score'] = float(item['score'].replace("\n", "").strip())

      if item['ranked'] == 'N/A':
        item['ranked'] = np.nan
      else:
        item['ranked']     = int(item['ranked'].replace("#", "").strip())

      item['popularity'] = int(item['popularity'].replace("#", "").strip())
      item['members']    = int(item['members'].replace(",", "").strip())
      item['episodes']   = item['episodes'].replace(",", "").strip()

      return item

    def process_review(self, item):
      item['score']      = float(item['score'].replace("\n", "").strip())

      return item

    def process_profile(self, item):

      return item

class SaveLocalPipeline(object):

    def open_spider(self, spider):
      os.makedirs('data/', exist_ok=True)

      self.files = {}
      self.files['AnimeItem']   = open('data/animes.jl', 'w+')
      self.files['ReviewItem']  = open('data/reviews.jl', 'w+')
      self.files['ProfileItem'] = open('data/profiles.jl', 'w+')

    def close_spider(self, spider):
      for k, v in self.files.items():
        v.close()

    def process_item(self, item, spider):
      item_class = item.__class__.__name__

      # Save
      self.save(item_class, item)

      return item

    def save(self, item_class, item):
      line =  json.dumps(dict(item)) + '\n'
      self.files[item_class].write(line)


class SaveMongoPipeline(object):
    def __init__(self, mongodb_url = "", update_cache = ""):
        self.mongodb_url = mongodb_url
        self.update_cache = update_cache

    def open_spider(self, spider):
      if self.is_configured:
        self.client  = MongoClient(self.mongodb_url)
        self.db      = self.client['myanimelist']

        self.collection = {}
        self.collection['AnimeItem']   = self.db.animes
        self.collection['ReviewItem']  = self.db.reviews
        self.collection['ProfileItem'] = self.db.profiles

        if self.update_cache == "True":
          self._update_cache(self.db)

    def close_spider(self, spider):
      self.client.close()

    def process_item(self, item, spider):
      item_class = item.__class__.__name__

      # Save
      if self.is_configured:
        self.save(item_class, item)

      return item

    def save(self, item_class, item):
      # self.collection[item_class].insert_one(dict(item))
      if item_class == "AnimeItem":
        self.collection[item_class].replace_one({"uid": dict(item)["uid"]}, dict(item), upsert=True)
      elif item_class == "ReviewItem":
        self.collection[item_class].replace_one({"uid": dict(item)["uid"]}, dict(item), upsert=True)
      elif item_class == "ProfileItem":
        self.collection[item_class].replace_one({"profile": dict(item)["profile"]}, dict(item), upsert=True)

    @property
    def is_configured(self):
      return (self.mongodb_url is not None)

    @classmethod
    def from_crawler(cls, crawler):
      settings = crawler.settings
      return cls(settings.get('MONGODB_URL'), settings.get("UPDATE_CACHE"))

    def _update_cache(self, db):
      print("===============================")
      print("UPDATING CACHEFILE")
      print("===============================")
      anime_uids = {}
      review_uids = {}
      profile_names = {}

      for doc in db.animes.find():
        anime_uids[doc["uid"]] = 1

      for doc in db.reviews.find():
        review_uids[doc["uid"]] = 1

      for doc in db.profiles.find():
        profile_names[doc["profile"]] = 1


      with open("cache/anime_uid.pkl", "wb") as f:
        pickle.dump(anime_uids, f)

      with open("cache/review_uid.pkl", "wb") as f:
        pickle.dump(review_uids, f)

      with open("cache/profile_names.pkl", "wb") as f:
        pickle.dump(profile_names, f)

      print("===============================")
      print("DONE UPDATING CACHEFILES")
      print("===============================")
