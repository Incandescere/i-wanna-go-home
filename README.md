# I wanna go home

I wanna go home (IWGH) is a “reminder as a service” telegram bot that allows users to specify subscriptions for bus stop-bus service pairs in Singapore. It fetches info from LTA Datamall’s API and sends bus timings at the time(s) you set. No need to open bus apps and search for your preferred stop when the info can be sent to you.     

# Motivations

Honestly, I was just too lazy to search for when my bus would arrive when I wanted to go home from the office. 

Initially, I thought of creating just a function with hardcoded parameters and hosting on AWS lambda, but that was not scalable. So, I thought of ways to make this app available to others as well, by making this a subscribable ‘reminder-as-a-service’. 

# How it works/how to use

Simply find the bot on telegram @i_wanna_go_home_bot,  and start it. Send a message (with the specified format at the bottom) to create your first subscription. 

# Architecture

The application comprises of 

1. 2 functions on AWS lambda: 
    1. A generic reminder function
    2. A subscription handler function
2. Eventbridge Schedulers triggering the lambda functions (1 for the subscription handler, and 1 for each subscription)
3. A publicly hosted MongoDB Atlas Database

# Subscribe handler function

The subscription scheduler calls the subscription function once per hour. 

The subscription function does the following: 

1. Fetches the update list from the telegram bot API.
2. Parses the updates to check its a subscribe or unsubscribe request.
3. For each valid sub/unsub request, it then creates/deletes a database entry and an EventBridge scheduler. 
4.  Informs the user if their sub/unsub request is successful.  

# Reminder function

For each subscription, a new EventBridge scheduler will be created. This scheduler passes in a subscription ID parameter when it calls the generic reminder function. 

On invocation, the function will: 

1. Fetch subscription details from the MongoDB database. 
2. Call the LTA Datamall API for bus info specified in the subscription details and parse the response
3. Send a reminder message to the Chat ID specified in the subscription details. 

# Future Plans

- Error messages to telegram on unsuccessful sub/unsub messages
- ~~More human-readable cron expression for the subscription message~~
- Handle the /Start command

# Technical documentation

## Subscription message

A 5-part comma-separated message

```bash
<description>, <busStopNo>, <busServiceNos>, <time>, <dayOfWeek>
```

|  Parameter | Description | Format | Example |
| --- | --- | --- | --- |
| description | Custom name for this subscription | text | Go home from office |
| busStopNo | Bus stop number | 5-digit number | 55039 |
| busServiceNos | Bus service number(s) | 1 bus service number or multiple space-separated bus service numbers at the specified bus stop no | <86> OR <86 163 854>  |
| time | time in 24hr format  | 4 digit time of day in 24hr format | 1800 |
| dayOfWeek | Day(s) of week to trigger | 3-letter name of day, or range separated by a “-” | <mon> OR <tue-thu> |

## Unsubscription message

A 2-part comma separated message

```bash
Unsub, <subId>
```

|  Parameter | Remarks |
| --- | --- |
| Unsub | Is case sensitive |
| subId | Subscription ID, which will be present in the reminder message |

## Changelog

### v1.0 (22 Oct 2025)

Initial release

### v1.1 (27 Oct 2025)

1. Changed subscription message to take in time and dayOfWeek instead of cron expression for ease of use and readability

### v1.2 (28 Oct 2025)

1. Updated application from taking in only 1 bus service number to taking in multiple space-separated bus service numbers