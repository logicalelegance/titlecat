import time

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
MILLIAMPS_FACTOR = 255.0 / 30
NUM_FRAMES = const(36)

class AS1130:
    """Driver base for the AS1130 LED Matrix Controller."""
    def __init__(self):
        # Set up in a sensible default configuration.
        time.sleep(0.25)
        # reset
        self.control_write(SHUTDOWN, 0b00000000)  # Turn on the display

        self.set_ram_config(1)
        self.set_current(18)
        self.control_write(DSP_OPTION, 0b11101011)
        self.control_write(MOVIE, 0b00000000)      # Turn movies off
        self.control_write(MOVIEMODE, 0b00000000)
        self.control_write(PICTURE, 0b00000000)   # Display frame 1
        self.control_write(FRAMETIME, 0b01110001)
        self.control_write(SHUTDOWN, 0b00000011)  # Turn on the display
        print("Init done")

    def control_write(self, control_register, value):

        # Select the control register
        self._write_register_byte(REGREG, CONTROL)

        # Write the control value to the control subregister
        self._write_register_byte(control_register, value)

    def play_movie(self, play):
        if play:
            self.control_write(PICTURE, 0b00000000)   # Display frame 1
            self.control_write(MOVIE, 0b01000000)      # Turn movies on
            self.control_write(DSP_OPTION, 0b11101011)

        else:
            self.control_write(MOVIE, 0b00000000)      # Turn movies off
            self.control_write(PICTURE, 0b01000000)   # Display frame 1
            self.control_write(DSP_OPTION, 0b00001011)

    def set_movie_frames(self, frames):
        frames = frames - 1
        self.control_write(MOVIEMODE, frames)

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
        self.control_write(CURRENT, register_value)

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

    def _databit(self, x, y):
        return(1<<(7-(x&7)))

    def _databyte(self, x, y):
        return int((y*3)+(x/8)) # for a 24x5 display

    def _write_buffer_to_frame(self, framenum, buffer, width, height, use_pwm = False):
        self.select_frame(framenum)

        # build a buffer to write to the display
        displaybuffer = bytearray(0x18)
        pwmbuffer = bytearray(132)
        for y in range(0, height):
            for x in range(0, width):
                ledIndex = (x*5+y)
                pwmbuffer[ledIndex] = buffer[x + y * width]
                registerBitIndex = ledIndex%10
                registerIndex = int(ledIndex/10)*2+int(registerBitIndex/8)
                if (buffer[x + y * width] != 0x00):
                    displaybuffer[registerIndex] |= (1<<(registerBitIndex&7))
                else:
                    displaybuffer[registerIndex] &= ~(1<<(registerBitIndex&7))

        displaybuffer[1] |= 0 # PWM Set 0
        for counter in range(0, 0x18):
            self._write_value_at_id(counter, displaybuffer[counter])

        self.select_pwm(0)
        for counter in range(0, 0x18):
            # Set up the blink bits
                self._write_value_at_id(counter, 0x00)

        for y in range(0, height):
            for x in range(0, width):
                ledIndex = (x*5+y)
                counter = ledIndex + 0x18
                # Set all PWM values
                if use_pwm:
                    self._write_value_at_id(counter, pwmbuffer[ledIndex])
                else:
                    self._write_value_at_id(counter, 0xFF)

    # Draw a large framebuffer to the screen, breaking it up in to frames that
    # fit
    def draw_framebuffer(self, framebuffer, clip_to_x = 0, use_pwm = False):
        width = framebuffer.width
        height = framebuffer.height
        clip_by = framebuffer.width - clip_to_x

        numberofframes = int(width / 24)
        numberofHWframes = int((width - clip_by) / 24) + 1

        if numberofHWframes > numberofframes:
            numberofHWframes = numberofframes

      #  self.set_movie_frames(numberofHWframes)
        self.set_movie_frames(numberofframes)

        for frame in range(0, numberofframes):

            # copy subframe
            subframe = bytearray(24*5)
            for x in range(0, 24):
                for y in range(0, 5):
                    subframe[x + y * 24] = framebuffer._framebuffer[x + (24 * frame) + width * y]
            self._write_buffer_to_frame(frame, subframe, int(width / numberofframes), height, use_pwm)

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

################################### END OF AS1130 DRIVER ############################