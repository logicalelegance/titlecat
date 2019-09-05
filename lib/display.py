class FrameBuffer:

    """Frame buffer for LED Matrix"""
    def __init__(self, width, height):
        # Single frame buffer, encoding brightness as
        # pixel value. Values of 0 are turned off
        self.width = width
        self.height = height
        self._framebuffer = bytearray(width * height)

    def blit(self, x, y, buffer, width, height):
        start_pos = y * self.width + x

        # Need to skip at byte boundaries
        storage_width = int((width + 8) / 8) * 8
        for y1 in range(0, height):
            for x1 in range(0, width):
                source_byte_pos = int((x1 + y1 * storage_width) / 8)
                source_bit_pos = x1 & 0x7
                if ((buffer[source_byte_pos] & (0b10000000 >> source_bit_pos))):
                    self._framebuffer[start_pos + x1 + (y+y1) * self.width] = 0xff
                else:
                    self._framebuffer[start_pos + x1 + (y+y1) * self.width] = 0x00

    def set_pixel_value(self, x, y, val):
        self._framebuffer[x + y * self.width] = val

    def clear_buffer(self):
        for x in range(self.width):
            for y in range(self.height):
                self.set_pixel_value(x, y, 0)

    def draw_string(self, x, y, msg, font, fill = False):
        max_str_length = int(self.width / (font.width + 1))
        if len(msg) > max_str_length:
            msg = msg[:(max_str_length-2)] + '..'
        else:
            msg = msg[:max_str_length] + '.' * (max_str_length - len(msg))
        for c in msg:
            self.blit(x, y, font.glyph(c), font.width, font.height)
            x = x + font.width + 1

        return x - font.width

class font:
    """Convenience class to hold monospace font data and sizeing info"""
    def __init__(self, width, height, fontbuffer):
        self.width = width
        self.height = height
        self.bitmaptable = fontbuffer

    def glyph(self, character):
        index = ord(character) - 32
        if index > len(self.bitmaptable):
            index = ord('?')
        glyph_bits = self.bitmaptable[index]
        return glyph_bits