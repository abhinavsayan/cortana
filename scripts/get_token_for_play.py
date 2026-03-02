import asyncio
from livekit import api

API_KEY = "devkey"
API_SECRET = "secret"
URL = "http://localhost:7880"

async def main():
    lkapi = api.LiveKitAPI(URL, API_KEY, API_SECRET)
    try:
        response = await lkapi.room.list_rooms(api.ListRoomsRequest())
        if not response.rooms:
            print("No active rooms.")
        for room in response.rooms:
            print(f"Room: {room.name} | Participants: {room.num_participants} | SID: {room.sid}")
    finally:
        await lkapi.aclose()

if __name__ == "__main__":
    asyncio.run(main())
