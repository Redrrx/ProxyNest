import asyncio
import os
from typing import Optional, List, Dict, Union
import bcrypt
import uvicorn
from fastapi import FastAPI, Query, Depends, HTTPException
from starlette import status
from starlette.responses import JSONResponse
from auth import get_current_user, collection, ResetPasswordRequest, admincheck
from proxynest import ProxyManagement, ProxyModel, SettingsModel

proxy_management = ProxyManagement(
    db_url=os.getenv('DB_URL'),
    db_name=os.getenv('DB_NAME'),
    db_user=os.getenv('DB_USER'),
    db_password=os.getenv('DB_PASSWORD'),
)

app = FastAPI(title="ProxyNest",
              description="ProxyNest is a proxy managment API",
              version="1.0.0",
              redoc_url="/redoc")


@app.post("/add_proxies", dependencies=[Depends(get_current_user)])
async def add_proxy(proxy: ProxyModel):
    result = await proxy_management.add_proxy(proxy)
    return result


@app.get("/proxies", dependencies=[Depends(get_current_user)])
async def get_proxies(tags: Optional[List[str]] = Query(None)):
    proxies = await proxy_management.get_proxies(tags=tags)
    return proxies


@app.post("/assign_proxy", dependencies=[Depends(get_current_user)])
async def assign_proxy_to_instance(instance_id: str, country_code: Optional[str] = Query(None),
                                   tags: Optional[List[str]] = Query(None)):
    result = await proxy_management.assign_proxy_to_instance(instance_id, country_code, tags)
    return result


@app.post("/update_proxy/{proxy_id}", dependencies=[Depends(get_current_user)])
async def update_proxy(proxy_id: str, proxy: Dict[str, Optional[Union[str, int, List[str]]]]):
    result = await proxy_management.edit_proxy(proxy_id, proxy)
    return result


@app.post("/delete_proxy/{proxy_id}", dependencies=[Depends(get_current_user)])
async def delete_proxy(proxy_id: str):
    result = await proxy_management.delete_proxy(proxy_id)
    return result


@app.post("/refresh_proxy_usage/{proxy_id}", dependencies=[Depends(get_current_user)])
async def refresh_proxy_usage(proxy_id: str, instance_id: Optional[str] = None):
    result = await proxy_management.update_last_used(proxy_id, instance_id)
    if result:
        if instance_id:
            return {"status": "success", "message": f"Proxy {proxy_id} usage refreshed for instance {instance_id}"}
        else:
            return {"status": "success", "message": f"Proxy {proxy_id} usage refreshed for all instances"}
    else:
        return {"status": "error", "message": "Failed to refresh proxy usage"}


@app.post("/clear_instance_proxies/{instance_id}", dependencies=[Depends(get_current_user)])
async def clear_instance_reservation(instance_id: str):
    return await proxy_management.clear_instance_reservation(instance_id)


@app.post("/clear_instance_from_specific_proxy/{proxy_id}/{instance_id}", dependencies=[Depends(get_current_user)])
async def clear_instance_from_specific_proxy(proxy_id: str, instance_id: str) -> JSONResponse:
    result = await proxy_management.clear_instance_from_specific_proxy(proxy_id, instance_id)
    return JSONResponse(content=result)


@app.post("/reset_all_proxies", dependencies=[Depends(get_current_user)])
async def reset_all_proxies():
    result = await proxy_management.reset_all_proxies()
    return result


@app.post("/reset-password/")
async def reset_password(
        reset_request: ResetPasswordRequest,
        current_user: dict = Depends(get_current_user)
):
    if not bcrypt.checkpw(reset_request.old_password.encode('utf-8'), current_user['password'].encode('utf-8')):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Old password is incorrect")

    new_encrypted_password = bcrypt.hashpw(reset_request.new_password.encode('utf-8'), bcrypt.gensalt())
    await collection.update_one(
        {"username": current_user['username']},
        {"$set": {"password": new_encrypted_password.decode('utf-8')}}
    )
    return {"message": "Password updated successfully"}


async def update_settings(self, new_settings: SettingsModel):
    try:
        result = await self.proxy_management.update_settings(new_settings)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.on_event("startup")
async def on_startup():
    await admincheck()
    await proxy_management.load_settings()
    asyncio.create_task(proxy_management.background_check_proxies())
    asyncio.create_task(proxy_management.clear_inactive_proxies())
    asyncio.create_task(proxy_management.background_update_country_codes())


if __name__ == "__main__":
    uvicorn.run("API:app", host="0.0.0.0", port=8042, reload=True)
