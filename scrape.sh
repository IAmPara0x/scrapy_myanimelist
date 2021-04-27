#! /usr/bin/bash

lastLine=($(tail -n 1 anime_scrape_idx.txt))
currlastidx=${lastLine[0]}
first_it=true

run_crawler(){
  if [[  $((count % 30)) == 0  ]];
  then
    scrapy runspider myanimelist/spiders/MyAnimeList.py -a start_limit=$currlastidx -s MONGODB_URL=mongodb://127.0.0.1:27017 -s UPDATE_CACHE=False -s USE_CACHED_PROXY=False
  else
    scrapy runspider myanimelist/spiders/MyAnimeList.py -a start_limit=$currlastidx -s MONGODB_URL=mongodb://127.0.0.1:27017 -s UPDATE_CACHE=False -s USE_CACHED_PROXY=True
  fi
}

count=1

while true
do
  currlastidx=$((currlastidx + 1))
  time=$(date +"%H:%M")
  echo "$currlastidx"
  printf "$currlastidx - started on $time - " >> anime_scrape_idx.txt


  if [[ $((count % 30)) == 0 ]];
  then
    echo "=============================="
    echo "CREATING PROXY LIST"
    echo "=============================="
    timeout --signal=SIGINT 20 proxybroker find --types HTTPS > proxy-list.txt
    ./preprocess_proxy.py
    echo "=============================="
    echo "DONE CREATING PROXY LIST"
    echo "=============================="
  fi


  if [ "$first_it" = true ];
  then
    echo "=============================="
    echo "STARTING"
    echo "=============================="
    first_it=false
    run_crawler
  else
    run_crawler
  fi

  time=$(date +"%H:%M")
  printf "completed on $time \n" >> anime_scrape_idx.txt
  rm -r data
  count=$((count + 1))
done

