# src/short_example/radar_receiver.py

import asyncio

from bleak import BleakScanner
from bleak import BleakClient


DEVICE_ADDRESS = "10:bd:a3:b0:e5:f6"
TX_UUID = "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"


VALUES = {
    "TP": "Total phase",
    "BP": "Breath phase",
    "HP": "Heart phase",
    "BR": "Breathing rate",
    "HR": "Heart rate",
    "D":  "Distance"
}


def notification_handler(characteristic, data):
    try:
        message = data.decode("utf-8").strip()

        if not message:
            return

        key, value = message.split("=", 1)

        value = float(value)
        name = VALUES.get(key, key)

        print(f"{name:16s}: {value:.2f}")

    except Exception:
        print("Raw:", data)


async def main():
    print("Scanning for radar...")
    devices = await BleakScanner.discover(timeout=5.0, return_adv=True)
    target = None

    for device, advertisement in devices.values():
        name = (advertisement.local_name or device.name or "")

        print(f"Found: {name} ({device.address})")

        if device.address.lower() == DEVICE_ADDRESS:
            target = device
            break

    if target is None:
        print()
        print(f"{DEVICE_ADDRESS} was not found.")
        return

    print()
    print("Radar found.")
    print("Connecting...")


    async with BleakClient(target) as client:
        print("Connected.")
        print("Receiving radar data...")
        print()

        await client.start_notify(TX_UUID, notification_handler)

        # Keep the program running
        while True:
            await asyncio.sleep(1)


asyncio.run(main())
