import random
from datetime import datetime
from pathlib import Path

from fastapi import Request, Depends, APIRouter
from fastapi.responses import FileResponse
from pymongo import MongoClient
from supermemo2 import SMTwo
import dateutil.parser
from loguru import logger

from consts import mongoUrl, MAX_LEVEL
from utilis import (
    verify_user_info,
    get_unique_id,
    encrypt_data,
    filtering,
    user_info,
    get_user_level,
)


router = APIRouter()

Client = MongoClient(mongoUrl)
db = Client["englishWordsApp"]
users_db = Client["usersDataBase"]
users_collection = db["users"]

logger.add("out.log", diagnose=True)


@router.get("/")
def get_words(user_collection: str = Depends(verify_user_info)):
    all_words = {}
    english_words = [
        x["word"]
        for x in users_db[user_collection].find(
            {"alreadyKnow": {"$exists": False}}, {"word": 1}
        )
    ]
    all_user_words = [
        x["word"] for x in users_db[user_collection].find({}, {"word": 1})
    ]
    logger.info(f"{len(english_words)}, {len(all_user_words)}")
    random.shuffle(english_words)
    random.shuffle(all_user_words)

    for x in all_user_words:
        try:
            word_obj = db["wordsObj"].find_one({x: {"$exists": True}})
            all_words[x] = [
                word_obj[x]["he"],
                word_obj["imageUrl"],
                word_obj["sentences"],
            ]
        except Exception as e:
            print("words: ", x, "failed", e)
    logger.info(
        f"user: {user_collection}, all words: {len(all_words)}, words: {len(english_words)}"
    )

    return {"words": english_words, "all words": all_words}


@router.get("/unlearned_words")
def get_unlearned_words(user_collection: str = Depends(verify_user_info)):
    query = {"review_date": "", "alreadyKnow": False}
    words = [x["word"] for x in users_db[user_collection].find(query)]
    random.shuffle(words)

    return words


@router.get("/already_passed_words")
def get_already_passed_words(user_collection: str = Depends(verify_user_info)):
    query = {"review_date": {"$ne": ""}}
    words = [x["word"] for x in users_db[user_collection].find(query)]
    random.shuffle(words)

    return words


@router.get("/practice_daily_words")
def get_practice_words(user_collection: str = Depends(verify_user_info)):
    today_query = {"review_date": {"$lt": datetime.now()}}
    low_rating_query = {"last_rate": {"$gt": -1, "$lt": 4}}
    today_words = [x["word"] for x in users_db[user_collection].find(today_query)]
    low_rating_words = [
        x["word"] for x in users_db[user_collection].find(low_rating_query)
    ]
    logger.info(f"today: {len(today_words)}, by rating: {len(low_rating_words)}")

    if not today_words:
        today_words += low_rating_words
    today_words = list(set(today_words))
    random.shuffle(today_words)

    return today_words


@router.post("/register")
def register(name: str, password: str, private_name: str):
    if len(name) < 5 or len(password) < 8:
        return {"ok": False, "log": "short data"}
    query = {"name": name}

    if users_collection.find_one(query) is not None:
        return {"ok": False, "log": "user name is already exist"}

    hash_pass, salt = encrypt_data(password)
    users_collection.insert_one(
        {
            "name": name,
            "password": hash_pass,
            "salt": salt,
            "collection": get_unique_id(name=name),
            "privateName": private_name,
            "level": 1,
        }
    )

    return {"ok": True, "log": "success"}


@router.put("/login")
def login(info: str, user_data_base: str = Depends(verify_user_info)):
    if user_data_base is None:
        return {"ok": False, "log": "user not found"}

    return {"ok": True, "log": "success"}


@router.put("/get_user_info")
def get_user_info(info: str, user_data_base: str = Depends(verify_user_info)):
    user_name, password = info.split(" ")

    return {"ok": user_info(user_name)}


@router.post("/send_words_rating")
async def save_words_rating(
    request: Request, user_collection: str = Depends(verify_user_info)
):
    resp = await request.json()
    words = resp["words"]
    ratings = resp["ratings"]

    if words is None or ratings is None:
        logger.info(f"None data {words}, {ratings}")
        return {"ok": False}

    try:
        for x in range(len(words)):
            current_word = users_db[user_collection].find_one({"word": words[x]})
            next_review = current_word["review_date"]
            # first review

            if current_word["repetitions"] == -1:
                review = SMTwo.first_review(ratings[x])
                next_review = dateutil.parser.parse(str(review.review_date))
            # isn't the first review
            else:
                review = SMTwo(
                    easiness=current_word["easiness"],
                    interval=current_word["interval"],
                    repetitions=current_word["repetitions"],
                )
                # if repeated this words cause the last rate lower then 4 so don't need to count this time

                if current_word["review_date"] <= datetime.now():
                    review.review(ratings[x])
                    next_review = dateutil.parser.parse(str(review.review_date))
            # save the new obj to DB
            users_db[user_collection].update(
                {"word": words[x]},
                {
                    "$set": {
                        "easiness": review.easiness,
                        "interval": review.interval,
                        "repetitions": review.repetitions,
                        "review_date": next_review,
                        "last_rate": ratings[x],
                    }
                },
            )
    except Exception as e:
        logger.info(f"the error is:\n  {str(e)}")
        return {"ok": False}

    return {"ok": True}


@router.put("/default_program")
async def default_words(user_collection: str = Depends(verify_user_info)):
    english_words = [
        list(filter(filtering, x.keys()))[0] for x in db["wordsObj"].find({"level": 1})
    ]

    for word in english_words:
        dic = {
            "word": str(word),
            "easiness": -1,
            "interval": -1,
            "repetitions": -1,
            "review_date": "",
            "last_rate": -1,
        }
        users_db[user_collection].insert_one(dic)

    return {"ok": True}


@router.put("/level_up")
async def level_up(info: str, user_collection: str = Depends(verify_user_info)):
    user_level = get_user_level(info)
    user_new_level = min(user_level + 1, MAX_LEVEL)
    users_collection.update(
        {"collection": user_collection}, {"$set": {"level": user_new_level}}
    )
    english_words = [
        list(filter(filtering, x.keys()))[0]
        for x in db["wordsObj"].find({"level": user_new_level})
    ]

    for word in english_words:
        dic = {
            "word": str(word),
            "easiness": -1,
            "interval": -1,
            "repetitions": -1,
            "review_date": "",
            "last_rate": -1,
        }
        users_db[user_collection].insert_one(dic)

    return {"ok": True}


@router.get("/{word}")
def get_audio(word: str):
    sounds_file = Path(__file__).parent.parent / f"sounds/{word}"
    return FileResponse(str(sounds_file), media_type="audio/mpeg")


@router.put("/send_data")
async def save_data(request: Request, user_collection: str = Depends(verify_user_info)):
    resp = await request.json()
    words = resp["words"]
    scores = resp["scores"]

    if words is None or scores is None:
        logger.info(f"None data {words}, {scores}")
        return {"ok": False}

    try:
        for x in range(len(words)):
            already_know = True

            if scores[x] != "3":
                already_know = False
            users_db[user_collection].update_one(
                {"word": words[x]}, {"$set": {"alreadyKnow": already_know}}
            )

            if scores[x] == "3":
                users_db[user_collection].remove({"word": words[x]})

        return {"ok": True}
    except Exception as e:
        print(f"the error is:\n {str(e)}")
        return {"ok": False}
