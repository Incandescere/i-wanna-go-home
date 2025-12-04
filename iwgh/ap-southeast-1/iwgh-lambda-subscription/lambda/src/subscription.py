# Import
import requests
import transaction
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
import boto3
import os
import json

# Test subscribe pipeline
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
# Convert text to cron exp
def textToCron(time,days):
    time = time.strip() 
    days = days.strip().upper()

    hr = int(time[:2])
    min = int(time[-2:])
    if len(time) != 4 or (hr<0 or hr>23) or (min<0 or min>59):
        return False

    cronExp = "{} {} ? * {} *".format(min, hr, days)
    return cronExp

# ========================================================================================================
#Main function
def handler(event, context):
# Define helpers first

    # Get update list from bot link
    def getUpdateList():
        response = requests.get(
            "https://api.telegram.org/bot{}/getUpdates".format(secrets.get("iwgh-telegram-api-key"))
        )
        updateListLen = len(response.json()["result"])
        print("GetUpdateList: {}".format(updateListLen))
        return response.json()["result"] if updateListLen > 0 else None

# --------------------------------------------------------------------------------------------------------

    def dbInsert(subData):
        try:
            result = collection.insert_one(subData)
            print(result)
        except Exception as e:
            print("dbInsert: Insert Exception")
            raise e

# --------------------------------------------------------------------------------------------------------

    def dbDelete(id):
        try:
            result = collection.find_one_and_delete({"_id": id})
            print(result)
            return result if result is not None else False
        except Exception as e:
            print("dbDelete: Delete Exception")
            raise e

# --------------------------------------------------------------------------------------------------------

    def clearUpdates(maxOffset):
        if maxOffset > 0:
            response = requests.post(
                "https://api.telegram.org/bot{}/getUpdates?offset={}".format(secrets.get("iwgh-telegram-api-key"), maxOffset+1)
            )
        print("ClearUpdatesSuccess {}".format(maxOffset) if response.status_code==200 else "ClearUpdatesFailed")

# --------------------------------------------------------------------------------------------------------

    scheduler = boto3.client('scheduler', region_name='ap-southeast-1')
    def createCron(id, cronExp):
        scheduler.create_schedule(
            Name='iwgh-schedule-subscription-'+id,
            ScheduleExpression='cron({})'.format(cronExp),
            ScheduleExpressionTimezone='Asia/Singapore',
            FlexibleTimeWindow={'Mode': 'OFF'},
            Target={
                'Arn': os.environ['reminderEbTargetArn'],
                'RoleArn': os.environ['reminderEbTargetRoleArn'],
                'Input': json.dumps({
                    'subId': id
                })
            }
        )
        print("CreateCron success")

# --------------------------------------------------------------------------------------------------------

    def deleteCron(id):
        scheduler.delete_schedule(
            Name='iwgh-schedule-subscription-'+id
        )
        print("DeleteCron success")

# --------------------------------------------------------------------------------------------------------

    def subscribe(updateId, chatId, subMsgArr):
        cronExp = textToCron(subMsgArr[3], subMsgArr[4])
        # print(cronExp)
        serviceNos = list(set(subMsgArr[2].split()))
        subData = {
            "_id": str(updateId),
            "description": subMsgArr[0],
            "busStopCode": subMsgArr[1],
            "serviceNos": serviceNos,
            "chatId": str(chatId),
            "cronExp": cronExp
        }
        # Insert into db
        try:
            # Writing to mongodb connection
            try:
                dbInsert(subData)
            except Exception as e:
                print("Subscribe: Insert Exception")
                raise e
            # Creating an eventbridge cron job
            createCron(str(updateId), subData["cronExp"])
            transaction.commit()
            print("SubscribeSucess")
            return True
        except Exception as e:
            transaction.abort()
            raise e

# --------------------------------------------------------------------------------------------------------

    def unsubscribe(id):
        deletedObject = {}
        try:
            try:
                deletedObject = dbDelete(id)
            except Exception as e:
                print("Unsubscribe: Delete Exception")
                print(e)
                raise e
            # Deleting an eventbridge cron job
            deleteCron(id)
            transaction.commit()
            print("UnsubscribeSuccess")
            return deletedObject or False
        except Exception as e:
            transaction.abort()
            raise e

