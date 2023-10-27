import asyncio
import json
from datetime import timedelta
from typing import Optional, List, Dict, Union, Type, Any, Annotated, Callable
import pytz
from aiohttp import ClientSession
from bson import ObjectId, json_util
from fastapi import HTTPException
from motor.motor_asyncio import AsyncIOMotorClient
from aiohttp_socks import ProxyConnector, ProxyType
from pydantic import BaseModel, Field
import logging
import sys
from colorlog import ColoredFormatter
import geoip2.database
from pydantic_core import ValidationError, core_schema
from pymongo import ReturnDocument
from datetime import datetime

GEOIP_DB_PATH = 'GeoLite2-Country.mmdb'
COLORS = {
    "DEBUG": "cyan",
    "INFO": "green",
    "WARNING": "yellow",
    "ERROR": "red",
    "CRITICAL": "bold_red",
}

formatter = ColoredFormatter(
    "%(log_color)s%(levelname)-8s%(reset)s %(asctime)s %(name)s %(message)s",
    datefmt=None,
    reset=True,
    log_colors=COLORS,
    secondary_log_colors={},
    style="%"
)

stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setFormatter(formatter)

logging.basicConfig(
    level=logging.INFO,
    handlers=[stream_handler]
)

logger = logging.getLogger(__name__)


class _ObjectIdPydanticAnnotation:
    @classmethod
    def __get_pydantic_core_schema__(
            cls,
            _source_type: Any,
            _handler: Callable[[Any], core_schema.CoreSchema],
    ) -> core_schema.CoreSchema:
        def validate_from_str(input_value: str) -> ObjectId:
            return ObjectId(input_value)

        return core_schema.union_schema(
            [
                core_schema.is_instance_schema(ObjectId),
                core_schema.no_info_plain_validator_function(validate_from_str),
            ],
            serialization=core_schema.to_string_ser_schema(),
        )


PydanticObjectId = Annotated[ObjectId, _ObjectIdPydanticAnnotation]


class ProxyModel(BaseModel):
    id: PydanticObjectId = Field(default_factory=PydanticObjectId, alias='_id')
    ip: str
    port: int
    username: Optional[str] = Field(default=None)
    password: Optional[str] = Field(default=None)
    protocol: str = Field(default="HTTP")
    response_time: Optional[float] = Field(default=None)
    status: str = Field(default="UNKNOWN")
    country_code: Optional[str] = Field(default=None)
    instance_id: Optional[str] = Field(default=None)
    instance_ids: Optional[Dict[str, datetime]] = Field(default_factory=dict)
    last_used: Optional[datetime] = Field(default=None)
    tags: Optional[List[str]] = Field(default_factory=list)

    class Config:
        arbitrary_types_allowed = True
        populate_by_name = True

        json_encoders = {
            ObjectId: str
        }


class SettingsModel(BaseModel):
    max_proxies_per_instance: Optional[int]
    max_instances_per_proxy: Optional[int]
    inactive_proxy_timeout: Optional[int]
    background_check_proxies_interval: Optional[int]
    threshold_time_minutes: Optional[int]


async def get_country_code(ip_address: str) -> Optional[str]:
    try:
        loop = asyncio.get_event_loop()
        reader = geoip2.database.Reader(GEOIP_DB_PATH)
        response = await loop.run_in_executor(None, reader.country, ip_address)
        return response.country.iso_code
    except Exception as e:
        print(f"Error getting country code for IP {ip_address}: {e}")
        return None


