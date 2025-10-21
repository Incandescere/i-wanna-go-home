# Import libs
import requests
from datetime import datetime, timezone, timedelta
from math import floor
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
import os
import boto3
from botocore.exceptions import ClientError
import json


# Gets secrets from secrets manager
def getSecrets():
    # Create a Secrets Manager client
    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager',
        region_name='ap-southeast-1'
    )
    try:
        get_secret_value_response = client.get_secret_value(
            SecretId="iwgh"
        )
    except ClientError as e:
        # For a list of exceptions thrown, see
        # https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_GetSecretValue.html
        raise e
    secrets = get_secret_value_response['SecretString']
    return json.loads(secrets)

# ========================================================================================================
# Connects to mongodb atlas client
def getMongoCollection(secrets):
    # Establish mongodb atlas connection
    dbUser = secrets.get("iwgh-mongo-db-username")
    dbPass = secrets.get("iwgh-mongo-db-password")
    uri = secrets.get("iwgh-mongo-conn-string").format(dbUser, dbPass)

    # Create a new client and connect to the server
    client = MongoClient(uri, server_api=ServerApi('1'))

    # Send a ping to confirm a successful connection
    try:
        client.admin.command('ping')
        print("DB Connection Check Success")
    except Exception as e:
        print(e)

    db = client["iwgh-db"]
    return db["iwgh-collection-subscriptions"]

# ========================================================================================================
# Main function called by handler at the bottom
def handler(event, context):

# Define helpers first
    def getSubById(id):
        try:
            result = collection.find_one({"_id": id})
            return result
        except Exception as e:
            print("getSubById: Get Exception")
            raise e

# --------------------------------------------------------------------------------------------------------
    
    def formatTime(time):
        return datetime.fromisoformat(time).strftime("%H:%M")

# --------------------------------------------------------------------------------------------------------
    
    def getDiffInMins(time):
        tz = timezone(timedelta(hours=8))
        delta = datetime.fromisoformat(time)-datetime.now(tz)
        if (delta.days < 0):
            return False

        if (floor(delta.seconds/60)) <= 0:
            return "< 1"
        else:
            return str(floor(delta.seconds/60))

# --------------------------------------------------------------------------------------------------------
    #Main function start
    secrets = getSecrets()
    collection = getMongoCollection(secrets)
    
    sub = getSubById(event["subId"])

    response = requests.get(
        "https://datamall2.mytransport.sg/ltaodataservice/v3/BusArrival",
        params={"BusStopCode": sub['busStopCode'], "ServiceNo": sub['serviceNo']},
        headers={"AccountKey": secrets.get("iwgh-lta-datamall-api-key")},
    )

    print(response.json())

    #Get bus arr timings in ISO format
    bus1arr = response.json()["Services"][0]["NextBus"]["EstimatedArrival"]
    bus2arr = response.json()["Services"][0]["NextBus2"]["EstimatedArrival"]
    bus3arr = response.json()["Services"][0]["NextBus3"]["EstimatedArrival"]

    # print(bus1arr)
    # print(bus2arr)
    # print(bus3arr)


    # Get bus arr timings in HH:mm
    bus1time = formatTime(bus1arr)
    bus2time = formatTime(bus2arr)
    bus3time = formatTime(bus3arr)

    # print(bus1time)
    # print(bus2time)
    # print(bus3time)


    # Get bus arr timings in mins
    diff1 = getDiffInMins(bus1arr)
    diff2 = getDiffInMins(bus2arr)
    diff3 = getDiffInMins(bus3arr)

    # print(diff1)
    # print(diff2)
    # print(diff3)


    #Format tele msg
    tgMsgFormat = "{}:\nBus {} arriving in {} min(s) [{}], and then in {} min(s) [{}]\nTo unsubscribe, text 'Unsub, {}'"
    if not diff1:
        tgMsg = tgMsgFormat.format(sub['description'], sub['serviceNo'], diff2, bus2time, diff3, bus3time, sub['_id'])
    else:
        tgMsg = tgMsgFormat.format(sub['description'], sub['serviceNo'], diff1, bus1time, diff2, bus2time, sub['_id'])

    print(tgMsg)


    # Other req params
    tgUrl = "https://api.telegram.org/bot{}/sendMessage".format(secrets.get("iwgh-telegram-api-key"))
    tgParams = {"chat_id": sub['chatId'], "text": tgMsg}


    # Check info
    print(tgMsg)
    # print(tgUrl)
    print(tgParams)

    requests.post(tgUrl, params = tgParams)
