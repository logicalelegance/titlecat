# AS 1130 driver goes here
from micropython import const

# Register definitions
REGREG      = const(0xFD)
#DOTCORR     = const(0x80)
CONTROL     = const(0xC0)

FRAME0      = const(0x01)
#FRAME1      = const(0x02)
#FRAME2      = const(0x03)
#FRAME3      = const(0x04)
#FRAME4      = const(0x05)
#FRAME5      = const(0x06)
#FRAME6      = const(0x07)
#FRAME7      = const(0x08)
#FRAME8      = const(0x09)
#FRAME9      = const(0x0A)

PWM0        = const(0x40)
#PWM1        = const(0x41)
#PWM2        = const(0x42)
#PWM3        = const(0x43)
#PWM4        = const(0x44)
#PWM5        = const(0x45)
#PWM6        = const(0x46)
#PWM7        = const(0x47)
#PWM8        = const(0x48)
#PWM9        = const(0x49)

# Control register sub-registers
PICTURE     = const(0x00)
MOVIE       = const(0x01)
MOVIEMODE   = const(0x02)
FRAMETIME   = const(0x03)
DSP_OPTION  = const(0x04)
CURRENT     = const(0x05)
AS_CONFIG   = const(0x06)
#INT_MASK    = const(0x07)
#INT_FRAME   = const(0x08)
SHUTDOWN    = const(0x09)
#I2CMONITOR  = const(0x0A)
#CLK_SYNC    = const(0x0B)
#INT_STATUS  = const(0x0E)
#AS_STATUS   = const(0x0F)
#OPENLED     = const(0x20)

# Various constants
MILLIAMPS_FACTOR = 30.0 / 255.0
NUM_FRAMES = const(36)

class AS1130:
    """Driver base for the AS1130 LED Matrix Controller."""
    def __init__(self):

        # Set up in a sensible default configuration.
        self.set_ram_config(1)
        self.set_current(10)
        self.control_write(DSP_OPTION, 0b11101011)
        self.control_write(MOVIE, 0b01000000)      # Turn movies off
        self.control_write(MOVIEMODE, 0b00000001)
     #   self.control_write(PICTURE, 0b01000000)   # Display frame 1
        self.control_write(FRAMETIME, 0b01110001)
        self.control_write(SHUTDOWN, 0b00000011)  # Turn on the display
        print("Init done")

    def control_write(self, control_register, value):

        # Select the control register
        self._write_register_byte(REGREG, CONTROL)

        # Write the control value to the control subregister
        self._write_register_byte(control_register, value)

    def select_frame(self, frame):

        # Write the frame select register
        # Check the frame is in bounds TODO
        self._write_register_byte(REGREG, frame + FRAME0)

    def select_pwm(self, pwm):

        # Write the PWM select register
        # Check the PWM is in bounds TODO
        self._write_register_byte(REGREG, pwm + PWM0)

    def set_ram_config(self, ram_config):

        self.control_write(AS_CONFIG, ram_config)

    def set_current(self, milliAmps):

        # Convert current to register value
        if milliAmps > 30:
            milliAmps = 30
        if milliAmps < 0:
            milliAmps = 0

        register_value = int(milliAmps * MILLIAMPS_FACTOR)
        self.control_write(CURRENT, 0x80)

    def _write_register_byte(self, register, value):
        # Write a single byte to the specified register
        # Some commands will require to of these, one to
        # select the control register, and one to select the
        # subregister and write the value
        raise NotImplementedError

    def _write_value_at_id(self, id, value):
        # Write a single byte to the specified id (usually a
        # LED on/off position or PWM position)
        raise NotImplementedError

class AS1130_I2C(AS1130):

    """Driver for the AS1130 LED Matrix Controller over I2C."""

    def __init__(self, i2c, *, address=0x30):
        import adafruit_bus_device.i2c_device as i2c_device
        self._i2c = i2c_device.I2CDevice(i2c, address)
        self._buffer = bytearray(2)
        super().__init__()

    def _write_register_byte(self, register, value):

        self._buffer[0] = register & 0xFF
        self._buffer[1] = value & 0xFF
        with self._i2c as i2c:
            i2c.write(self._buffer, start = 0, end = 2)

    def _write_value_at_id(self, id, value):
        self._buffer[0] = id & 0xFF
        self._buffer[1] = value & 0xFF
        with self._i2c as i2c:
            i2c.write(self._buffer, start = 0, end = 2)

    def _databit(self, x, y):
        return(1<<(7-(x&7)))

    def _databyte(self, x, y):
        return int((y*3)+(x/8)) # for a 24x5 display

    def _write_buffer_to_frame(self, framenum, buffer, width, height):
        self.select_frame(framenum)

        # build a buffer to write to the display
        displaybuffer = bytearray(0x18)

        for y in range(0, height):
            for x in range(0, width):
                if (buffer[x + y * width] != 0x00):
                    ledIndex = (x*5+y)
                    registerBitIndex = ledIndex%10
                    registerIndex = int(ledIndex/10)*2+int(registerBitIndex/8)
                    displaybuffer[registerIndex] |= (1<<(registerBitIndex&7))
        displaybuffer[1] |= 0 # PWM Set 0
        for counter in range(0, 0x18):
            self._write_value_at_id(counter, displaybuffer[counter])

        self.select_pwm(0)
        for counter in range(0, 0x18):
            # Set up the blink bits
                self._write_value_at_id(counter, 0x00)

        for counter in range(0x18, 0x9B):
            # Set all PWM values
            self._write_value_at_id(counter, 0xFF)


    # Draw a large framebuffer to the screen, breaking it up in to frames that
    # fit
    def draw_framebuffer(self, framebuffer):
        width = framebuffer.width
        height = framebuffer.height

        numberofframes = int(width / 24)

        for frame in range(0, numberofframes):

            # copy subframe
            subframe = bytearray(24*5)
            for x in range(0, 24):
                for y in range(0, 5):
                    subframe[x + y * 24] = framebuffer._framebuffer[x + 24 * frame + width * y]
            self._write_buffer_to_frame(frame, subframe, int(width / numberofframes), height)

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
        for y1 in range(0, height):
            for x1 in range(0, width):
                source_byte_pos = int((x1 + y1 * width) / 8)
                source_bit_pos = x1 & 0x7
                if ((buffer[source_byte_pos] & (0b10000000 >> source_bit_pos))):
                    self._framebuffer[start_pos + x1 + (y+y1) * self.width] = 0xff
                else:
                    self._framebuffer[start_pos + x1 + (y+y1) * self.width] = 0x00

    def set_pixel_value(self, x, y, val):
        self._framebuffer[x + y * self.width] = 0xff

    def clear_buffer(self):
        self._framebuffer = bytearray(width * height)

    @property
    def framebuffer(self):
        return self._framebuffer

class font:
    """Convenience class to hold monospace font data and sizeing info"""
    def __init(self, width, height, fontbuffer):
        self.width = width
        self.height = height
        self._bitmaptable = fontbuffer

    def glyph(self, character):
        index = int(character) - 32
        mv = memoryview(self._bitmaptable)
        glyph_bits = mv[index]
        return glyph_bits

################################### END OF AS1130 DRIVER ############################