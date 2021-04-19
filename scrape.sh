#! /usr/bin/bash

lastLine=($(tail -n 1 anime_scrape_idx.txt))
currlastidx=${lastLine[0]}

while true
do
 currlastidx=$((currlastidx + 1))
 time=$(date +"%H:%M")
 echo "$currlastidx"
 printf "$currlastidx - started on $time - " >> anime_scrape_idx.txt
 scrapy runspider myanimelist/spiders/MyAnimeList.py -a start_limit=$currlastidx -a end_limit=20000 -s MONGODB_URL=mongodb://127.0.0.1:27017
 printf "completed \n" >> anime_scrape_idx.txt
done