class ProxyManagement:

    def __init__(self, db_url: str, db_name: str, db_user: str, db_password: str):
        self.settings = None
        self.db_client = AsyncIOMotorClient(
            db_url,
            username=db_user,
            password=db_password,
            serverSelectionTimeoutMS=1000
        )
        self.db = self.db_client[db_name]
        self.proxy_check_urls = ["https://google.com", "https://bing.com", "https://yahoo.com"]

    async def load_settings(self):
        default_settings = {
            "inactive_proxy_timeout": 10,
            "threshold_time_minutes": 10,
            "background_check_proxies_interval": 60,
            "max_instances_per_proxy": 2,
            "max_proxies_per_instance": 1
        }

        settings = await self.db.proxy_manager_settings.find_one()
        if settings is None:
            await self.db.proxy_manager_settings.insert_one(default_settings)
            settings = default_settings
            self.settings = settings
        self.inactive_proxy_timeout = settings["inactive_proxy_timeout"]
        self.threshold_time_minutes = settings["threshold_time_minutes"]
        self.background_check_proxies_interval = settings["background_check_proxies_interval"]
        self.max_instances_per_proxy = settings["max_instances_per_proxy"]
        self.max_proxies_per_instance = settings["max_proxies_per_instance"]

        return settings

    def __str__(self):
        return (
            f"ProxyManagement Settings:\n"
            f"  - inactive_proxy_timeout: {self.inactive_proxy_timeout} \n"
            f"  - background_check_proxies_interval: {self.background_check_proxies_interval} \n"
            f"  - threshold_time_minutes: {self.threshold_time_minutes} \n"
            f"  - max_instances_per_proxy: {self.max_instances_per_proxy}\n"
        )

    async def reset_all_proxies(self):
        result = await self.db.proxies.update_many({}, {"$set": {"instance_ids": {}, "last_used": None}})

        if result.matched_count == 0:
            return {
                "status": "info",
                "message": "No proxies were available to reset."
            }
        elif result.modified_count == 0:
            return {
                "status": "info",
                "message": "No proxies needed resetting."
            }
        else:
            return {
                "status": "success",
                "message": f"Successfully reset {result.modified_count} proxies."
            }

    async def update_settings(self, updated_settings: SettingsModel):
        try:
            update_dict = {k: v for k, v in updated_settings.model_dump(exclude_none=True).items()}

            if not update_dict:
                raise HTTPException(status_code=400, detail="No updates provided")

            result = await self.db.proxy_manager_settings.update_one({}, {'$set': update_dict}, upsert=True)

            if result.matched_count < 1:
                raise HTTPException(status_code=404, detail="Settings not found")

            await self.load_settings()

            return {"status": "success", "detail": "Settings have been updated", "updated_settings": update_dict}

        except HTTPException as http_exc:
            raise http_exc

        except Exception as e:
            raise HTTPException(status_code=500, detail="An error occurred while updating settings") from e

    async def get_settings(self):
        settings = json.loads(json_util.dumps(self.settings))
        return settings

    async def clear_instance_reservation(self, instance_id: str):
        proxies = await self.get_proxies()
        cleared_proxies = []

        for proxy in proxies:
            if instance_id in proxy.instance_ids:
                result = await self.clear_instance_id(proxy.id, instance_id)
                if result:
                    cleared_proxies.append(proxy.id)
                else:
                    return {
                        "status": "error",
                        "message": f"Failed to clear instance {instance_id} reservation from proxy {proxy.id}"
                    }

        if cleared_proxies:
            str_cleared_proxies = [str(proxy) for proxy in cleared_proxies if
                                   proxy is not None]
            return {
                "status": "success",
                "message": f"Instance {instance_id} reservation cleared from proxies {', '.join(str_cleared_proxies)}"
            }

        else:
            return {
                "status": "error",
                "message": f"Instance {instance_id} not found in any proxy"
            }

    async def clear_instance_from_specific_proxy(self, proxy_id: str, instance_id: str):
        proxy_object_id = ObjectId(proxy_id)
        result = await self.clear_instance_id(proxy_object_id, instance_id)
        if result:
            logger.info(f"Cleared instance {instance_id} from proxy {proxy_id}")
            return {"status": "success", "message": f"Instance {instance_id} cleared from proxy {proxy_id}"}
        else:
            logger.error(f"Failed to clear instance {instance_id} from proxy {proxy_id}")
            return {"status": "error", "message": f"Failed to clear instance {instance_id} from proxy {proxy_id}"}

    async def clear_instance_id(self, proxy_id: ObjectId, instance_id: str):
        result = await self.db.proxies.update_one(
            {"_id": proxy_id, "instance_ids": {"$type": "object"}},
            {"$unset": {f"instance_ids.{instance_id}": ""}}
        )

        if result.modified_count == 1:
            return True

        result = await self.db.proxies.update_one(
            {"_id": proxy_id},
            {"$set": {"instance_id": None}}
        )
        return result.modified_count == 1

    async def assign_proxy_to_instance(self, instance_id: str, country_code: Optional[str] = None,
                                       tags: Optional[List[str]] = None):
        instance_proxies = await self.db.proxies.find({"instance_ids": instance_id}).to_list(None)

        if len(instance_proxies) >= self.max_proxies_per_instance:
            return {
                "status": "error",
                "message": f"Instance {instance_id} is already assigned to the maximum allowed number of proxies ({self.max_proxies_per_instance})."
            }

        query = {
            "status": "UP",
            "$where": f"this.instance_ids && Object.keys(this.instance_ids).length < {self.max_instances_per_proxy}"
        }

        if tags:
            query["tags"] = {"$all": tags}
        if country_code:
            query["country_code"] = country_code.upper()

        proxy = await self.db.proxies.find_one(query)

        if not proxy:
            no_proxies_message = "No available proxies found"
            if country_code:
                no_proxies_message += f" for country code {country_code}"
            if tags:
                no_proxies_message += f" and tags {tags}" if country_code else f" for tags {tags}"

            return {
                "status": "error",
                "message": no_proxies_message
            }

        proxy_id = proxy["_id"]
        current_time = datetime.now(pytz.utc)

        proxy['instance_ids'] = {
            k: v for k, v in proxy['instance_ids'].items()
            if v.replace(tzinfo=pytz.utc) > current_time - timedelta(minutes=self.inactive_proxy_timeout)
        }

        proxy['instance_ids'][instance_id] = current_time

        result = await self.db.proxies.update_one(
            {'_id': proxy['_id']},
            {'$set': {'instance_ids': proxy['instance_ids']}}
        )

        if result.modified_count == 1:
            await self.update_last_used(proxy_id)
            return {
                "status": "success",
                "message": f"Proxy {proxy_id} assigned to instance {instance_id}",
                "proxy_id": str(proxy_id),
                "ip": proxy['ip'],
                "port": proxy['port'],
                "username": proxy.get('username'),
                "password": proxy.get('password'),
                "protocol": proxy['protocol'],
            }
        else:
            return {
                "status": "error",
                "message": f"Failed to assign proxy {proxy_id} to instance {instance_id}"
            }

    async def clear_inactive_proxies(self):
        while True:
            current_time = datetime.now(pytz.utc)
            threshold_time = current_time - timedelta(minutes=self.threshold_time_minutes)
            proxies = await self.db.proxies.find({}).to_list(length=None)

            for proxy in proxies:
                instance_ids = proxy.get("instance_ids", {})

                if not isinstance(instance_ids, dict):
                    logger.error(
                        f"instance_ids in proxy {proxy['_id']} is not a dictionary. Actual value: {instance_ids}")
                    continue

                expired_instance_ids = [
                    instance_id for instance_id, last_used in instance_ids.items()
                    if last_used.replace(tzinfo=pytz.utc) < threshold_time
                ]

                if expired_instance_ids:
                    logger.info(f"Proxy {proxy['_id']} has expired instances: {expired_instance_ids}")
                    update_query = {
                        "$unset": {f"instance_ids.{instance_id}": "" for instance_id in expired_instance_ids}
                    }

                    if len(expired_instance_ids) == len(instance_ids):
                        update_query["$unset"]["last_used"] = ""

                    await self.db.proxies.update_one({'_id': proxy['_id']}, update_query)

                    for instance_id in expired_instance_ids:
                        logger.info(f"Removed expired instance {instance_id} from proxy {proxy['_id']}")

            await asyncio.sleep(self.background_check_proxies_interval)

    async def edit_proxy(self, proxy_id: str, updated_fields: Dict[str, Optional[Union[str, int, List[str]]]]):
        existing_proxy = await self.db.proxies.find_one({"_id": ObjectId(proxy_id)})
        if existing_proxy is None:
            raise HTTPException(status_code=404, detail="Proxy not found")

        update_dict = {}
        allowed_fields = ["ip", "port", "username", "password", "protocol", "country_code", "tags"]
        fields_updated = []

        for field, value in updated_fields.items():
            if field in allowed_fields:
                if value is None:
                    raise HTTPException(status_code=400, detail=f"Value for field '{field}' cannot be None")

                if field == "tags":
                    if not isinstance(value, list):
                        raise HTTPException(status_code=400, detail=f"Value for field 'tags' must be a list")

                fields_updated.append(field)
                update_dict[field] = value
            else:
                raise HTTPException(status_code=400, detail=f"Field '{field}' is not editable")

        if update_dict:
            result = await self.db.proxies.find_one_and_update(
                {"_id": ObjectId(proxy_id)},
                {"$set": update_dict},
                return_document=ReturnDocument.AFTER
            )

            if not result:
                raise HTTPException(status_code=500, detail="The update was not successful for an unknown reason")

            updated_proxy_data = {**result, "_id": str(result["_id"])}

            updated_proxy_model = ProxyModel(**updated_proxy_data)
            asyncio.create_task(self.check_proxy(updated_proxy_model))

            return {
                "status": "success",
                "message": "Proxy updated and check scheduled",
                "updated_fields": fields_updated,
                "updated_proxy": updated_proxy_data
            }

        return {"status": "error", "message": "No valid fields were provided for update"}

    async def get_proxy(self, proxy_id: str):
        proxy = await self.db.proxies.find_one({"_id": ObjectId(proxy_id)})
        if proxy:
            return ProxyModel(**proxy)
        else:
            return None

    async def get_all_proxies(self):
        proxies = await self.db.proxies.find({}).to_list(length=None)
        return [ProxyModel(**proxy) for proxy in proxies]

    async def add_proxy(self, proxy: ProxyModel):
        try:
            if proxy.id is None:
                proxy.id = ObjectId()

            proxy_data = proxy.model_dump(by_alias=True, exclude_none=True)

            existing_proxy = await self.db.proxies.find_one({
                'ip': proxy_data['ip'],
                'port': proxy_data['port'],
                'protocol': proxy_data['protocol']
            })

            if existing_proxy:
                raise HTTPException(
                    status_code=400,
                    detail="A proxy with the same IP, port, and protocol already exists."
                )

            await self.db.proxies.insert_one(proxy_data)
            asyncio.create_task(self.check_proxy(proxy))
            return {"_id": str(proxy.id), "status": "success", "message": "Proxy added, scheduled for checking"}

        except HTTPException as http_exc:
            raise http_exc
        except Exception as e:
            raise HTTPException(status_code=500, detail="An error occurred while adding the proxy.") from e

    async def check_proxy(self, proxy: ProxyModel):
        if proxy.id is None:
            logger.error("Received a proxy with no ID.")
            return

        response_times = []
        proxy_type_mapping = {
            "HTTP": ProxyType.HTTP,
            "SOCKS4": ProxyType.SOCKS4,
            "SOCKS5": ProxyType.SOCKS5
        }
        proxy_type = proxy_type_mapping.get(proxy.protocol.upper())

        connector_kwargs = {
            "host": proxy.ip,
            "port": proxy.port,
            "proxy_type": proxy_type,
        }
        if proxy.username and proxy.password:
            connector_kwargs["username"] = proxy.username
            connector_kwargs["password"] = proxy.password

        connector = ProxyConnector(**connector_kwargs)

        async with ClientSession(connector=connector) as session:
            for url in self.proxy_check_urls:
                try:
                    start_time = datetime.now()
                    async with session.get(url) as response:
                        response.raise_for_status()
                    end_time = datetime.now()
                    duration = end_time - start_time
                    response_time = round(duration.seconds * 100)
                    response_times.append(response_time)

                    logger.info(
                        f"Success: Proxy {proxy.id} ({proxy.ip}:{proxy.port}), URL: {url}, Response time: {response_time} ms")
                except Exception as e:
                    logger.error(f"Error checking proxy {proxy.id} ({proxy.ip}:{proxy.port}): {str(e)}")
                    response_times.append(float('inf'))

        valid_response_times = [t for t in response_times if t != float('inf')]
        avg_response_time = round(
            sum(valid_response_times) / len(valid_response_times)) if valid_response_times else float('inf')
        status = "UP" if valid_response_times else "DOWN"
        try:
            update_fields = {
                "status": status,
                "response_time": avg_response_time
            }

            result = await self.db.proxies.update_one(
                {"_id": proxy.id},
                {"$set": update_fields}
            )

            if result.modified_count == 0:
                logger.error(f"No document was updated for Proxy ID: {proxy.id}. Does the document exist?")
            else:
                logger.info(f"Updated document for Proxy ID: {proxy.id}.")
        except Exception as e:
            logger.error(f"An error occurred during the database update for Proxy ID: {proxy.id}. Error: {str(e)}")

        avg_response_time_display = f"{avg_response_time} ms" if avg_response_time != float('inf') else "N/A"
        logger.info(
            f"Proxy: {proxy.id} ({proxy.ip}:{proxy.port}), Average response time: {avg_response_time_display}, Status: {status}")

    async def background_update_country_codes(self):
        while True:
            proxies = await self.get_proxies()
            if proxies:
                for proxy in proxies:
                    proxy_dict = proxy.model_dump()
                    try:
                        if proxy_dict["country_code"] is None:
                            country_code = await get_country_code(proxy_dict["ip"])
                            if country_code:
                                await self.update_proxy_country_code(proxy_dict["id"], country_code)
                    except Exception as e:
                        logger.error(f"Error updating country code for proxy {proxy_dict['id']}: {e}")
                        pass
            await asyncio.sleep(20)

    async def update_proxy_country_code(self, proxy_id: str, country_code: str):
        try:
            result = await self.db.proxies.update_one(
                {"_id": ObjectId(proxy_id)},
                {"$set": {"country_code": country_code}}
            )
            if result.modified_count == 1:
                return {
                    "status": "success",
                    "message": f"Updated country code for proxy with ID {proxy_id} to {country_code}"
                }
            else:
                return {
                    "status": "error",
                    "message": f"Failed to update country code for proxy with ID {proxy_id}"
                }
        except Exception as e:
            print(f"Error updating country code for proxy with ID {proxy_id}: {e}")
            return {
                "status": "error",
                "message": f"Error updating country code for proxy with ID {proxy_id}: {e}"
            }

    async def refresh_proxy_usage(self, proxy_id: str, instance_id: Optional[str] = None):
        proxy = await self.get_proxy(proxy_id)
        if not proxy:
            return {"status": "error", "message": f"Proxy {proxy_id} not found"}

        if instance_id:
            instance_ids = [instance_id]
        else:
            standalone_instance_id = [proxy.instance_id] if proxy.instance_id else []
            instance_ids_in_list = list(proxy.instance_ids.keys())
            instance_ids = standalone_instance_id + instance_ids_in_list

        if not instance_ids:
            return {"status": "error", "message": f"No instances associated with proxy {proxy_id}"}

        refresh_results = []
        for inst_id in instance_ids:
            result = await self.update_last_used(proxy_id, inst_id)
            if result:
                refresh_results.append(
                    {"status": "success", "message": f"Proxy {proxy_id} usage refreshed for instance {inst_id}"})
            else:
                refresh_results.append(
                    {"status": "error", "message": f"Failed to refresh proxy usage for instance {inst_id}"})

        return refresh_results

    async def update_last_used(self, proxy_id: str, instance_id: Optional[str] = None):
        proxy_object_id = ObjectId(proxy_id)

        if instance_id:
            update_query = {"$currentDate": {f"instance_ids.{instance_id}": True}}
        else:
            update_query = {"$currentDate": {"last_used": True}}

        result = await self.db.proxies.update_one(
            {"_id": proxy_object_id},
            update_query
        )

        return result.modified_count > 0

    async def get_proxies(self, tags: Optional[List[str]] = None):
        query = {}
        if tags:
            query["tags"] = {"$in": tags}

        proxies = await self.db.proxies.find(query).to_list(length=None)
        proxies_with_counts = []
        for proxy in proxies:
            proxy_data = dict(proxy)
            instance_ids = proxy_data.get("instance_ids", {})

            if not isinstance(instance_ids, dict):
                print(f"Warning: 'instance_ids' expected to be a dict, but got {type(instance_ids).__name__} instead.")
                instance_ids = {}

            instances_count = len(instance_ids)
            if instances_count == 1:
                proxy_data["instance_id"] = next(iter(instance_ids))
            else:
                proxy_data["instance_ids"] = instance_ids

            try:
                proxies_with_counts.append(ProxyModel(**proxy_data))
            except ValidationError as e:
                print(f"A validation error occurred: {e}")

        return proxies_with_counts

    async def delete_proxy(self, proxy_id: str):
        result = await self.db.proxies.delete_one({"_id": ObjectId(proxy_id)})
        if result.deleted_count == 1:
            return {"status": "success", "message": "Proxy deleted"}
        else:
            return {"status": "error", "message": "Failed to delete the proxy"}

    async def assign_instance_id(self, proxy_id: str, instance_id: str):
        result = await self.db.proxies.update_one(
            {"_id": ObjectId(proxy_id)},
            {"$addToSet": {"instance_ids": instance_id}}
        )
        return result.modified_count == 1

    async def background_check_proxies(self):
        while True:
            cursor = self.db.proxies.find({})
            proxies = await cursor.to_list(length=None)
            proxies = [
                ProxyModel(
                    **{
                        **proxy,
                        "_id": ObjectId(proxy["_id"]),
                        "response_time": float(proxy["response_time"]) if "response_time" in proxy and isinstance(
                            proxy["response_time"], (int, float)) else None
                    }
                )
                for proxy in proxies if "_id" in proxy
            ]
            await asyncio.gather(*(self.check_proxy(proxy) for proxy in proxies))
            await asyncio.sleep(self.background_check_proxies_interval)


if __name__ == "__main__":
    print("Run the API.py file instead")
