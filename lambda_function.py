import boto3
# import logging
from botocore.config import Config
# from botocore.exceptions import ClientError
# import os
import requests
import io
import json

def aws_client_init(region, service_type):
    # login aws wafv2
    my_config = Config(
        region_name=region,
    )

    aws_client = boto3.client(service_type,
                              config=my_config)
    return aws_client

def getWafIPSetID(ip_set_name, aws_client):
    print('WAF get IPSET ID start...')
    response_waf_id = aws_client.list_ip_sets(
        Scope='REGIONAL',
        # NextMarker='maintenance-test-acl',
        Limit=50
    )
    length = len(response_waf_id['IPSets'])
    ip_set_id = ''
    # print(response_waf_id)
    for i in range(0, length):
        if response_waf_id['IPSets'][i]['Name'] == ip_set_name:
            ip_set_id = response_waf_id['IPSets'][i]['Id']
    if not ip_set_id:
        print('Error: Can not find IPSET ID,please check IPSET name: ', ip_set_name)
        print('WAF get IPSET ID end,program end')
        exit()
    print('WAF get IPSET ID end')
    return ip_set_id

def getCMSWhiteList(cloudfront_ip_url):
    print("Get IP set from", cloudfront_ip_url)

    api_response = requests.get(cloudfront_ip_url).json()
    
    length = len(api_response['CLOUDFRONT_GLOBAL_IP_LIST'])
    print('globla ip length: ', length)
    update_ip = []
    for i in range(0, length):
        ip = api_response['CLOUDFRONT_GLOBAL_IP_LIST'][i].strip()
        update_ip.append(ip)

    length = len(api_response['CLOUDFRONT_REGIONAL_EDGE_IP_LIST'])
    print('EDGE ip length: ', length)
    for i in range(0, length):
        ip = api_response['CLOUDFRONT_REGIONAL_EDGE_IP_LIST'][i].strip()
        update_ip.append(ip)
    return list(dict.fromkeys(update_ip))

def getWafIPSet(ip_set_name, ip_set_id, aws_client):

    print("Get IP set from waf start...")

    # get current ip set 'lock token' and 'ip list'
    response_get_ip_set = aws_client.get_ip_set(
        Name=ip_set_name,
        Scope='REGIONAL',
        Id=ip_set_id
    )

    # print("get ip lock token")
    ip_set_lock_token = response_get_ip_set['LockToken']
    # print("get ip set")
    aws_ip_set = response_get_ip_set['IPSet']['Addresses']
    print("Get IP set from waf end")
    return aws_ip_set, ip_set_lock_token

def ipSetEqual(cloufront_ip_range, wafIPs):
    cloufront_ip_range.sort()
    wafIPs.sort()
    return "|".join(cloufront_ip_range) == "|".join(wafIPs)

def lambda_handler(event, context):
    # logging.root.setLevel(logging.DEBUG)

    # waf init
    aws_client_waf = aws_client_init('ap-southeast-1', 'wafv2')

    ip_set_name = 'CloudFront-ip'
    ip_set_id = getWafIPSetID(ip_set_name, aws_client_waf)
    wafIPs, token = getWafIPSet(ip_set_name, ip_set_id, aws_client_waf)
    print('ip_set id: ', ip_set_id)
    cloudfront_ip_url = 'https://d7uri8nf7uskq.cloudfront.net/tools/list-cloudfront-ips'
    cloufront_ip_range = getCMSWhiteList(cloudfront_ip_url)
    print('cloudfront ip range: ', cloufront_ip_range)
    if ipSetEqual(cloufront_ip_range, wafIPs):
        print("IP set is equal,no action")
    else:
        print("Update IP set to waf")
        response_update_ip_Set = aws_client_waf.update_ip_set(
            Name=ip_set_name,
            Scope='REGIONAL',
            Id=ip_set_id,
            Addresses=cloufront_ip_range,
            LockToken=token
        )
        print("IP set updated in waf: ", response_update_ip_Set)