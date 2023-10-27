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

### Using Docker.

Let's start by building the docker image, get into the directory and run the docker build command.
```
docker build -t proxynest  .
```

then we'll start it 
```
docker run -d -p 8000:8000 --name proxynest  \
-e DB_URL='your_db_url' \
-e DB_NAME='your_db_name' \
-e DB_USER='your_db_user' \
-e DB_PASSWORD='your_db_password' \
-e PORT=8000 \ proxynest
```



## ⏰ Planned upgrades :
- Better authentication.
- Considerably better task queuing instead of using asyncio task queuing for very large scale operations.
- Multi user support.
