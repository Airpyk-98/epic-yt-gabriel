import asyncio
import edge_tts

async def main():
    comm = edge_tts.Communicate('test', 'en-US-AnaNeural')
    async for event in comm.stream():
        print(event)

asyncio.run(main())
