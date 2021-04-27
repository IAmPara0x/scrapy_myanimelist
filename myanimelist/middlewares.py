
import random
import time
from functools import total_ordering
import math
import pickle


from scrapy import signals

@total_ordering
class Proxy:
  def __init__(self, proxy):
    self.info : str = "WORKING"
    self.__time : float = math.inf
    self.__proxy : str = proxy

  def __repr__(self):
    return f"Proxy: {self.__proxy}, Status: {self.info}, Request Time: {self.__time}"

  @property
  def status(self):
    return self.info

  @property
  def proxy(self):
    self.__time = time.time()
    return self.__proxy

  @status.setter
  def status(self, x):
    if x.lower() == "working":
      self.info = "WORKING"
    elif x.lower() == "dead":
      self.info = "DEAD"
    elif x.lower() == "cooldown":
      self.info = "COOLDOWN"
    else:
      raise ValueError("Only possible status are working, cooldown, dead")

  @property
  def time(self):
    return self.__time

  def __eq__(self, other):
    if other.__class__ is self.__class__:
      return (self.info == other.info) and (self.time == other.time)
    else:
      return NotImplemented

  def __ne__(self, other):
    if other.__class__ is self.__class__:
      return not self.__eq__(other)
    else:
      return NotImplemented

  def __lt__(self, other):
    if other.status == self.status:
      return (time.time() - self.time) < (time.time() - other.time)
    elif other.status == "WORKING":
      return True
    elif other.status == "COOLDOWN" and self.status == "DEAD":
      return True
    else:
      return False

PROXY_LIST = None
def spider_closed(spider, reason):
  with open("proxy-list-state.pkl", "wb") as f:
    pickle.dump(PROXY_LIST, f)

class RotatingProxies(object):

  def __init__(self, use_cached_proxy=""):
    if use_cached_proxy == "True":
      with open("proxy-list-state.pkl", "rb") as f:
        self.proxy_list = pickle.load(f)
    else:
      with open("proxy-list.txt", "r") as f:
        x = f.readlines()
        x = [i[:-1] for i in x]
        self.proxy_list = [Proxy(i) for i in x]
      try:
        with open("proxy-list-state.pkl", "rb") as f:
          x = pickle.load(f)
          self.proxy_list.extend([i for i in x if i.status == "WORKING"])
      except Exception as e:
        pass

    self.max_proxies_to_try = len(self.proxy_list)//4
    self.logstats_interval = 30

  @classmethod
  def from_crawler(cls, crawler):
    crawler.signals.connect(spider_closed, signal=signals.spider_closed)
    settings = crawler.settings
    return cls(settings.get("USE_CACHED_PROXY"))

  def engine_started(self):
    self.log_task = task.LoopingCall(self.log_stats)
    self.log_task.start(self.logstats_interval, now=True)

  def process_request(self, request, spider):

    # print("=======================")
    # print(f"using proxy : {proxy}")
    # print("=======================")

    proxy = self.get_proxy()
    request.meta["download_timeout"] = 5
    if "dont_use_proxy" not in request.meta:
      request.meta["proxy"] = proxy
    else:
      print("=======================")
      print("using default IP")
      print("=======================")

  def process_response(self, request, response, spider):
    if "dont_use_proxy" not in request.meta:
      print("=======================")
      print(f"proxy : {request.meta['proxy']} status : {response.status} url : {response.url}")
      print("=======================")
      global PROXY_LIST
      PROXY_LIST = self.proxy_list
      proxyCls = self._get_proxy_cls(request.meta["proxy"])
      if len(response.css("div.basresult")) > 0:
        proxyCls.status = "dead"
        self.proxy_list = sorted(self.proxy_list, reverse=True)
        return self._retry(request, spider)
      elif response.status == 403:
        proxyCls.status = "cooldown"
        self.proxy_list = sorted(self.proxy_list, reverse=True)
        return self._retry(request, spider)
      else:
        proxyCls.status = "working"
        return response
    else:
      return response

  def process_exception(self, request, exception, spider):
    if "dont_use_proxy" not in request.meta:
      proxyCls = self._get_proxy_cls(request.meta["proxy"])
      proxyCls.status = "dead"
      self.proxy_list = sorted(self.proxy_list, reverse=True)
      return self._retry(request, spider)

  def _retry(self, request, spider):
    print("====================================")
    print(f"RETRYING {request.url}")
    print("====================================")
    retries = request.meta.get('proxy_retry_times', 0) + 1
    max_proxies_to_try = request.meta.get('max_proxies_to_try',
                                          self.max_proxies_to_try)
    if retries <= max_proxies_to_try:
      retryreq = request.copy()
      retryreq.meta['proxy_retry_times'] = retries
      retryreq.dont_filter = True
      return retryreq
    else:
      return None

  def log_stats(self):
      logger.info('%s' % self.proxy_list)

  def _get_proxy_cls(self, proxy):
      for proxyCls in self.proxy_list:
        if proxyCls.proxy == proxy:
          return proxyCls

  def get_proxy(self):
    self.proxy_list = sorted(self.proxy_list, reverse=True)
    if self.proxy_list[0] != math.inf:
      proxy = random.choice(self.proxy_list[:6]).proxy
    else:
      proxy = self.proxy_list[0].proxy
    self.proxy_list = sorted(self.proxy_list, reverse=True)
    return proxy

