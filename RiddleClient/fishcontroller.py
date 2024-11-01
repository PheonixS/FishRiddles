import signal
from .consts import *
import smbus2
import time
from enum import Enum

class FishControllerStatuses(Enum):
    ACTION_COMPLETED = 0x10

class FishController:
    def __init__(self, pipe, i2c_bus=1, device_address=0x08):
        # Initialize the I2C bus and device address
        self.bus = smbus2.SMBus(i2c_bus)
        self.device_address = device_address
        self.pipe = pipe

        # internal stuff
        self.exiting = False

        def handle_sigterm(signum, frame):
            print("FishController: Received SIGTERM or SIGINT. Shutting down gracefully...")
            self.exiting = True

        signal.signal(signal.SIGTERM, handle_sigterm)
        signal.signal(signal.SIGINT, handle_sigterm)

    def send_status_on_completion(func):
        def wrapper(self, *args, **kwargs):
            result = func(self, *args, **kwargs)
            self.pipe.send(FishControllerStatuses.ACTION_COMPLETED)
            return result
        return wrapper

    def process(self):
        self._cleanup_bus()
        self._assume_control()

        print("Fish puppet under control")

        try:
            while not self.exiting:
                if self.pipe.poll(timeout=1):
                    method_name, args = self.pipe.recv()
                    method = getattr(self, method_name)
                    method(*args)
                else:
                    time.sleep(0.1)
        except Exception as e:
            print(f"Child process exception: {e}")
        finally:
            self.head_down()
            self._leave_body()
            self.bus.close()

    # FIXME: this is hack to stabilize bus

    def _cleanup_bus(self):
        for r in [CONTROL_STATUS, MOUTH_STATUS, TAIL_STATUS, HEAD_STATUS]:
            self._get_state(r)
            time.sleep(0.2)

    def _set_state(self, register, value):
        try:
            # Write the state (1 or 0) to the mouth state register
            self.bus.write_byte_data(self.device_address, register, value)
        except Exception as e:
            print(f"Error writing to mouth state register: {e}")

    def _get_state(self, register) -> int:
        try:
            return self.bus.read_byte_data(self.device_address, register)
        except Exception as e:
            print(f"Error reading from mouth state register: {e}")
            return None

    def _wait_for_state(self, register, want):
        while not self.exiting and (self._get_state(register) != want):
            time.sleep(0.1)

    def _assume_control(self):
        self._set_state(DIRECT_CONTROL_REG, CONTROL_REQUESTED)
        self._wait_for_state(CONTROL_STATUS, CONTROL_UNDER_CONTROL)

    def _leave_body(self):
        self._set_state(DIRECT_CONTROL_REG, CONTROL_LEAVE)
        self._wait_for_state(CONTROL_STATUS, CONTROL_IDLE)

    @send_status_on_completion
    def head_up(self):
        self._set_state(HEAD_REG, MOTOR_UP_REQUESTED)
        self._wait_for_state(HEAD_STATUS, MOTOR_UP)

    @send_status_on_completion
    def head_down(self):
        self._set_state(HEAD_REG, MOTOR_DOWN_REQUESTED)
        self._wait_for_state(HEAD_STATUS, MOTOR_IDLE)

    @send_status_on_completion
    def tail_up(self):
        self._set_state(TAIL_REG, MOTOR_UP_REQUESTED)
        self._wait_for_state(TAIL_STATUS, MOTOR_UP)

    @send_status_on_completion
    def tail_down(self):
        self._set_state(TAIL_REG, MOTOR_DOWN_REQUESTED)
        self._wait_for_state(TAIL_STATUS, MOTOR_IDLE)

    @send_status_on_completion
    def mouth_open(self):
        self._set_state(MOUTH_REG, MOTOR_UP_REQUESTED)
        self._wait_for_state(MOUTH_STATUS, MOTOR_UP)

    @send_status_on_completion
    def mouth_close(self):
        self._set_state(MOUTH_REG, MOTOR_DOWN_REQUESTED)
        self._wait_for_state(MOUTH_STATUS, MOTOR_IDLE)
