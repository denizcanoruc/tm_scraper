import json
import re
from scrapy import Spider, Request
from scrapy.loader import ItemLoader
from tm_scraper.items import Match
from urllib.parse import urlencode, urlparse, parse_qs
from datetime import datetime, timezone
#from soccerway.competitions import competitions_id_list

class MatchesSpider(Spider):
    name = "matches_frnd"
    start_urls = ['https://www.transfermarkt.com/international-friendlies/gesamtspielplan/wettbewerb/FS?saison_id=2021&spieltagVon=1&spieltagBis=52']


    def parse(self, response):
        info_box = response.css('table.auflistung')
        if info_box:
            values = info_box.css('select.chzn-select')
            for val in values.xpath('./option/@value'):
                current_url = str(response.url)
                next_url = current_url.replace(current_url[-33:-29],val.get())
                yield response.follow(next_url, self.extract_match_url, dont_filter=True)
        else:
            yield response.follow(response.url, self.extract_match_url, dont_filter=True)

    def extract_match_url(self, response):
        boxses = response.css("div.large-6.columns")
        for box in boxses:
            match = box.css("tr:not([class^='bg_balu_20'])")
            ht = match.xpath("./td[3]/a/@title").get()
            at = match.xpath("./td[7]/a/@title").get()
            if ht[-3] != 'U' and at[-3] != 'U':
                href = match.xpath('./td[5]/a/@href').get()
                yield response.follow(href, self.parse_match_sheet)

    def parse_match_sheet(self, response):
        item = Match()

        # id of match in transfermarkt
        ind = str(response.url).rfind('/')
        item['id'] = response.url[ind+1:]

        # name of the tournament
        tour_box = response.css('div.spielername-profil')
        item['competition_name'] = tour_box.xpath('./h2/span/a/text()').get()

        # extract home and away "boxes" attributes and name of the teams
        game_box = response.css('div.box-content')
        home_club_box = game_box.css('div.sb-heim')
        away_club_box = game_box.css('div.sb-gast')
        item['home_team'] = home_club_box[0].xpath('a/text()').get()
        item['away_team'] = away_club_box[0].xpath('a/text()').get()

        # extract stadium info for checking home advantage in following parsers
        info_box = game_box.css('p.sb-zusatzinfos')
        stadium_href = info_box.xpath('span/a/@href').get()

        # extract date and time "box" attributes and data
        datetime_box = game_box.css('div.sb-spieldaten')[0]
        item['datetime'] = self.safe_strip(datetime_box.xpath('p/a[contains(@href, "datum")]/@href').get())[-10:]

        # parse scores form match sheet to extract regular and extra time scores
        # check if overtime applied
        game_box = response.css('div.box-content')
        result_box = game_box.css('div.ergebnis-wrap')
        overtime_check = self.safe_strip(result_box.css('div.sb-halbzeit::text').get())
        # check if overtime and penalty
        if overtime_check not in ["on pens", "AET"]:
            item['overtime'] = False
            item['score_regular'] = self.safe_strip(result_box.css('div.sb-endstand::text').get())
            item['score_overtime'] = self.safe_strip(result_box.css('div.sb-endstand::text').get())
        # if overtime or penalty check the goal box and scan the goals
        else:
            item['overtime'] = True

            boxes = response.css("div.box")
            goal_box = None
            for box in boxes:
                if box.xpath("./div/h2/text()").get() == "Goals":
                    goal_box = box
            # not goal box means match ended 0:0
            if goal_box is None:
                item['score_regular'] = "0:0"
                item['score_overtime'] = "0:0"
            # if goal box, iterate over home and away goals and check their minute
            else:
                home_goals = goal_box.css("li.sb-aktion-heim")
                away_goals = goal_box.css("li.sb-aktion-gast")
                home_score_reg = 0
                away_score_reg = 0
                home_score_ot = 0
                away_score_ot = 0

                # iterate goals of home team
                for goal in home_goals:
                    min_str = goal.css("span.sb-sprite-uhr-klein::attr(style)").get()
                    min_list = re.findall(r'\d+', min_str)
                    min = (int(min_list[0]) / 36) + 1 + (10 * (int(min_list[1]) / 36))
                    if min <= 90:
                        home_score_reg += 1
                    else:
                        home_score_ot += 1

                # iterate goals of away team
                for goal in away_goals:
                    min_str = goal.css("span.sb-sprite-uhr-klein::attr(style)").get()
                    min_list = re.findall(r'\d+', min_str)
                    min = (int(min_list[0]) / 36) + 1 + (10 * (int(min_list[1]) / 36))
                    if min <= 90:
                        away_score_reg += 1
                    else:
                        away_score_ot += 1

                item['score_regular'] = str(home_score_reg) + ":" + str(away_score_reg)
                item['score_overtime'] = str(home_score_reg+home_score_ot) + ":" + str(away_score_reg+away_score_ot)

        # continue to line-up page
        footer_link = response.css('li[id="line-ups"]')
        next_url = footer_link.xpath('a/@href').get()
        if (next_url is None):
            item['home_team_age'] = None
            item['away_team_age'] = None
            item['home_team_mv'] = None
            item['home_team_mv'] = None
            yield response.follow(stadium_href, self.check_home_adv, cb_kwargs={'item': item}, dont_filter=True)
        else:
            yield response.follow(next_url, self.parse_match_lineup, cb_kwargs={'item': item,'stadium_href' : stadium_href})


    def parse_match_lineup(self, response, item, stadium_href):

        # get statistics table
        starting_row = response.css('div.row.sb-formation')[0]
        home_footer = starting_row.xpath('./div[1]/div/div[3]')
        away_footer = starting_row.xpath('./div[2]/div/div[3]')

        # handle home team
        if(home_footer):
            item['home_team_age'] = home_footer[0].xpath('./table/tr/td[1]/text()').get()[10:]
            # extract market value of the teams
            mv = str(home_footer[0].xpath('./table/tr/td[3]/text()').get()[11:-1])
            if mv is "":
                item['home_team_mv'] = None
            else:
                if "Th" in mv:
                    item['home_team_mv'] = "0."+ mv[0]
                else:
                    item['home_team_mv'] = mv
        else:
            item['home_team_age'] = None
            item['home_team_mv'] = None

        if(away_footer):
            item['away_team_age'] = away_footer[0].xpath('./table/tr/td[1]/text()').get()[10:]
            # extract market value of the teams
            mv = str(away_footer[0].xpath('./table/tr/td[3]/text()').get()[11:-1])
            if mv is "":
                item['away_team_mv'] = None
            else:
                if "Th" in mv:
                    item['away_team_mv'] = "0."+ mv[0]
                else:
                    item['away_team_mv'] = mv
        else:
            item['away_team_age'] = None
            item['away_team_mv'] = None

        if stadium_href is None or "//" in stadium_href:
            item['home_advantage'] = None
            yield item
        else:
            yield response.follow(stadium_href, self.check_home_adv, cb_kwargs={'item': item}, dont_filter=True)

    def check_home_adv(self, response, item):
        adress_box = response.css('div[class = "content zentriert"]')
        if(adress_box):
            add_lines = adress_box[0].css('tr')
            country = add_lines.xpath('./td/text()').getall()
            if(item["home_team"] in country):
                item['home_advantage'] = True
            else:
                item['home_advantage'] = False
        else:
            item['home_advantage'] = None


        yield item




    def safe_strip(self, word):
        if word:
            return word.strip()
        else:
            return word


