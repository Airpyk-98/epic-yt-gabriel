import asyncio
import edge_tts

async def main():
    comm = edge_tts.Communicate('This is a longer test sentence to see if we get boundaries.', 'en-US-AnaNeural')
    async for event in comm.stream():
        if event['type'] == 'WordBoundary':
            print(event)

asyncio.run(main())
