#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# <bitbar.title>Tesla BitBar</bitbar.title>
# <bitbar.version>v1.0</bitbar.version>
# <bitbar.author>therippa@gmail.com</bitbar.author>
# <bitbar.author.github>therippa</bitbar.author.github>
# <bitbar.desc>Control your Tesla from the menubar</bitbar.desc>
# <bitbar.image>https://i.imgur.com/XbwiemY.png</bitbar.image>
# <bitbar.dependencies>python</bitbar.dependencies>
# <bitbar.abouturl>https://github.com/therippa/tesla-bitbar</bitbar.abouturl>
#
# by therippa@gmail.com

try: # Python 3
    from urllib.parse import urlencode
    from urllib.request import Request, urlopen, build_opener
    from urllib.request import ProxyHandler, HTTPBasicAuthHandler, HTTPHandler
    from urllib.request import HTTPError # <- is this right???
except: # Python 2
    from urllib import urlencode
    from urllib2 import Request, urlopen, build_opener
    from urllib2 import ProxyHandler, HTTPBasicAuthHandler, HTTPHandler
    from urllib2 import HTTPError
import json
import sys, os
import datetime
import calendar
import base64
import keyring
import time
from pprint import pprint

USE_EMOJI=True

TEMP_UNIT='F' # 'F' or whatever else, it'll end up 'C'

VEHICLES = { 
    # map vehicle ID numbers to real names
    #'012345': 'Example Vehicle Name',
}

# ----------------------------------
# Thank you to Greg Glockner for the code below - https://github.com/gglockner/teslajson
# ----------------------------------

class Connection(object):
    """Connection to Tesla Motors API"""
    def __init__(self,
            email='',
            password='',
            access_token='',
            proxy_url = '',
            proxy_user = '',
            proxy_password = ''):
        """Initialize connection object
        
        Sets the vehicles field, a list of Vehicle objects
        associated with your account
        Required parameters:
        email: your login for teslamotors.com
        password: your password for teslamotors.com
        
        Optional parameters:
        access_token: API access token
        proxy_url: URL for proxy server
        proxy_user: username for proxy server
        proxy_password: password for proxy server
        """
        self.proxy_url = proxy_url
        self.proxy_user = proxy_user
        self.proxy_password = proxy_password
        tesla_client = {
            'v1': {
                'id': 'e4a9949fcfa04068f59abb5a658f2bac0a3428e4652315490b659d5ab3f35a9e', 
                'secret': 'c75f14bbadc8bee3a7594412c31416f8300256d7668ea7e6e7f06727bfb9d220', 
                'baseurl': 'https://owner-api.teslamotors.com', 
                'api': '/api/1/'
            }
        }
        current_client = tesla_client['v1']
        self.baseurl = current_client['baseurl']
        self.api = current_client['api']
        self.access_token = None
        self.expiration = 0
        if access_token:
            self.__sethead(access_token)
        else:
            self.oauth = {
                "grant_type" : "password",
                "client_id" : current_client['id'],
                "client_secret" : current_client['secret'],
                "email" : email,
                "password" : password }

        # This is now a vechicles() function
        #self.vehicles = [Vehicle(v, self) for v in self.get('vehicles')['response']]
   
    def vehicles(self):
        return [Vehicle(v, self) for v in self.get('vehicles')['response']]

    def get_token(self):
        if self.access_token and self.expiration < time.time():
            return self.access_token

        try:
            auth = self.__open("/oauth/token", data=self.oauth)
        except HTTPError as e:
            # Typically, this means non 200 response code
            return None

        if 'access_token' in auth and auth['access_token']:
            self.access_token = auth['access_token']
            self.expiration = int(time.time()) + auth['expires_in'] - 86400
            return self.access_token

        return None


    def get(self, command):
        """Utility command to get data from API"""
        return self.post(command, None)
    
    def post(self, command, data={}):
        """Utility command to post data to API"""
        now = time.time()
        if now > self.expiration:
            auth = self.__open("/oauth/token", data=self.oauth)
            self.__sethead(auth['access_token'],
                           auth['created_at'] + auth['expires_in'] - 86400)
        return self.__open("%s%s" % (self.api, command), headers=self.head, data=data)
    
    def __sethead(self, access_token, expiration=float('inf')):
        """Set HTTP header"""
        self.access_token = access_token
        self.expiration = expiration
        self.head = {"Authorization": "Bearer %s" % access_token}
    
    def __open(self, url, headers={}, data=None, baseurl=""):
        """Raw urlopen command"""
        if not baseurl:
            baseurl = self.baseurl
        req = Request("%s%s" % (baseurl, url), headers=headers)
        try:
            req.data = urlencode(data).encode('utf-8') # Python 3
        except:
            try:
                req.add_data(urlencode(data)) # Python 2
            except:
                pass

        # Proxy support
        if self.proxy_url:
            if self.proxy_user:
                proxy = ProxyHandler({'https': 'https://%s:%s@%s' % (self.proxy_user,
                                                                     self.proxy_password,
                                                                     self.proxy_url)})
                auth = HTTPBasicAuthHandler()
                opener = build_opener(proxy, auth, HTTPHandler)
            else:
                handler = ProxyHandler({'https': self.proxy_url})
                opener = build_opener(handler)
        else:
            opener = build_opener()
        resp = opener.open(req)
        charset = resp.info().get('charset', 'utf-8')
        return json.loads(resp.read().decode(charset))
        

