import json
import re
from scrapy import Spider, Request
from scrapy.loader import ItemLoader
from tm_scraper.items import Squad
from urllib.parse import urlencode, urlparse, parse_qs
from datetime import datetime, timezone
#from soccerway.competitions import competitions_id_list

class SquadSpider(Spider):
    name = "squad"
    # start_urls = ['https://www.transfermarkt.com/weltmeisterschaft-2022/teilnehmer/pokalwettbewerb/WM22/saison_id/2021']
    # start_urls = ['https://www.transfermarkt.com/ weltmeisterschaft-2018/teilnehmer/pokalwettbewerb/WM18/saison_id/2017']
    start_urls = ['https://www.transfermarkt.com/weltmeisterschaft-2014/teilnehmer/pokalwettbewerb/WM14/saison_id/2013']


    def parse(self, response):
        teams = response.xpath('//html/body/div[2]/main/div[4]/div[1]/div[1]/div[2]/div/table/tbody/tr')
        for team in teams:
            link = team.xpath('./td[2]/a/@href').get()
            link = link + "?saison_id=2013"
            yield response.follow(link, self.parse2)



    def parse2(self, response):
        team = str(response.xpath('/html/body/div[2]/main/header/div[1]/h1/text()').get())
        players = response.xpath('/html/body/div[2]/main/div[2]/div[1]/div[1]/div[3]/div/table/tbody/tr')
        item = Squad()
        for player in players:
            item["team_name"] = team
            item["player_name"] = player.xpath("./td[2]/table/tr[1]/td[2]/div[1]/span/a/text()").get()
            item["position"] = player.xpath("./td[2]/table/tr[2]/td/text()").get()
            mv = player.xpath('./td[5]/a/text()').get() # 6 for defult, 5 for earlier years
            if mv is None:
                item['market_value'] = None
            else:
                mv = mv[1:]
                if "Th" in mv:
                    item['market_value'] = "0."+ mv[0]
                else:
                    item['market_value'] = mv[:-1]
            item["is_starting"] = False
            yield item


