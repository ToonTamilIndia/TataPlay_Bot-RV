import re
import json
import requests
from bot.config import tplay_path
from bot.helpers.utils import timestamp_to_datetime
from datetime import datetime, timedelta
from dateutil import parser
import pytz
import random


def within_12_hours(timestamp):

    provided_time = parser.isoparse(timestamp)
    provided_time = provided_time.astimezone(pytz.timezone('Asia/Kolkata'))
    
    current_time = datetime.now(pytz.timezone('Asia/Kolkata'))
    
    time_difference = current_time - provided_time

    return time_difference < timedelta(hours=1)

class TPLAY_API():
    API_ALL_CHANNELS = "https://kong-tatasky.videoready.tv/content-detail/pub/api/v1/channels?limit=1000"
    FETCHER = "https://yuvraj.fun/tp/fetcher.json"
    HMAC = "https://yuvraj.fun/tp/hmac.json?random={}".format(random.randint(10,99))
    HMAC_v2 = "https://yuvraj.fun/tp/hmac.json?random={}".format(random.randint(10,99)




    def get_hmac_v2(self):
        response = requests.get(self.HMAC).json()['data']
        return response['hmac']['hdnea']['value']

    def get_hmac(self):
        response = requests.get(self.HMAC)
        response.raise_for_status()
        data = response.json()
        hdnea = data['data']['hmac']['hdnea']['value']
        res = hdnea.split('exp=', 1)[1]
        return res

    def get_data(self):
      

        data = [channel for channel in self.channels['data']['channels'] if (channel.get('name').replace(" ", "").lower() == self.channel_slug.lower())][0]

        if data:
            return data
        else:
            raise Exception("Channel slug didn't matched with the channel in the tplay data. Please check and try again!...")

    def get_channelId(self):
        all_channels = requests.get(self.API_ALL_CHANNELS).json()['data']['list']

        try:
            data = [channel for channel in all_channels if channel.get('title').replace("!" , "").replace("Hindi" , "").replace(" ", "") == self.channel_slug][0]
            return data.get('id')
        except Exception:
            raise Exception("Enable to extract channelId from channelSlug")

