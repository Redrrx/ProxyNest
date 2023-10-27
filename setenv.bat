@echo off
set /p DB_URL=Enter your DB_URL:
set /p DB_NAME=Enter your DB_NAME:
set /p DB_USER=Enter your DB_USER:
set /p DB_PASSWORD=Enter your DB_PASSWORD:

setx DB_URL "%DB_URL%"
setx DB_NAME "%DB_NAME%"
setx DB_USER "%DB_USER%"
setx DB_PASSWORD "%DB_PASSWORD%"

echo Environment variables have been set!
