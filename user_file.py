from pymongo import MongoClient

# MongoDB connection URI (replace with your own credentials)
MONGO_URI = "mongodb+srv://nithin:nithin@cluster0.ohw9t2m.mongodb.net/Foodie?retryWrites=true&w=majority&appName=Cluster0"

# Function to initialize MongoDB connection
def get_database():
    client = MongoClient(MONGO_URI)
    return client.get_database()

# Function to read data from a specific collection
def read_data(collection_name):
    db = get_database()
    collection = db[collection_name]
    return collection

# Function to write data to a specific collection
def write_data(collection_name, data):
    db = get_database()
    collection = db[collection_name]
    collection.insert_one(data)
