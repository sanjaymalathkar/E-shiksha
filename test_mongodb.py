import pymongo

# Connect to MongoDB
try:
    client = pymongo.MongoClient("mongodb://localhost:27017/")

    # Test connection
    client.admin.command('ping')
    print("Connected to MongoDB successfully!")

    # List databases
    print("\nDatabases:")
    for db in client.list_databases():
        print(f"- {db['name']}")

    # Check e_shiksha database
    db = client["e_shiksha"]

    # List collections
    print("\nCollections in e_shiksha:")
    for collection in db.list_collection_names():
        print(f"- {collection}")

    # Count documents in each collection
    print("\nDocument counts:")
    for collection in db.list_collection_names():
        count = db[collection].count_documents({})
        print(f"- {collection}: {count} documents")

except Exception as e:
    print(f"Error connecting to MongoDB: {str(e)}")
