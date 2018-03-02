# localbitcoin_crawler
 This repo is used to search localbitcoins for offers according to your criteria.
 
 ## How it works
 
 The python script uses mechanical soup to get all available offers. It then compares the entries with the entries seen previously in order to fire alarms. Basically, it checks the website every 20 minutes, but it only sends an alert every hour, to avoid spamming.
 
 The criteria for alarms are price, reputation of trader, total of previous transactions of a trader. Those are currently hard-coded.
 
 The alarm currently used is an email via mailjet API. I plan to include slack on the next versions.
 
 Specific information is loaded from crawler.conf.
```
{
"src_email" : "src@email.com",
"dest_email" : "destination@email.com",
"api_public_key" : "NONE",
"api_secret_key" : "NONE",
"slack_token" : "NONE",
"url" : "https://localbitcoins.com/instant-bitcoins/?action=sell&country_code=US&amount=&currency=USD&place_country
=US&online_provider=CREDITCARD&find-offers=Search"
"btc" : 10650 ##Default BTC price
}
``` 
## Dependencies

```
pip3 install slackclient pandas
```

## Usage

```
./main.py
```
