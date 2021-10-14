from asyncio import Lock
from contextlib import asynccontextmanager

class RWLock(object):
    """ RWLock class; this is meant to allow an object to be read from by
        multiple threads, but only written to by a single thread at a time. See:
        https://en.wikipedia.org/wiki/Readers%E2%80%93writer_lock
        Usage:
            from rwlock import RWLock
            my_obj_rwlock = RWLock()
            # When reading from my_obj:
            with my_obj_rwlock.r_locked():
                do_read_only_things_with(my_obj)
            # When writing to my_obj:
            with my_obj_rwlock.w_locked():
                mutate(my_obj)
    """

    def __init__(self):
        self.w_lock = Lock()
        self.num_r_lock = Lock()
        self.num_r = 0

    async def r_acquire(self):
        await self.num_r_lock.acquire()
        self.num_r += 1
        if self.num_r == 1:
            await self.w_lock.acquire()
        self.num_r_lock.release()

    async def r_release(self):
        assert self.num_r > 0
        await self.num_r_lock.acquire()
        self.num_r -= 1
        if self.num_r == 0:
            self.w_lock.release()
        self.num_r_lock.release()
    
    @asynccontextmanager
    async def r_locked(self):
        try:
            await self.r_acquire()
            yield
        finally:
            await self.r_release()

    async def w_acquire(self):
        await self.w_lock.acquire()

    async def w_release(self):
        self.w_lock.release()

    @asynccontextmanager
    async def w_locked(self):
        try:
            await self.w_acquire()
            yield
        finally:
            await self.w_release()