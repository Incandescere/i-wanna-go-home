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
import heapq


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
    print("GetSecrets ok" if len(secrets)>0 else "GetSecrets failed")
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
        raise e

    db = client["iwgh-db"]
    return db["iwgh-collection-subscriptions"]

# ========================================================================================================
    
def formatTime(time):
    return datetime.fromisoformat(time).strftime("%H:%M")

# ========================================================================================================

def getDiffInMins(time):
    tz = timezone(timedelta(hours=8))
    delta = datetime.fromisoformat(time)-datetime.now(tz)
    if (delta.days < 0):
        return False

    return str(floor(delta.seconds/60))

# ========================================================================================================
#Main function
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
    #Main function start
    secrets = getSecrets()
    collection = getMongoCollection(secrets)
    
    sub = getSubById(event["subId"])

    # Get bus arrivals
    pq = []
    failToFind = []
    busIndex = ["NextBus", "NextBus2", "NextBus3"]
    for service in sub["serviceNos"]:
        response = requests.get(
            "https://datamall2.mytransport.sg/ltaodataservice/v3/BusArrival",
            params={"BusStopCode": sub['busStopCode'], "ServiceNo": service},
            headers={"AccountKey": userdata.get('LtaDatamall')},
        )

        # Failed to find service in subscription
        if not response.json()["Services"]:
            failToFind.append(service)
            continue

        for i in busIndex:
            busArr = response.json()["Services"][0][i]["EstimatedArrival"]
            # case where there is empty bus time
            if not busArr:
                continue

            arrivalTime = formatTime(busArr)
            arrivalMins = getDiffInMins(busArr)
            # case where time is before curr time
            if not arrivalMins:
                continue
            pqObj = {
                "busService": service,
                "arrivalTime": arrivalTime,
                "arrivalMins": arrivalMins
            }
            # print(pqObj)
            heapq.heappush(pq, (int(arrivalMins), int(service), pqObj))

    # Format tg msg    
    tgMsg = "{}".format(sub['description'])
    if len(pq) == 0:
        tgMsg = "No more busses"
    else:
        for i in range(5):
            nextBus = heapq.heappop(pq)[2]
            arrivalMins = nextBus["arrivalMins"] if int(nextBus["arrivalMins"]) > 0 else "< 1"
            line = "{} coming in {} mins ({})".format(nextBus["busService"], arrivalMins, nextBus["arrivalTime"])
            tgMsg = tgMsg + "\n" + line
            if len(pq) == 0:
                break

        if len(failToFind)>0:
            line = "Could not find bus service(s): "
            for i in failToFind:
                line = line + str(i) + ", "
            line = line[:-2]
            tgMsg = tgMsg + "\n\n" + line



    tgMsg += "\n\nSend \"Unsub, {}\" to unsubscribe".format(sub['_id'])

    # Other req params
    tgUrl = "https://api.telegram.org/bot{}/sendMessage".format(secrets.get("iwgh-telegram-api-key"))
    tgParams = {"chat_id": sub['chatId'], "text": tgMsg}


    # Check info
    print("Sending message: {}".format(tgMsg))
    # print(tgParams)
    response = requests.post(tgUrl, params = tgParams)
    print("Reminder sent successfully" if response.status_code==200 else "Reminder sending failed")
