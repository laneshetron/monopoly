from subprocess import Popen
import asyncio
import re

class Tasker:
    @asyncio.coroutine
    def receive(self, message):
        # Passthrough commands to scripts in a designated directory
        # Sanitize input to ensure this dir cannot be escaped
