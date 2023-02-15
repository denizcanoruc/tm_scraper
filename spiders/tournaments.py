import scrapy
from tm_scraper.items import Tournament

class TournamentsSpider(scrapy.Spider):
    name = "tournaments"
    start_urls = [
            "https://www.transfermarkt.com/wettbewerbe/fifa",
            #"https://www.transfermarkt.com/wettbewerbe/europa",
            "https://www.transfermarkt.com/wettbewerbe/amerika",
            "https://www.transfermarkt.com/wettbewerbe/afrika",
            "https://www.transfermarkt.com/wettbewerbe/asien"
        ]

    def parse(self, response):
        boxes = response.css('div.box')
        for box in boxes:
            box_header = box.css('div.content-box-headline::text').get()
            if(box_header is not None and box_header.strip() == "International cups"):
                break

        tours = box.css("a.tm-links")
        for tour in tours:
            item = Tournament()
            item['name'] = tour.xpath('@class').get()
            item['confederation'] = str(response)[47:-1]
            item['url'] = tour.xpath('@href').get()
            yield item

