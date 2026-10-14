"""CLI entry point for iot-gateway."""

import asyncio
import logging
import signal
import sys

from .config import GatewayConfig
from .gateway import Gateway

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("iot-gateway")


def main() -> None:
    config = GatewayConfig.from_env()
    gateway = Gateway(config)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def _run() -> None:
        # Catch SIGINT/SIGTERM for graceful shutdown
        loop.add_signal_handler(signal.SIGINT, lambda: asyncio.create_task(gateway.shutdown()))
        loop.add_signal_handler(signal.SIGTERM, lambda: asyncio.create_task(gateway.shutdown()))
        try:
            await gateway.start()
        except KeyboardInterrupt:
            pass
        finally:
            await gateway.shutdown()

    try:
        loop.run_until_complete(_run())
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()
        logger.info("Gateway stopped")


if __name__ == "__main__":
    main()
