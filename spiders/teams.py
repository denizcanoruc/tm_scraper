import scrapy
from tm_scraper.items import Team

class TeamsSpider(scrapy.Spider):
    name = "teams"
    start_urls = [
            "https://www.transfermarkt.com/statistik/weltrangliste"
        ]

    def parse(self, response):
        pages = response.css('a.tm-pagination__link::attr(href)')
        for page in pages:
            yield response.follow(page, self.parse_teams)

    def parse_teams(self, response):
        teams = response.css('tr.odd') + response.css('tr.even')
        for team in teams:
            item = Team()
            item['name'] = team.xpath('./td[2]/a[1]/@title').get()
            item['confederation'] = team.xpath('./td[6]/text()').get()
            yield item

