# -*- coding: utf-8 -*-
import json
import re
from scrapy import Spider, Request
from scrapy.loader import ItemLoader
from tm_scraper.items import Match
from urllib.parse import urlencode, urlparse, parse_qs
from datetime import datetime, timezone
#from soccerway.competitions import competitions_id_list

#TODO: ERROR: Spider error processing <GET https://www.transfermarkt.com/spielbericht/index/spielbericht/3579212>
# (referer: https://www.transfermarkt.com/afrika-cup/gesamtspielplan/pokalwettbewerb/AFCN/saison_id/1956) ValueError: url can't be None


class MatchesSpider(Spider):


    name = "matches"
    '''
    #allowed_domains = ["soccerway.mobi"]
    start_urls = ['https://www.transfermarkt.com']
    params = {
        "comp_name": "european-qualifiers-play-offs",
        "comp_id": "POEM"
    }
    '''
    def start_requests(self):
        #start_url = 'http://www.soccerway.mobi/?sport=soccer&page=competition&id={}&localization_id=www'
        #start_url = "https://www.transfermarkt.com/{comp_name}/startseite/pokalwettbewerb/{comp_id}"
        start_url = "https://www.transfermarkt.com"
        tours = getattr(self, 'tours', None)
        f = open(tours)
        data = json.load(f)
        #for i in competitions_id_list:
        #    request = Request(url=start_url.format(str(i)), callback=self.parse)
        #    yield request
        for i in data:
            request = Request(url=start_url + i['url'], callback=self.parse)
            yield request
    

    def parse(self, response):
        footer_links = response.css('div.footer-links')
        for footer_link in footer_links:
            text = footer_link.xpath('a//text()').get().strip()
            if text in [
                "All fixtures & results",
                "All games"
            ]:
                next_url = footer_link.xpath('a/@href').get()
                # TODO: YIELD OR RETURN
                yield response.follow(next_url, self.check_years)

    def check_years(self, response):
        info_box = response.css('table.auflistung')
        if info_box:
            values = info_box.css('select.chzn-select')
            for val in values.xpath('./option/@value'):
                current_url = str(response.url)
                next_url = current_url.replace(current_url[-4:],val.get())
                yield response.follow(next_url, self.extract_match_url,dont_filter=True)
        else:
            yield response.follow(response.url, self.extract_match_url, dont_filter=True)


    def extract_match_url(self, response):
        game_links = response.css('a.ergebnis-link')
        for link in game_links:
            href = link.xpath('@href').get()
            yield response.follow(href, self.parse_match_sheet)
            #return response.follow("https://www.transfermarkt.com/spielbericht/index/spielbericht/3044310", self.parse_match_sheet)

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
        yield response.follow(next_url, self.parse_match_lineup, cb_kwargs={'item': item,'stadium_href' : stadium_href})

    '''
    def parse_match_lineup(self, response, item, stadium_href):

        # get statistics table
        stat_footers = response.css('div.table-footer')

        # extract average of the teams
        item['home_team_age'] = stat_footers[0].xpath('./table/tr/td[1]/text()').get()[10:]
        item['away_team_age'] = stat_footers[1].xpath('./table/tr/td[1]/text()').get()[10:]

        # extract market value of the teams
        mv = str(stat_footers[0].xpath('./table/tr/td[3]/text()').get()[11:-1])
        if "Th" in mv:
            item['home_team_mv'] = "0."+ mv[0]
        else:
            item['home_team_mv'] = mv

        mv = str(stat_footers[1].xpath('./table/tr/td[3]/text()').get()[11:-1])
        if "Th" in mv:
            item['away_team_mv'] = "0."+ mv[0]
        else:
            item['away_team_mv'] = mv

        if "//" in stadium_href:
            item['home_advantage'] = None
            yield item
        else:
            yield response.follow(stadium_href, self.check_home_adv, cb_kwargs={'item': item}, dont_filter=True)
    '''

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



        """
        def parse(self, response):
            venue = Venue()
            venue['country'], venue['city'], venue['name'] = response.css('title::text')[0].extract().split(',')
            res = response.xpath('//td//b/text()')
            if len(res) > 0:
                venue['opened'] = res[0].extract()
            res = response.xpath('//td//b/text()')
            if len(res) > 1:
                venue['capacity'] = res[1].extract()
            venue['lat'], venue['lng'] = response.xpath('//script/text()')[1].re(r'\((.*)\)')[1].split(',')
            return venue


        def parse(self, response):
            items = []
            area_id = parse_qs(response.xpath('//div[@class="clearfix subnav level-1"]//a[1]/@href').extract()[1])['area_id'][0]
            area_name = response.xpath('//div[@class="clearfix subnav level-1"]//a[1]/text()').extract()[1]
            competition_id = parse_qs(response.xpath('//div[@class="clearfix subnav level-1"]//li//a[2]/@href').extract_first())['id'][0]
            competition_name = response.xpath('//div[@class="clearfix subnav level-1"]//li//a[2]/text()').extract_first()
            matches = response.xpath('//table[@class="matches   "]//tbody//tr')
            for m in matches:
                item = Match()
                item['id'] = parse_qs(m.xpath('./td[@class="info-button button"]//a/@href').extract_first())['id'][0]
                item['datetime'] = datetime.fromtimestamp(int(m.xpath('@data-timestamp').extract_first()), timezone.utc).isoformat(' ')
                item['home_team_id'] = parse_qs(m.xpath('./td[contains(@class, "team team-a")]//a/@href').extract_first())['id'][0]
                item['away_team_id'] = parse_qs(m.xpath('./td[contains(@class, "team team-b")]//a/@href').extract_first())['id'][0]
                item['home_team'] = m.xpath('./td[contains(@class, "team team-a")]//a/text()').extract_first().strip()
                item['away_team'] = m.xpath('./td[contains(@class, "team team-b")]//a/text()').extract_first().strip()
                item['kick_off'] = m.xpath('./td[@class="score-time status"]//span/text()').extract_first()
                item['score'] = m.xpath('./td[@class="score-time score"]//span/text()').extract_first()

                item['area_id'] = area_id
                item['area_name'] = area_name
                item['competition_id'] = competition_id
                item['competition_name'] = competition_name

                item['updated'] = datetime.utcnow().isoformat(' ')
                yield item
                items.append(item)
            return items
            #self.log('URL: {}'.format(response.url))


    """