class Vehicle(dict):
    """Vehicle class, subclassed from dictionary.
    
    There are 3 primary methods: wake_up, data_request and command.
    data_request and command both require a name to specify the data
    or command, respectively. These names can be found in the
    Tesla JSON API."""
    def __init__(self, data, connection):
        """Initialize vehicle class
        
        Called automatically by the Connection class
        """
        super(Vehicle, self).__init__(data)
        self.connection = connection
    
    def data_request(self, name):
        """Get vehicle data"""
        result = self.get('data_request/%s' % name)
        return result['response']
    
    def wake_up(self):
        """Wake the vehicle"""
        return self.post('wake_up')
    
    def command(self, name, data={}):
        """Run the command for the vehicle"""
        return self.post('command/%s' % name, data)
    
    def get(self, command):
        """Utility command to get data from API"""
        return self.connection.get('vehicles/%i/%s' % (self['id'], command))
    
    def post(self, command, data={}):
        """Utility command to post data to API"""
        return self.connection.post('vehicles/%i/%s' % (self['id'], command), data)

def get_name(id):
    # check name mapping array for humanized vehicle names
    if id in VEHICLES:
        return VEHICLES[id]
    else:
        return id

def convert_temp(temp):
    if TEMP_UNIT == 'F':
        return (temp * 1.8) + 32
    else:
        return temp

def prompt_login():
    for attempt in range(3):
        sys.stdout.write("\ntesla.com username (will not be saved): ")
        username = sys.stdin.readline()

        sys.stdout.write("tesla.com password (will not be saved): ")
        os.system("stty -echo")  # Don't echo typed characters to terminal
        password = sys.stdin.readline()
        os.system("stty echo")   # Echo characters to terminal, as normal

        sys.stdout.write("\nChecking...")
        sys.stdout.flush()

        c = Connection(username, password)
        access_token = c.get_token()

        if not access_token:
            print ("Access denied")
            time.sleep(0.5)
            continue

        tesla_access_token=keyring.set_password('tesla-bitbar', 'access-token', access_token)
        print ('Success!')
        print ("\nType \"exit\" and hit enter to close this window")
        return

    print ("Sorry, double check your username and password then try again")
    print ("\nType \"exit\" and hit enter to close this window")


