import pymongo

client = pymongo.MongoClient("mongodb://124.16.71.9:24217/", connect=False)
users = client['guoke']['users']