# --------------------------------------------------------------------------------------------------------

    # Inform sub/unsub success fn
    def informSubscribeSuccess(updateId, chatId, subMsgArr):
        tgMsg = "Subscription for {} successful!\nBus(es) {} at stop {}\n\nTo Unsub, send 'Unsub, {}'".format(subMsgArr[0], subMsgArr[2], subMsgArr[1], updateId)
        print(tgMsg)
        tgUrl = "https://api.telegram.org/bot{}/sendMessage".format(secrets.get("iwgh-telegram-api-key"))
        tgParams = {"chat_id": chatId, "text": tgMsg}
        response = requests.post(tgUrl, params = tgParams)
        print("InformSubscribeSuccess ok" if response.status_code ==200 else "InformSubscribeSuccess failed")

    def informUnsubscribeSuccess(desc, chatId):
        tgMsg = "Successfully unsubscribed from \"{}\"".format(desc)
        print(tgMsg)
        tgUrl = "https://api.telegram.org/bot{}/sendMessage".format(secrets.get("iwgh-telegram-api-key"))
        tgParams = {"chat_id": chatId, "text": tgMsg}
        response = requests.post(tgUrl, params = tgParams)
        print("InformUnsubscribeSuccess ok" if response.status_code ==200 else "InformUnsubscribeSuccess failed")

# --------------------------------------------------------------------------------------------------------

    def sendWelcomeMsg(chatId):
        tgMsg = "Welcome to @i_wanna_go_home_bot\n\nTo subscribe, send '<description>, <busStopNo>, <busServiceNos>, <time>, <dayOfWeek>'\n\nFor more information, check out the project GitHub here: https://github.com/Incandescere/i-wanna-go-home"
        print(tgMsg)
        tgUrl = "https://api.telegram.org/bot{}/sendMessage".format(secrets.get("iwgh-telegram-api-key"))
        tgParams = {"chat_id": chatId, "text": tgMsg}
        response = requests.post(tgUrl, params = tgParams)
        print("SendWelcomeMsg ok" if response.status_code ==200 else "SendWelcomeMsg failed")

# --------------------------------------------------------------------------------------------------------

    #Get list of updates from tele
    secrets = getSecrets()

    updateList = getUpdateList()
    if updateList is None:
        return
    
    collection = getMongoCollection(secrets)

    maxOffset = 0
    for listItem in updateList:
        updateId = listItem["update_id"]
        maxOffset = max(maxOffset, updateId)
        chatId = listItem["message"]["chat"]["id"]
        subMsgArr = listItem["message"]["text"].split(",")
        subMsgArr = [x.strip() for x in subMsgArr]

        if len(subMsgArr) < 2: 
            if subMsgArr[0] == '/Start':
                sendWelcomeMsg(chatId)
            continue
        
        # check if msgs are valid sub/unsub reqs
        validSubMsg = len(subMsgArr) == 5
        validUnsubMsg = len(subMsgArr) == 2 and subMsgArr[0] == 'Unsub'

        # print('\n'+"Curr submsgarr: ")
        # print(subMsgArr+'\n')

        # check curr state of sub id
        subscribed = collection.find_one({"_id": updateId}) is not None
        unsubSubscribed = collection.find_one({"_id": subMsgArr[1]}) is not None

        # print("sub conditions")
        # print('subscribed? {}'.format(subscribed))
        # print('valid sub msg? {}'.format(validSubMsg))
        # print("unsub conditions")
        # print('unsub subscribed? {}'.format(unsubSubscribed))
        # print('valid unsub msg? {}'.format(validUnsubMsg))

        #Subscribe Flow
        if not subscribed and validSubMsg:
            print("Try subscribe flow...")
            try:
                subscribeResult = subscribe(updateId, chatId, subMsgArr)
                if subscribeResult:
                    informSubscribeSuccess(updateId, chatId, subMsgArr)
            except Exception as e:
                print("Subscribe flow failed")
                print(e)

        # Unsubscribe Flow
        if unsubSubscribed and validUnsubMsg:
            print("Try unsubscribe flow...")
            try:
                unsubscribeResult = unsubscribe(subMsgArr[1])
                if unsubscribeResult != False:
                    informUnsubscribeSuccess(unsubscribeResult["description"], chatId)

            except Exception as e:
                print("Unsubscribe flow failed")
                print(e)

        print("=================================================")
    
    clearUpdates(maxOffset)