def abort_credentials():
    print ('Click to login | refresh=true terminal=true bash="%s" param1=login' % (sys.argv[0]))

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "login":
        prompt_login()
        return

    # print menu - below is icon.png encoded as base64
    print ('|image=iVBORw0KGgoAAAANSUhEUgAAACwAAAAsCAYAAAAehFoBAAAABGdBTUEAALGPC/xhBQAAACBjSFJNAAB6JgAAgIQAAPoAAACA6AAAdTAAAOpgAAA6mAAAF3CculE8AAAACXBIWXMAABYlAAAWJQFJUiTwAAABWWlUWHRYTUw6Y29tLmFkb2JlLnhtcAAAAAAAPHg6eG1wbWV0YSB4bWxuczp4PSJhZG9iZTpuczptZXRhLyIgeDp4bXB0az0iWE1QIENvcmUgNS40LjAiPgogICA8cmRmOlJERiB4bWxuczpyZGY9Imh0dHA6Ly93d3cudzMub3JnLzE5OTkvMDIvMjItcmRmLXN5bnRheC1ucyMiPgogICAgICA8cmRmOkRlc2NyaXB0aW9uIHJkZjphYm91dD0iIgogICAgICAgICAgICB4bWxuczp0aWZmPSJodHRwOi8vbnMuYWRvYmUuY29tL3RpZmYvMS4wLyI+CiAgICAgICAgIDx0aWZmOk9yaWVudGF0aW9uPjE8L3RpZmY6T3JpZW50YXRpb24+CiAgICAgIDwvcmRmOkRlc2NyaXB0aW9uPgogICA8L3JkZjpSREY+CjwveDp4bXBtZXRhPgpMwidZAAACQ0lEQVRYCe2XTUtVURSGrx+D/KJAMAxs4GcDnehAii4N/A9hREENFJzmpH+hkxo3UME/oKBNEowiBMtm6sSaFRWEEWn1vHA2bDb7WvfedThe2Ase9vda7153n33PKZWSpQykDKQMpAwUmYGmGoM3s24UJmEQBqAfuqEzg6L0PeMz5SEcwD68gj34DVVZNYL78HwbpuAGXARnp1SOQMKOMyhK7RnaiNa3gLNvVLbhOayC1v/T/kfwHF7uwnXQ/BN4Ay9gC5Q5mUS9BQnx7RKNMfgEWq9fogy3YAJa4Q+8hCV4AnXZMquVwQ24B8NwH56CBGoDCig0x8+i6pvZmMY1dxe01vlSqXWKsQJ12xU8DMEdWAdfoBPqlwvMcbZIxR8L6/K1BtOgGIplYrN4CYOprYBf4AMoQ27OA+oPvbbGPoLmVtrwDGOmNo+3XyBRr+EmXABneuqd4J/UhWvvuEmUbVAG+dC4fD6CXGwcrzpvOseh6fw5gWH5LJxMewTkSz4LscdEDYW6tlkGmw23phujkr2rNFBk/1WCu4yGZW+Rws6K/TUiWn8YZmZ5JCQqdixifTVvwFpw7KzG+s6N4Fg2G05wbBM1Z9h6YRcO9Y7rbgnVO6yDWPs79ATvWzu3fuikzz+z5schD8G+SF+8SbIbTrDJrgMn12i7hy72VhdML76pz6IfoI9R819QH4DWpq+L95lTXWumlodgCdTDpmNhbnkJ9m8KU9F5CTa/zkx3HXHWQ9/lSH/qShlIGUgZSBlo8Az8BUQapSzDgvJzAAAAAElFTkSuQmCC')     
    print ('---')

    tesla_access_token=keyring.get_password('tesla-bitbar', 'access-token')
    if not tesla_access_token:
        abort_credentials()
        return

    # create connection to tesla account
    c = Connection(access_token = tesla_access_token)

    try:
        vehicles = c.vehicles()
    except HTTPError as e:
        if e.code == 401:
            abort_credentials()
            return
        raise

    # see if args are passed, if so, pass commands and bail
    if len(sys.argv) > 1:
        v = vehicles[int(sys.argv[1])]
        v.wake_up()
        if sys.argv[2] != "wakeup":
            v.command(sys.argv[2])
        return

    # only do submenu if multiple vehicles
    prefix = ''
    if len(vehicles) > 1:
        prefix = '--'

    battery_str = "Battery:"
    charging_str = "Charging:"
    if USE_EMOJI:
        battery_str = ":battery:"
        charging_str = ":electric_plug:"

    # loop through vehicles, print menu with relevant info       
    for i, vehicle in enumerate(vehicles):
        if prefix:
            print get_name(vehicle['display_name'])

        if vehicle['state'] != "online" and vehicle['state'] != "driving":
            print ('%sState: %s| color=black' %  (prefix, vehicle['state']))
            print ('%sWakeup | refresh=true terminal=false bash="%s" param1=%s param2=wake_up' % (prefix, sys.argv[0], str(i)))
            print ('%sStart HVAC | refresh=true terminal=false bash="%s" param1=%s param2=auto_conditioning_start' % (prefix, sys.argv[0], str(i)))
        else:
            charge_state = vehicle.data_request('charge_state')
            climate_state = vehicle.data_request('climate_state')
            drive_state = vehicle.data_request('drive_state')

            print ('%s%s %s%%| color=black' % (prefix, battery_str, str(charge_state['battery_level'])))
            
            # The default charge state text
            pretty_charge_state = charge_state['charging_state']

            if charge_state['charging_state'] == "Charging":
                # Calculate the wattage ourself for more signifiant digits
                v = charge_state['charger_voltage']
                a = charge_state['charger_actual_current']
                if v and a:
                    rate = float(v * a) / 1000.0
                else:
                    rate = 0
                added = charge_state['charge_energy_added']
                pretty_charge_state = "+%0.2f kWh @ %0.2f kW" % (added, rate)
                try:
                    ttf = float(charge_state['time_to_full_charge'])
                    if ttf > 1.4:
                        pretty_charge_state += ", %0.1f hours remaining" % (ttf)
                    else:
                        pretty_charge_state += ", %d min remaining" % (ttf * 60.0)
                except Exception:
                    pass
            elif charge_state['charge_port_latch'] != "Engaged":
                pretty_charge_state = "Unplugged"
            else:
                if charge_state['scheduled_charging_pending']:
                    pretty_charge_state = "Scheduled"

            print ('%s%s %s| color=black' % (prefix, charging_str, pretty_charge_state))
            print ('%s---' % prefix)
            try:
                print ('%sInside Temp: %.1f°| color=black' % (prefix, convert_temp(climate_state['inside_temp'])))
            except:
                print ('%sInside Temp: Unavailable' % prefix)
            try:
                print ('%sOutside Temp: %.1f°| color=black' % (prefix, convert_temp(climate_state['outside_temp'])))
            except:
                print ('%sOutside Temp: Unavailable' % prefix)

            if climate_state['is_climate_on']:
                print ('%sStop HVAC | refresh=true terminal=false bash="%s" param1=%s param2=auto_conditioning_stop' % (prefix, sys.argv[0], str(i)))
            else:
                print ('%sStart HVAC | refresh=true terminal=false bash="%s" param1=%s param2=auto_conditioning_start' % (prefix, sys.argv[0], str(i)))

            # GPS
            print ('%s---' % prefix)
            print ('%sGear: %s| color=black' % (prefix, drive_state['shift_state']))
            print ('%sOpen in Google Maps… | href=https://www.google.com/maps/preview?q=%f,%f' % (prefix, drive_state['latitude'], drive_state['longitude']))

if __name__ == '__main__':
    main()
