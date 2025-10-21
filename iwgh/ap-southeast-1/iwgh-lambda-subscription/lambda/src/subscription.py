# Import
import requests
import transaction
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
import boto3
import os
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
        raise e

    db = client["iwgh-db"]
    return db["iwgh-collection-subscriptions"]

# ========================================================================================================
# Inform sub/unsub success fn
def informSubscribeSuccess(updateId, chatId, subMsgArr):
    tgMsg = """
    Subscription for {} successful!\nBus {} at stop {}\n\nTo Unsub, send 'Unsub, {}'""".format(subMsgArr[0], subMsgArr[2], subMsgArr[1], updateId)
    print(tgMsg)
    tgUrl = "https://api.telegram.org/bot{}/sendMessage".format(secrets.get("iwgh-telegram-api-key"))
    tgParams = {"chat_id": chatId, "text": tgMsg}
    requests.get(tgUrl, params = tgParams)

def informUnsubscribeSuccess(desc, chatId):
    tgMsg = "Successfully unsubscribed from \"{}\"".format(desc)
    print(tgMsg)
    tgUrl = "https://api.telegram.org/bot{}/sendMessage".format(secrets.get("iwgh-telegram-api-key"))
    tgParams = {"chat_id": chatId, "text": tgMsg}
    requests.get(tgUrl, params = tgParams)

# ========================================================================================================
#Main function
def handler(event, context):
# Define helpers first
    # Get update list from bot link
    def getUpdateList():
        response = requests.get(
            "https://api.telegram.org/bot{}/getUpdates".format(secrets.get("iwgh-telegram-api-key"))
        )
        return response.json()["result"]

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
            return result if result is not None else False
        except Exception as e:
            print("dbDelete: Delete Exception")
            raise e

# --------------------------------------------------------------------------------------------------------

    def clearUpdates(maxOffset):
        if maxOffset > 0:
            requests.get(
                "https://api.telegram.org/bot{}/getUpdates?offset={}".format(secrets.get("iwgh-telegram-api-key"), maxOffset+1)
            )

# --------------------------------------------------------------------------------------------------------

    scheduler = boto3.client('scheduler', region_name='ap-southeast-1')
    def createCron(id, cronExp):
        # Create cron

        scheduler.create_schedule(
            Name='iwgh-schedule-subscription-'+id,
            ScheduleExpression='cron({})'.format(cronExp),
            FlexibleTimeWindow={'Mode': 'OFF'},
            Target={
                'Arn': os.environ['reminderEbTargetArn'],
                'RoleArn': os.environ['reminderEbTargetRoleArn'],
                'Input': json.dumps({
                    'id': id
                })
            }
        )

# --------------------------------------------------------------------------------------------------------

    def deleteCron(id):
        scheduler.delete_schedule(
            Name='iwgh-schedule-subscription-'+id
        )

# --------------------------------------------------------------------------------------------------------

    def subscribe(updateId, chatId, subMsgArr):
        subData = {
            "_id": str(updateId),
            "description": subMsgArr[0],
            "busStopCode": subMsgArr[1],
            "serviceNo": subMsgArr[2],
            "chatId": str(chatId),
            "cronExp": subMsgArr[3]
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
            return deletedObject or False
        except Exception as e:
            transaction.abort()
            raise e

# --------------------------------------------------------------------------------------------------------

    #Get list of updates from tele
    updateList = getUpdateList()
    maxOffset = 0
    for listItem in updateList:
        updateId = listItem["update_id"]
        maxOffset = max(maxOffset, updateId)
        chatId = listItem["message"]["chat"]["id"]
        subMsgArr= listItem["message"]["text"].split(",")
        subMsgArr = [x.strip() for x in subMsgArr]

        # check if msgs are valid sub/unsub reqs
        validSubMsg = len(subMsgArr) == 4
        validUnsubMsg = len(subMsgArr) == 2 and subMsgArr[0] == 'Unsub'

        # print()
        # print("Curr submsgarr: ")
        # print(subMsgArr)
        # print()

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
                print(subscribeResult)
                if subscribeResult:
                    informSubscribeSuccess(updateId, chatId, subMsgArr)
            except Exception as e:
                print("Subscribe flow failed")

        # Unsubscribe Flow
        if unsubSubscribed and validUnsubMsg:
            print("Try unsubscribe flow...")
            try:
                print(subMsgArr)
                unsubscribeResult = unsubscribe(subMsgArr[1])
                print(unsubscribeResult)
                if unsubscribeResult != False:
                    informUnsubscribeSuccess(unsubscribeResult["description"], chatId)
            except Exception as e:
                print("Unsubscribe flow failed")

        print("=================================================")
    
    clearUpdates(maxOffset)
