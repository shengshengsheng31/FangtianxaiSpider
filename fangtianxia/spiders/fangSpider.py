# -*- coding: utf-8 -*-
import scrapy
import re
from fangtianxia.items import NewHouseItem, ESFHouseItem
from scrapy_redis.spiders import RedisSpider


# 分布式改造1，使用redis的爬虫
# class FangspiderSpider(scrapy.Spider):
class FangspiderSpider(RedisSpider):
    name = 'fangSpider'
    allowed_domains = ['fang.com']
    # 分布式改造2，取消start_urls使用redis_key
    # start_urls = ['https://www.fang.com/SoufunFamily.htm']
    redis_key = "fangSpider:start_urls"

    def parse(self, response):
        self.count = 0
        province = None
        trs = response.xpath('//div[@id="c02"]//tr')
        # 遍历省
        for tr in trs:
            provinces_text = tr.xpath('./td[not(@class)]/strong/text()').get()
            # 去除所有None的情况
            if provinces_text:
                provinces_text = re.sub(r"\s", "", provinces_text)
            # 过滤外国
            if provinces_text == "其它":
                break
            # 去除所有空的情况
            if provinces_text:
                province = provinces_text
            city_texts = tr.xpath('.//a')
            # 遍历市
            for city_text in city_texts:
                city = city_text.xpath('./text()').get()
                # 城市url
                city_url = city_text.xpath('./@href').get()
                scheme = city_url.split('.')[0].split('/')[-1]
                # 新房url
                newhouse_url = 'https://' + scheme + '.newhouse.fang.com/house/s/'
                # 二手房url
                esf_url = 'https://' + scheme + '.esf.fang.com'
                # yield scrapy.Request(url=newhouse_url, callback=self.parse_newhouse, meta={"info": (province, city)})
                yield scrapy.Request(url=esf_url, callback=self.parse_esf, meta={"info": (province, city)})
            #     break  # 市遍历
            # break  # 省遍历

    def parse_newhouse(self, response):
        province, city = response.meta.get("info")
        lists = response.xpath('//div[@class="clearfix"]')
        for li in lists:
            name_text = li.xpath('.//div[@class="nlcd_name"]/a/text()').get()
            house_type_text = li.xpath('.//div[contains(@class,"house_type")]/a/text()').getall()
            area_text = "".join(li.xpath('.//div[contains(@class,"house_type")]/text()').getall())
            price_text = str(li.xpath('.//div[@class="nhouse_price"]/span/text()').get()) + str(
                li.xpath('.//div[@class="nhouse_price"]/em/text()').get())
            address_text = li.xpath('.//div[@class="address"]/a/@title').get()
            district_text = "".join(li.xpath('.//div[@class="address"]/a//text()').getall())
            sale_text = li.xpath('.//div[contains(@class,"fangyuan")]/span/text()').get()
            origin_url_text = "https:" + str(li.xpath('.//div[@class="nlcd_name"]/a/@href').get())

            # 避免有None的情况
            if name_text:
                name = name_text.strip()
                rooms = "".join(house_type_text)
                area = re.sub(r"\s|/|－", "", area_text)
                price = price_text
                address = address_text
                district = re.search(r".*\[(.+)\].*", district_text).group(1)  # 匹配第一个括号内容
                sale = sale_text
                origin_url = origin_url_text
                self.count += 1
                # print(name,origin_url,count)
            item = NewHouseItem(name=name, rooms=rooms, area=area, price=price, address=address, district=district,
                                sale=sale, origin_url=origin_url, province=province, city=city)
            yield item
        next_url = response.xpath('//a[@class="next"]/@href').get()
        if next_url:
            yield scrapy.Request(url=response.urljoin(next_url),
                                 callback=self.parse_newhouse,
                                 meta={"info": (province, city)})  # 下一页url由ajax加载，没有使用selenium，所以使用urljoin构建绝对url

    def parse_esf(self, response):
        province, city = response.meta.get("info")
        lists = response.xpath('//dl[@class="clearfix"]')
        # 给定初始值，避免无值报错
        rooms = floor = toward = year = area = " "
        for li in lists:
            name_text = li.xpath('.//p[@class="add_shop"]/a/@title').get()
            infos = li.xpath('.//p[@class="tel_shop"]/text()').getall()
            infos = list(map(lambda x: re.sub(r"\s", "", x), infos))
            for info in infos:
                if "厅" in info:
                    rooms = info
                elif "层" in info:
                    floor = info
                elif "向" in info:
                    toward = info
                elif "年" in info:
                    year = str(re.search(r'(\d+).*?', info).group(1))
                elif "㎡" in info:
                    area = info
            address_text = li.xpath('.//p[@class="add_shop"]/span/text()').get()
            unit_text = li.xpath('.//dd[@class="price_right"]/span[2]/text()').get()
            origin_url_text = li.xpath('.//h4[@class="clearfix"]/a/@href').get()
            price_text = str(li.xpath('.//dd[@class="price_right"]/span/b/text()').get()) + str(
                li.xpath('.//dd[@class="price_right"]/span/text()').get())
            if name_text:
                name = name_text
                address = address_text
                unit = unit_text
                price = price_text
                origin_url = response.urljoin(origin_url_text)

            item = ESFHouseItem(name=name, rooms=rooms, floor=floor, toward=toward, year=year, address=address,
                                area=area, price=price, unit=unit, origin_url=origin_url)
            yield item
            next_url = response.xpath('//div[@class="page_al"]//a[contains(text(),"下一页")]/@href').get()
            if next_url:
                yield scrapy.Request(url=response.urljoin(next_url),
                                     callback=self.parse_esf,
                                     meta={"info": (province, city)})  # 下一页url由ajax加载，没有使用selenium，所以使用urljoin构建绝对url
