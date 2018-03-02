#!/usr/bin/python3
import argparse
import base64
import csv
import os
import re
import smtplib
import socket
import sys
import time
import schedule
import json
import pandas as pd
from datetime import datetime
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import mechanicalsoup
from bs4 import BeautifulSoup
from selenium import webdriver
from mailjet_rest import Client
from decimal import Decimal
from slackclient import SlackClient

btcPrice = {}

class LocalBitcoinsSpider:
    __previos_data = []
    __data = {}
    __total_updated = 0

    def __init__(self, input_url, csv_file, from_address=None, to_address=None, subject=None,
                 email_body=None, api_public_key = None, api_secret_key = None, slack_token=None, btc=None):
        self.__url = input_url
        self.__output_csv = csv_file + '.csv' if not str(csv_file).endswith('.csv') else csv_file
        self.__from_address = from_address
        self.__to_address = to_address
        self.__subject = subject
        self.__email_body = email_body
        self.__api_public_key = api_public_key
        self.__api_secret_key = api_secret_key
        self.__slack_token = slack_token
        self.btc = btc
        try:
            self.__data = pd.read_csv(self.__output_csv, index_col='trader')
        except:
            self.__data = pd.DataFrame(
                             {'tx_total': 0,
                              'reputation': 0,
                              'price': 0,
                              'volume': 0,
                              'age': 0}, index=['null'])

    def __enter__(self):
        self.__build_opener()
        self.__previos_data.clear()
        if os.path.exists(self.__output_csv):
            self.__data = pd.read_csv(self.__output_csv, index_col='trader')
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.__browser:
            del self.__browser

    def __build_opener(self):
        socket.setdefaulttimeout(60)
        self.__browser = mechanicalsoup.Browser(
            soup_config={'features': 'lxml'}
        )

    def grab_data(self):
        try:
            print('=== URL: {} ==='.format(self.__url))
            cap = webdriver.DesiredCapabilities.PHANTOMJS
            cap["phantomjs.page.settings.javascriptEnabled"] = True
            cap[
                "phantomjs.page.settings.userAgent"] = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/59.0.3071.115 Safari/537.36'
            driver = webdriver.PhantomJS('./phantomjs', desired_capabilities=cap)
            driver.get(self.__url)

            print('Script is going to sleep for 10 seconds...')
            time.sleep(10)

            print('Trying to get results from page...')
            driver.get(self.__url)
            data = driver.page_source
            driver.close()

            soup = BeautifulSoup(data)
            if not soup:
                print('No response data found from url: {}'.format(self.__url))
                return

            results_link = soup.find('a', {'name': 'results'})
            if not results_link:
                print('No result found!')
                return

            table = results_link.find_next_sibling('table')
            if not table:
                print('No result found!')
                return

            tr_list = table.find_all('tr')
            if tr_list and len(tr_list) > 1:
                for tr in tr_list[1:]:
                    td_list = tr.find_all('td')
                    if not td_list or len(td_list) < 4:
                        continue

                    try:
                        trader1, trader2, trader3 = '', '', ''
                        trader_content = self.__clean_data(td_list[0].text.strip())
                        trader_m = re.search(r'^([^\(]*?)\(([^\)]*?)\)', trader_content)
                        if trader_m:
                            trader_part1 = trader_m.group(1).strip()
                            trader_part2 = trader_m.group(2).strip()
                            trader_part2_split = re.split(r';', trader_part2)
                            trader = trader_part1 + ', ' + ', '.join(
                                [re.sub(r'[^\d]', '', word) for word in trader_part2_split])
                            trader1, trader2, trader3 = trader.split(', ')
                        payment_method = self.__clean_data(td_list[1].text.strip())
                        price = self.__clean_data(td_list[2].text.strip().strip("USD"))
                        limits = self.__clean_data(td_list[3].text.strip())
                        csv_data = [trader1, trader2, trader3, price, limits]
                        print(csv_data)
                        if trader1 in self.__data.index:
                            print('Already exists. Skip writing...')
                            continue
                        value = Decimal(re.sub(r'[^\d.]', '', price))
                        if value<self.btc*1.17:
                            #todo raise exception instead
                            print("Price low, skipping")
                            continue
                        if (int(trader3) < 95):
                            print('Bad Reputation Skip writing...')
                            continue
                        if (int(trader2) < 31):
                            print('Bad Reputation Skip writing...')
                            continue
                        newRow = pd.DataFrame({'tx_total': trader2,
                              'reputation': trader3,
                              'price': price,
                              'volume': limits,
                              'age': 0}, index=[trader1])
                        self.__data = self.__data.append(newRow)
                        self.__total_updated+=1
                    except Exception as ex:
                        print("Exception Found:", ex)
            self.__write_data_to_csv()
        except Exception as x:
            print('Error grabbing page: ')
            print(x)
        finally:
            print("Finally")
            if (self.__total_updated > 0):
                self.send_email_via_mailjet()


    @staticmethod
    def __clean_data(data):
        try:
            result = re.sub(r'\n+', ' ', data)
            return re.sub(r'\s+', ' ', result)
        except Exception as x:
            print('Error when cleanup data.' + str(x))
        return ''

    def __write_data_to_csv(self):
        df = self.__data
        df['age'] += 1
        df=df[df['age']<3]
        df.to_csv(self.__output_csv, index_label='trader')

    def send_email_via_mailjet(self):
        try:
            if not self.__from_address or not self.__to_address:
                return

            print('Sending email...')
            mailjet = Client(auth=(self.__api_public_key, self.__api_secret_key), version='v3.1')
            data = {
                'Messages': [
                    {
                        "From": {
                            "Email": self.__from_address,
                            "Name": ""
                         },
                        "To": [
                            {
                                "Email": self.__to_address,
                                "Name": ""
                            }
                        ],
                        "Subject": self.__subject,
                        "TextPart": self.__email_body + str(self.__data.index.values)
                    }
                ]
            }
            result = mailjet.send.create(data=data)
            print(result.status_code)
            #print(result.json())
            print('Email send successfully.')
        except Exception as x:
            print(x)

def updatedBtcPrice( btc ):
    date = datetime.now().date()
    global btcPrice
    if date in btcPrice:
        return btcPrice[date]
    else:
        try:
          btcPrice[date] = ccxt.gdax().fetch_ticker('BTC/USD')['ask']
          return btcPrice[date]
        except:
          return btc

def job():
    print("Starting a job")
    with open('crawler.conf', 'r') as f:
        args = json.load(f)

    url = args['url']
    #https://localbitcoins.com/instant-bitcoins/?action=sell&country_code=US&amount=&currency=USD&place_country=US&online_provider=ALL_ONLINE&find-offers=Search

    file = 'df'
    email = args['src_email']
    subject = 'New alarms'
    body = "The following traders are available: "
    dest_email = args['dest_email']
    api_public_key = args['api_public_key']
    api_secret_key = args['api_secret_key']
    btc = args['btc']
    btc = updatedBtcPrice(btc)
    with LocalBitcoinsSpider(url, file, email, dest_email, subject, body, api_public_key, api_secret_key , btc=btc) as spider:
        spider.grab_data()

if __name__ == '__main__':
    job()
    schedule.every(19).minutes.do(job)
    while 1:
        schedule.run_pending()
        time.sleep(1)

