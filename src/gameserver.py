import sys
import uuid
import shelve
import asyncio
import websockets

import game
import human

from nn.models import Models


MODELS = Models.load('../models')

async def handler(websocket, path):
    # while(True):
    #     await asyncio.sleep(1)
    #     await websocket.send("Hello")
    # print(f'got websocket connection {websocket}')
    # name = await websocket.recv()
    # print(f"< {name}")

    # greeting = f"Hello {name}!"

    # await websocket.send(greeting)
    # print(f"> {greeting}")
    rdeal = game.random_deal()
    
    driver = game.Driver(MODELS, human.WebsocketFactory(websocket))
    driver.set_deal(*rdeal)
    driver.human = [False, False, True, False]

    try:
        await driver.run()

        with shelve.open('gamedb') as db:
            deal_bots = driver.to_dict()
            db[uuid.uuid4().hex] = deal_bots
            print('saved')
    
    except Exception as ex:
        print('Error:', ex)
        raise ex


start_server = websockets.serve(handler, "0.0.0.0", 4443)

asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().run_forever()
