import scrapy

class MediaItem(scrapy.Item):
    page_url = scrapy.Field()   
    media_url = scrapy.Field()  
    media_type = scrapy.Field() 