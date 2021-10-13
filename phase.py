import asyncio

class Phase:
  TO_INITIAL = -0.5
  INITIAL = 0
  TO_WAITING = 0.5
  WAITING = 1
  BETWEEN_WAITING_AND_PLAYING = 1.5
  PLAYING = 2

  def __init__(self):
    self.lock = asyncio.Lock()
    self.val = self.INITIAL_PHASE

  def set(self, val):
    async with self.lock:
      self.phase = val
  
  async def get(self):
    async with self.lock:
      return self.phase
  