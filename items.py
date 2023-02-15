# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy
from scrapy import Item, Field

class Match(Item):
    id = Field()
    datetime = Field()
    competition_name = Field()
    home_team = Field()
    away_team = Field()
    score_regular = Field()
    score_overtime = Field()
    overtime = Field()
    home_advantage = Field()
    home_team_mv = Field()
    away_team_mv = Field()
    home_team_age = Field()
    away_team_age = Field()


class Tournament(Item):
    url = Field()
    name = Field()
    confederation = Field()

class Team(Item):
    name = Field()
    confederation = Field()


class Squad(Item):
    team_name = Field()
    player_name = Field()
    position = Field()
    market_value = Field()
    is_starting = Field()
