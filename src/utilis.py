from Crypto import Random
from fastapi import HTTPException, status
from pymongo import MongoClient
import time
import hashlib
from loguru import logger

from consts import mongoUrl

Client = MongoClient(mongoUrl)
db = Client["englishWordsApp"]
users_collection = db["users"]

logger.add("utilsOut.log", diagnose=True)


def verify_user_info(info: str) -> str:
    print("start")
    name, password = info.split(" ")
    salt = get_user_salt(name)
    print(salt)
    hash_pass, salt = encrypt_data(password, salt=salt)
    logger.info(hash_pass)
    query = {"name": name, "password": hash_pass}
    user = users_collection.find_one(query)
    if user is None:
        logger.info(f"error:\n name: {name}, password: {password}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    return user["collection"]


def user_info(user_name):
    user_obj = users_collection.find_one({"name": user_name})
    user_collection = Client["usersDataBase"][user_obj["collection"]]
    info = {
        "privateName": user_obj["privateName"],
        "totalAmountWords": len(
            list(db["wordsObj"].find({"level": {"$gte": 1, "$lte": user_obj["level"]}}))
        ),
        "shouldLearn": len(list(user_collection.find({"alreadyKnow": False}))),
        "neverLearned": len(list(user_collection.find({"repetitions": -1}))),
        "startedPractice": len(
            list(user_collection.find({"repetitions": {"$ne": -1}}))
        ),
        "learnedPerfectly": len(
            list(user_collection.find({"repetitions": {"$gte": 5}}))
        ),
        "userLevel": user_obj["level"],
    }
    return info


def get_user_level(info: str):
    user_name, password = info.split(" ")
    user_obj = users_collection.find_one({"name": user_name})
    return user_obj["level"]


def get_user_salt(name):
    user = users_collection.find_one({"name": name})
    if user is None:
        logger.info("no user name found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    return bytes(user["salt"], "utf-8")


def get_unique_id(name: str) -> str:
    return name + str(int(time.time() * 1000000))


def filtering(word):
    forbidden = ["_id", "imageUrl", "sentences"]
    return word not in forbidden


def encrypt_data(plaintext, salt=None):
    if salt is None:
        salt = bytes(Random.get_random_bytes(16).hex(), "utf-8")
    plaintext = bytes(plaintext, "utf-8")
    s2 = hashlib.sha256(plaintext + salt)
    return s2.hexdigest(), salt.decode("utf-8")
