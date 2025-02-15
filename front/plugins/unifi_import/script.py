#!/usr/bin/env python
# Inspired by https://github.com/stevehoek/Pi.Alert

# Example call
# python3 /home/pi/pialert/front/plugins/unifi_import/script.py username=pialert password=passw0rd host=192.168.1.1 site=default protocol=https port=8443 version='UDMP-unifiOS'
# python3 /home/pi/pialert/front/plugins/unifi_import/script.py username=pialert password=passw0rd host=192.168.1.1 sites=sdefault port=8443 verifyssl=false version=v5

from __future__ import unicode_literals
from time import strftime
import argparse
import logging
import pathlib
import os
import json
import sys
import requests
from requests import Request, Session, packages
from requests.packages.urllib3.exceptions import InsecureRequestWarning
from pyunifi.controller import Controller

# Add your paths here
sys.path.append("/home/pi/pialert/front/plugins")
sys.path.append('/home/pi/pialert/pialert')

from plugin_helper import Plugin_Object, Plugin_Objects
from logger import mylog

CUR_PATH = str(pathlib.Path(__file__).parent.resolve())
LOG_FILE = os.path.join(CUR_PATH, 'script.log')
RESULT_FILE = os.path.join(CUR_PATH, 'last_result.log')

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

# Workflow

def main():
    
    mylog('verbose', ['[UNFIMP] In script'])

    
    # init global variables
    global UNIFI_USERNAME, UNIFI_PASSWORD, UNIFI_HOST, UNIFI_SITES, PORT, VERIFYSSL, VERSION


    parser = argparse.ArgumentParser(description='Import devices from a UNIFI controller')

    parser.add_argument('username',  action="store",  help="Username used to login into the UNIFI controller")
    parser.add_argument('password',  action="store",  help="Password used to login into the UNIFI controller")
    parser.add_argument('host',  action="store",  help="Host url or IP address where the UNIFI controller is hosted (excluding http://)")
    parser.add_argument('sites',  action="store",  help="Name of the sites (usually 'default', check the URL in your UniFi controller UI). Separated by comma (,) if passing multiple sites")
    parser.add_argument('port',  action="store",  help="Usually 8443")
    parser.add_argument('verifyssl',  action="store",  help="verify SSL certificate [true|false]")
    parser.add_argument('version',  action="store",  help="The base version of the controller API [v4|v5|unifiOS|UDMP-unifiOS]")

    values = parser.parse_args()

    # parse output
    plugin_objects = Plugin_Objects(RESULT_FILE)

    
    mylog('verbose', [f'[UNFIMP] Check if all login information is available: {values}'])

    if values.username and values.password and values.host and values.sites:

        UNIFI_USERNAME = values.username.split('=')[1]
        UNIFI_PASSWORD = values.password.split('=')[1]
        UNIFI_HOST = values.host.split('=')[1]
        UNIFI_SITES = values.sites.split('=')[1]
        PORT = values.port.split('=')[1]
        VERIFYSSL = values.verifyssl.split('=')[1]
        VERSION = values.version.split('=')[1]

        plugin_objects = get_entries(plugin_objects)

    plugin_objects.write_result_file()
    

    mylog('verbose', [f'[UNFIMP] Scan finished, found {len(plugin_objects)} devices'])

# .............................................

def get_entries(plugin_objects):
    global VERIFYSSL

    sites = []

    if ',' in UNIFI_SITES:
        sites = UNIFI_SITES.split(',')

    else:
        sites.append(UNIFI_SITES)

    if (VERIFYSSL.upper() == "TRUE"):
        VERIFYSSL = True
    else:
        VERIFYSSL = False

    for site in sites:

        c = Controller(UNIFI_HOST, UNIFI_USERNAME, UNIFI_PASSWORD, port=PORT, version=VERSION, ssl_verify=VERIFYSSL, site_id=site)
        
        mylog('verbose', [f'[UNFIMP] Identify Unifi Devices'])
        # get all Unifi devices
        for ap in c.get_aps():

            # mylog('verbose', [f'{json.dumps(ap)}'])

            deviceType = ''
            if (ap['type'] == 'udm'):
                deviceType = 'Router'
            elif (ap['type'] == 'usg'):
                deviceType = 'Router'
            elif (ap['type'] == 'usw'):
                deviceType = 'Switch'
            elif (ap['type'] == 'uap'):
                deviceType = 'AP'

            name = get_unifi_val(ap, 'name')
            hostName = get_unifi_val(ap, 'hostname')

            name = set_name(name, hostName)

            plugin_objects.add_object(
                primaryId=ap['mac'],
                secondaryId=get_unifi_val(ap, 'ip'),
                watched1=name,
                watched2='Ubiquiti Networks Inc.',
                watched3=deviceType,
                watched4=ap['state'],
                extra=get_unifi_val(ap, 'connection_network_name')
            )

        
        mylog('verbose', [f'[UNFIMP] Found {len(plugin_objects)} Unifi Devices'])
        

        online_macs = set()

        # get_clients() returns all clients which are currently online.
        for cl in c.get_clients():

            # mylog('verbose', [f'{json.dumps(cl)}'])
            online_macs.add(cl['mac'])

        
        mylog('verbose', [f'[UNFIMP] Found {len(plugin_objects)} Online Devices'])

        # get_users() returns all clients known by the controller
        for user in c.get_users():

            mylog('verbose', [f'{json.dumps(user)}'])

            name = get_unifi_val(user, 'name')
            hostName = get_unifi_val(user, 'hostname')

            name = set_name(name, hostName)

            status = 1 if user['mac'] in online_macs else 0

            if status == 1:

                ipTmp = get_unifi_val(user, 'last_ip')

                if ipTmp == 'null':
                    ipTmp = get_unifi_val(user, 'fixed_ip')

                plugin_objects.add_object(
                    primaryId=user['mac'],
                    secondaryId=ipTmp,
                    watched1=name,
                    watched2=get_unifi_val(user, 'oui'),
                    watched3='Other',
                    watched4=status,
                    extra=get_unifi_val(user, 'last_connection_network_name')
                )

    
    mylog('verbose', [f'[UNFIMP] Found {len(plugin_objects)} Clients overall'])

    return plugin_objects

# -----------------------------------------------------------------------------
def get_unifi_val(obj, key):

    res = ''

    res = obj.get(key, None)

    if res not in ['','None', None]:
        return res


    return 'null'

# -----------------------------------------------------------------------------

def set_name(name: str, hostName: str) -> str:

    if name != 'null':
        return name

    elif name == 'null' and hostName != 'null':
        return hostName

    else:
        return 'null'

#===============================================================================
# BEGIN
#===============================================================================
if __name__ == '__main__':
    main()