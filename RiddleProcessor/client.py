import asyncio
import socketio

sio = socketio.AsyncClient()

wav_file = open("test_output.wav", "rb").read()

async def handle_wav():
    await sio.emit("handle_wav", wav_file)
    print("Message sent!")

@sio.event
async def connect():
    print('connection established')

@sio.event
async def disconnect():
    print('disconnected from server')

@sio.on('processed')
async def on_processed(data):
    print("Server response:", data['message'])

@sio.on('error')
async def on_error(error):
    print("Error:", error['message'])

async def main():
    await sio.connect('http://192.168.88.46:8081')
    await handle_wav()
    await sio.wait()

if __name__ == '__main__':
    asyncio.run(main())
