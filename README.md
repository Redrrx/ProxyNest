# 🌐 ProxyNest a Proxy Management Solution! 


Managing proxies for scaled data scraping and other automation operations will eventually require something like ProxyNest.
ProxyNest is a proxy managment API that is well-suited for mid-scale and will soon be made for large ones.



## 🚀 The tech stack :

* FastAPI
* Uvicorn
* MongoDB 

<br>

## 🛠️ The features :

### Proxy management:
- add/update/delete proxies and fetch by country tag or codes.
- reset all proxies if anything goes wrong.
<br>

### Reservation system:
- reserve proxies for instances.
- refresh the reservation on request.
- clear the instance reservation.
<br>

### Background checks:
- periodic check for proxy uptime and latency.
- periodic check for country code of the IP.
- cleanup for instances that expired.
<br>


## Setup.

###  Using Docker 🐋 (Recommended).

Make sure you have docker installed and a mongoDB hosted.
let's start by building the docker image, get into the directory using any terminal and run the docker build command.
```
docker build -t proxynest  .
```

then we'll start it and pass the right variables to your mongoDB
```
docker run -d -p 8000:8000 --name proxynest  \
-e DB_URL='your_db_url' \
-e DB_NAME='your_db_name' \
-e DB_USER='your_db_user' \
-e DB_PASSWORD='your_db_password' \
-e PORT=8000 \ proxynest
```

you'll have it running in no time serving requests ! 

![alt text](https://i.imgur.com/AkWyn3I.png)

### Using the python script directly.
requires Python 3.10.

1 - Modify your enivronment variables.

for linux change setenv.sh then run this command.

```
bash setenv.sh
```

for windows  change setenv.bat then just double click the bat file.

2 - install the required packages using

```
 pip install -r requirements.txt 
```

3 - run the API.py 

```
python API.py
```

feel free to edit this part of the code in APY.py  to change uvicorn launch settings.

```
if __name__ == "__main__":
    uvicorn.run("API:app", host="0.0.0.0", port=8042)
```


## ⏰ Planned upgrades :
- Better authentication.
- Considerably better task queuing instead of using asyncio task queuing for very large scale operations.
- Multi user support.
