# <p align="center">🪹 ProxyNest a Proxy Management Solution! </p>


Managing proxies for scaled data scraping and other automation operations will eventually require something like ProxyNest.
ProxyNest is a proxy managment API that is well-suited for mid-scale and will soon be made for large ones.

![alt text](https://i.imgur.com/Zr4K21h.png)


## 🚀 The tech stack :

* FastAPI
* Uvicorn
* MongoDB 

<br>

## 🛠️ The features :

### ⚙️ Proxy management:
- add/update/delete proxies and fetch by country tag or codes.
- reset all proxies if anything goes wrong.

### 🎫 Reservation system:
- reserve proxies for instances.
- refresh the reservation on request.
- clear the instance reservation.

###  Background checks:
- periodic check for proxy uptime and latency.
- periodic check for country code of the IP.
- cleanup for instances that expired.
<br>


## Setup.
```
the default username is admin and password is password :p 
```
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
<details>
  <summary>requires Python 3.10, click here.</summary>
 1 - Modify your environment variables.

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
</details>

<br>


### 🔗 Routes summary

Including the overall routes in here, you can read indepth about the documentation when you read the webserver, or the wiki once its setup.


| Route url  | Usage |
| ------------- | ------------- |
| /Docs  | Full routes documentation  |
| /add_proxies | Add proxies. |
|/proxies  | Get proxies  |
|/assign_proxy  | Assign proxies to an instance  |
|/update_proxy/{proxy_id}  | update proxy  |
|/delete_proxy/{proxy_id}  | delete proxy  |
|/refresh_proxy_usage/{proxy_id}  | refresh proxy  |
|/clear_instance_proxies/{instance_id}  | clearn instance proxies|
|/clear_instance_from_specific_proxy/{proxy_id}/{instance_id}  | clear instance from specific proxy |
|/reset_all_proxies  | reset all proxies  |
|/reset-password/  | reset auth password  |


<br>

## TODO
- [ ] fix tag system with proxy reservation as its unused there for now.
- [ ] write an actual documentation of the project.
- [ ] build a docker image automatically and publish using Github actions.
- [ ] perfecounter usage for response time instead of what is being currently used.

<br>



## ⏰ Planned tasks :
- Integrated rotating proxy creation.
- Better authentication.
- Considerably better task queuing instead of using asyncio task queuing for very large scale operations.
- Custom host to measure latency.
- Multi user support.
- Write more documentation
- Stress test with k6
- more profiling


## important mention. 
This project includes GeoLite2 data created by MaxMind, available from [https://www.maxmind.com](https://www.maxmind.com).
