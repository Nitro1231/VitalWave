# src/vitalwave/receiver.py

import asyncio
import logging
import threading

from queue import Queue
from bleak import BleakClient, BleakScanner


log = logging.getLogger(__name__)

DEVICE_ADDRESS = "10:bd:a3:b0:e5:f6"
TX_UUID = "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"

METRICS = {
    "HR": ("Heart rate", "bpm"),
    "BR": ("Breathing rate", "/min"),
    "D": ("Distance", "m"),
}

PHASES = {
    "TP": "Total phase",
    "BP": "Breath phase",
    "HP": "Heart phase",
}


class RadarReceiver:
    """Find the radar, stay connected, and queue each reading."""

    def __init__(self, address=DEVICE_ADDRESS, tx_uuid=TX_UUID):
        self.address = address.lower()
        self.tx_uuid = tx_uuid
        self.events = Queue()
        self._stop = threading.Event()

    def start(self):
        threading.Thread(target=self._run, daemon=True).start()

    def stop(self):
        self._stop.set()

    def _run(self):
        asyncio.run(self._listen())

    def _status(self, text):
        log.info(text)
        self.events.put(("status", text))

    async def _wait(self, seconds):
        for _ in range(int(seconds * 10)):
            if self._stop.is_set():
                return
            await asyncio.sleep(0.1)

    async def _listen(self):
        while not self._stop.is_set():
            self._status("Scanning...")
            device = await self._find()
            if device is None:
                self._status("Radar not found. Retrying...")
                await self._wait(2)
                continue

            try:
                await self._stream(device)
            except Exception:
                log.exception("Connection lost. Retrying...")
                self.events.put(("status", "Connection lost. Retrying..."))
            await self._wait(2)

    async def _find(self):
        found = await BleakScanner.discover(timeout=5.0, return_adv=True)
        for device, advertisement in found.values():
            name = advertisement.local_name or device.name or ""
            log.info("Found: %s (%s)", name, device.address)
            if device.address.lower() == self.address:
                return device
        return None

    async def _stream(self, device):
        self._status("Connecting...")
        async with BleakClient(device) as client:
            self._status("Connected")
            await client.start_notify(self.tx_uuid, self._on_notify)
            while client.is_connected and not self._stop.is_set():
                await asyncio.sleep(0.2)

    def _on_notify(self, _characteristic, data):
        text = bytes(data).decode("utf-8", errors="ignore").strip()
        for line in text.splitlines():
            if "=" not in line:
                continue
            key, raw = line.split("=", 1)
            try:
                value = float(raw)
            except ValueError:
                continue
            self.events.put(("value", key.strip(), value))
