import logging
import os
from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel
import motor.motor_asyncio
import bcrypt


class User(BaseModel):
    username: str
    password: str


class ResetPasswordRequest(BaseModel):
    username: str
    old_password: str
    new_password: str


class DBCON(BaseModel):
    DB_URL: str
    DB_NAME: str
    DB_USER: str
    DB_PASSWORD: str


db_url = os.getenv('DB_URL')
db_name = os.getenv('DB_NAME')
db_user = os.getenv('DB_USER')
db_password = os.getenv('DB_PASSWORD')

client = motor.motor_asyncio.AsyncIOMotorClient(
    db_url,
    username=db_user,
    password=db_password,
    serverSelectionTimeoutMS=1000
)
db = client.administration
collection = db.user
security = HTTPBasic()


async def admincheck():
    admin_user = await collection.find_one({"username": "admin"})
    if admin_user is None:
        logging.info('No Administrator detected, creating default admin account wih credentials admin:password.')
        admin_password = "password"
        encrypted_password = bcrypt.hashpw(admin_password.encode('utf-8'), bcrypt.gensalt())

        new_admin = {
            "username": "admin",
            "password": encrypted_password.decode('utf-8'),
        }
        await collection.insert_one(new_admin)


async def get_current_user(credentials: HTTPBasicCredentials = Depends(security)):
    user = await collection.find_one({"username": credentials.username})
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    password_match = bcrypt.checkpw(credentials.password.encode('utf-8'), user['password'].encode('utf-8'))
    if not password_match:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password")

    return user
