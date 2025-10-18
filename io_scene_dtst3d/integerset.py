import struct
from typing import List, BinaryIO

# The standard mathmatical set, where there are no duplicates.  However,
# this set uses bits instead of numbers.
class TSIntegerSet:
    def __init__(self):
        values: List[int]

    def copy_from(self, other):
        self.values = other.values.copy()

    def read(self, stream : BinaryIO):
        reader = stream

        self.values = [0] * 64

        # numInts, unused
        struct.unpack('<L', reader.read(4))

        # sz
        sz = struct.unpack('<L', reader.read(4))[0]
        for x in range(sz):
            self.values[x] = struct.unpack('<L', reader.read(4))[0]