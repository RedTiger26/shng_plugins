#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2013 - 2015 KNX-User-Forum e.V.    http://knx-user-forum.de/
#  Copyright 2022        Julian Scholle     julian.scholle@googlemail.com
#  Copyright 2024 -      Sebastian Helms         morg @ knx-user-forum.de
#########################################################################
#
#  SML module for SmartMeter plugin for SmartHomeNG
#
#  This file is part of SmartHomeNG.py.
#  Visit:  https://github.com/smarthomeNG/
#          https://knx-user-forum.de/forum/supportforen/smarthome-py
#          https://smarthomeng.de
#
#  SmartHomeNG.py is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  SmartHomeNG.py is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with SmartHomeNG.py. If not, see <http://www.gnu.org/licenses/>.
#########################################################################


__license__ = "GPL"
__version__ = "2.0"
__revision__ = "0.1"
__docformat__ = 'reStructuredText'

import asyncio
import errno
import logging
import serial
try:
    import serial_asyncio
    ASYNC_IMPORTED = True
except ImportError:
    ASYNC_IMPORTED = False
import socket
import time
import traceback

from smllib.reader import SmlStreamReader
from smllib import const as smlConst
from threading import Lock
from typing import Union

# only for syntax/type checking
try:
    from lib.model.smartplugin import SmartPlugin
except ImportError:
    class SmartPlugin():
        pass

    class SmartPluginWebIf():
        pass

"""
This module implements the query of a smartmeter using the SML protocol.
The smartmeter needs to have an infrared interface and an IR-Adapter is needed for USB.

Abbreviations
-------------
OBIS
   OBject Identification System (see iec62056-61{ed1.0}en_obis_protocol.pdf)
"""


OBIS_NAMES = {
    **smlConst.OBIS_NAMES,
    '010000020000': 'Firmware Version, Firmware Prüfsumme CRC, Datum',
    '0100010800ff': 'Bezug Zählerstand Total',
    '0100010801ff': 'Bezug Zählerstand Tarif 1',
    '0100010802ff': 'Bezug Zählerstand Tarif 2',
    '0100011100ff': 'Total-Zählerstand',
    '0100020800ff': 'Einspeisung Zählerstand Total',
    '0100020801ff': 'Einspeisung Zählerstand Tarif 1',
    '0100020802ff': 'Einspeisung Zählerstand Tarif 2',
    '0100600100ff': 'Server-ID',
    '010060320101': 'Hersteller-Identifikation',
    '0100605a0201': 'Prüfsumme',
}

# serial config
S_BITS = serial.EIGHTBITS
S_PARITY = serial.PARITY_NONE
S_STOP = serial.STOPBITS_ONE


if __name__ == '__main__':
    logger = logging.getLogger(__name__)
    logger.debug(f"init standalone {__name__}")
else:
    logger = logging.getLogger(__name__)
    logger.debug(f"init plugin component {__name__}")


#
# internal testing
#
TESTING = False
# TESTING = True

if TESTING:
    if __name__ == '__main__':
        from sml_test import RESULT
    else:
        from .sml_test import RESULT
    logger.error(f'SML testing mode enabled, no serial communication, no real results! Dataset is {len(RESULT)} bytes long.')
else:
    RESULT = b''


#
# start module code
#


def to_hex(data: Union[int, str, bytes, bytearray], space: bool = True) -> str:
    """
    Returns the hex representation of the given data
    """
    if isinstance(data, int):
        return hex(data)

    if isinstance(data, str):
        if space:
            return " ".join([data[i:i + 2] for i in range(0, len(data), 2)])
        else:
            return data

    templ = "%02x"
    if space:
        templ += " "
    return "".join(templ % b for b in data).rstrip()


def format_time(timedelta):
    """
    returns a pretty formatted string according to the size of the timedelta
    :param timediff: time delta given in seconds
    :return: returns a string
    """
    if timedelta > 1000.0:
        return f"{timedelta:.2f} s"
    elif timedelta > 1.0:
        return f"{timedelta:.2f} s"
    elif timedelta > 0.001:
        return f"{timedelta*1000.0:.2f} ms"
    elif timedelta > 0.000001:
        return f"{timedelta*1000000.0:.2f} µs"
    elif timedelta > 0.000000001:
        return f"{timedelta * 1000000000.0:.2f} ns"

#
# asyncio reader
#


class AsyncReader():

    def __init__(self, logger, plugin: SmartPlugin, config: dict):
        self.buf = bytes()
        self.logger = logger
        self.lock = config['lock']

        if not ASYNC_IMPORTED:
            raise ImportError('pyserial_asyncio not installed, running asyncio not possible.')
        self.config = config
        self.transport = None
        self.stream = SmlStreamReader()
        self.fp = SmlFrameParser(config)
        self.frame_lock = Lock()

        # set from plugin
        self.plugin = plugin
        self.data_callback = plugin._update_values

        if not ('serial_port' in config or ('host' in config and 'port' in config)):
            raise ValueError(f'configuration {config} is missing source config (serialport or host and port)')

        self.serial_port = config.get('serial_port')
        self.host = config.get('host')
        self.port = config.get('port')
        self.timeout = config.get('timeout', 2)
        self.baudrate = config.get('baudrate', 9600)
        self.target = '(not set)'
        self.buffersize = config.get('sml', {'buffersize': 1024}).get('buffersize', 1024)
        self.listening = False
        self.reader = None

    async def listen(self):
        result = self.lock.acquire(blocking=False)
        if not result:
            self.logger.error('couldn\'t acquire lock, polling/manual access active?')
            return

        self.logger.debug('acquired lock')
        try:  # LOCK
            if self.serial_port:
                self.reader, _ = await serial_asyncio.open_serial_connection(
                    url=self.serial_port,
                    baudrate=self.baudrate,
                    bytesize=S_BITS,
                    parity=S_PARITY,
                    stopbits=S_STOP,
                )
                self.target = f'async_serial://{self.serial_port}'
            else:
                self.reader, _ = await asyncio.open_connection(self.host, self.port)
                self.target = f'async_tcp://{self.host}:{self.port}'

            self.logger.debug(f'target is {self.target}')
            if self.reader is None and not TESTING:
                self.logger.error('error on setting up async listener, reader is None')
                return

            self.plugin.connected = True
            self.listening = True
            self.logger.debug('starting to listen')
            while self.listening and self.plugin.alive:
                if TESTING:
                    chunk = RESULT
                else:
                    try:
                        chunk = await self.reader.read(self.buffersize)
                    except serial.serialutil.SerialException:
                        # possibly port closed from remote site? happens with socat...
                        chunk = b''
                if chunk == b'':
                    self.logger.debug('read reached EOF, quitting')
                    break
                # self.logger.debug(f'read {chunk} ({len(chunk)} bytes), buf is {self.buf}')
                self.buf += chunk

                if len(self.buf) < 100:
                    continue
                try:
                    # self.logger.debug(f'adding {len(self.buf)} bytes to stream')
                    self.stream.add(self.buf)
                except Exception as e:
                    self.logger.error(f'Writing data to SmlStreamReader failed with exception {e}')
                else:
                    self.buf = bytes()
                    # get frames as long as frames are detected
                    while True:
                        try:
                            frame = self.stream.get_frame()
                            if frame is None:
                                # self.logger.debug('didn\'t get frame')
                                break

                            # self.logger.debug('got frame')
                            self.fp(frame)
                        except Exception as e:
                            detail = traceback.format_exc()
                            self.logger.warning(f'Preparing and parsing data failed with exception {e}: and detail: {detail}')

                    # get data from frameparser and call plugin
                    if self.data_callback:
                        self.data_callback(self.fp())

                # just in case of many errors, reset buffer
                # with SmlStreamParser, this should not happen anymore, but who knows...
                if len(self.buf) > 100000:
                    self.logger.error("Buffer got to large, doing buffer reset")
                    self.buf = bytes()
        finally:
            # cleanup
            try:
                self.reader.feed_eof()
            except Exception:
                pass
            self.plugin.connected = False
            self.lock.release()

    async def stop_on_queue(self):
        """ wait for STOP in queue and signal reader to terminate """
        self.logger.debug('task waiting for STOP from queue...')
        await self.plugin. wait_for_asyncio_termination()
        self.logger.debug('task received STOP, halting listener')
        self.listening = False


#
# single-shot reader
#


class SmlReader():
    def __init__(self, logger, config: dict):
        self.config = config
        self.sock = None
        self.lock = config['lock']
        self.logger = logger

        if not ('serial_port' in config or ('host' in config and 'port' in config)):
            raise ValueError(f'configuration {config} is missing source config (serialport or host and port)')

        if not config.get('poll') and not ASYNC_IMPORTED:
            raise ValueError('async configured but pyserial_asyncio not imported. Aborting.')
        self.serial_port = config.get('serial_port')
        self.host = config.get('host')
        self.port = config.get('port')
        self.timeout = config.get('timeout', 2)
        self.baudrate = config.get('baudrate', 9600)
        self.target = '(not set)'
        self.buffersize = config.get('sml', {'buffersize': 1024}).get('buffersize', 1024)

        logger.debug(f"config='{config}'")

    def __call__(self) -> bytes:

        #
        # open the serial communication
        #
        locked = self.lock.acquire(blocking=False)
        if not locked:
            logger.error('could not get lock for serial/network access. Is another scheduled/manual action still active?')
            return b''

        try:  # lock release
            runtime = time.time()
            self.get_sock()
            if not self.sock:
                # error already logged, just go
                return b''
            logger.debug(f"time to open {self.target}: {format_time(time.time() - runtime)}")

            #
            # read data from device
            #
            response = bytes()
            try:
                response = self.read()
                if len(response) == 0:
                    logger.error('reading data from device returned 0 bytes!')
                    return b''
                else:
                    logger.debug(f'read {len(response)} bytes')

            except Exception as e:
                logger.error(f'reading data from {self.target} failed with error: {e}')

        except Exception:
            # passthrough, this is only for releasing the lock
            raise
        finally:
            #
            # clean up connection
            #
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None
            self.lock.release()
        return response

    def _read(self) -> bytes:
        """ isolate the read method from the connection object """
        if isinstance(self.sock, serial.Serial):
            return self.sock.read()
        elif isinstance(self.sock, socket.socket):
            return self.sock.recv(self.buffersize)
        else:
            return b''

    def read(self) -> bytes:
        """
        This function reads some bytes from serial or network interface
        it returns an array of bytes if a timeout occurs or a given end byte is encountered
        and otherwise b'' if an error occurred
        :returns the read data
        """
        if TESTING:
            return RESULT

        self.logger.debug("start to read data from serial/network device")
        response = bytes()
        while True:
            try:
                # on serial, length is ignored
                data = self._read()
                if data:
                    response += data
                    if len(response) >= self.buffersize:
                        self.logger.debug('read end, length reached')
                        break
                else:
                    if isinstance(self.sock, serial.Serial):
                        self.logger.debug('read end, end of data reached')
                        break
            except socket.error as e:
                if e.args[0] == errno.EAGAIN or e.args[0] == errno.EWOULDBLOCK:
                    self.logger.debug(f'read end, error: {e}')
                    break
                else:
                    raise
            except Exception as e:
                self.logger.debug(f"error while reading from serial/network: {e}")
                return b''

        self.logger.debug(f"finished reading data from serial/network {len(response)} bytes")
        return response

    def get_sock(self):
        """ open serial or network socket """
        if TESTING:
            self.sock = 1
            self.target = '(test input)'
            return

        if self.serial_port:
            #
            # open the serial communication
            #
            count = 0
            while count < 3:
                try:  # open serial
                    count += 1
                    self.sock = serial.Serial(
                        self.serial_port,
                        self.baudrate,
                        S_BITS,
                        S_PARITY,
                        S_STOP,
                        timeout=self.timeout
                    )
                    if not self.serial_port == self.sock.name:
                        logger.debug(f"Asked for {self.serial_port} as serial port, but really using now {self.sock.name}")
                    self.target = f'serial://{self.sock.name}'

                except FileNotFoundError:
                    logger.error(f"Serial port '{self.serial_port}' does not exist, please check your port")
                    return None, ''
                except serial.SerialException:
                    if self.sock is None:
                        if count < 3:
                            # count += 1
                            logger.error(f"Serial port '{self.serial_port}' could not be opened, retrying {count}/3...")
                            time.sleep(3)
                            continue
                        else:
                            logger.error(f"Serial port '{self.serial_port}' could not be opened")
                    else:
                        logger.error(f"Serial port '{self.serial_port}' could be opened but somehow not accessed")
                    return None, ''
                except OSError:
                    logger.error(f"Serial port '{self.serial_port}' does not exist, please check the spelling")
                    return None, ''
                except Exception as e:
                    logger.error(f"unforeseen error occurred: '{e}'")
                    return None, ''

            if self.sock is None:
                if count == 3:
                    logger.error("retries unsuccessful, serial port could not be opened, giving up.")
                else:
                    # this should not happen...
                    logger.error("retries unsuccessful or unforeseen error occurred, serial object was not initialized.")
                return None, ''

            if not self.sock.is_open:
                logger.error(f"serial port '{self.serial_port}' could not be opened with given parameters, maybe wrong baudrate?")
                return None, ''

        elif self.host:
            #
            # open network connection
            #
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            sock.connect((self.host, self.port))
            sock.setblocking(False)
            self.target = f'tcp://{self.host}:{self.port}'

        else:
            logger.error('neither serialport nor host/port was given, no action possible.')
            return None, ''


#
# frame parser
#


class SmlFrameParser():
    def __init__(self, config: dict):
        self.config = config
        self.result = {}

    def __call__(self, frame=None):
        if frame is None:
            res = self.result
            self.result = {}
            return res
        else:
            self.parse_frame(frame)
            return self.result

    def parse_frame(self, frame):
        """ parse single SML frame and add data to result dict """
        obis_values = frame.get_obis()
        for entry in obis_values:
            code = entry.obis.obis_code
            if code not in self.result:
                self.result[code] = []
            content = {
                'obis': code,
                'value': entry.get_value(),
                'valueRaw': entry.get_value(),
                'name': OBIS_NAMES.get(entry.obis)
            }
            # skip scaler calculation as the smllib has done this already
            # if entry.scaler:
            #    content['scaler'] = entry.scaler
            #    content['value'] = round(content['value'] * 10 ** content['scaler'], 1)
            if entry.unit:
                content['unit'] = smlConst.UNITS.get(entry.unit)
                content['unitCode'] = entry.unit
            if entry.val_time:
                content['valTime'] = entry.val_time
                content['actTime'] = time.ctime(self.config.get('date_offset', 0) + entry.val_time)
            if entry.value_signature:
                content['signature'] = entry.value_signature
            if entry.status:
                content['status'] = entry.status
                # Decoding status information if present
                # for bitwise operation, true-ish result means bit is set
                try:
                    content['statRun'] = bool((content['status'] >> 8) & 1)              # True: meter is counting, False: standstill
                    content['statFraudMagnet'] = bool((content['status'] >> 8) & 2)      # True: magnetic manipulation detected, False: ok
                    content['statFraudCover'] = bool((content['status'] >> 8) & 4)       # True: cover manipulation detected, False: ok
                    content['statEnergyTotal'] = bool((content['status'] >> 8) & 8)      # Current flow total. True: -A, False: +A
                    content['statEnergyL1'] = bool((content['status'] >> 8) & 16)        # Current flow L1. True: -A, False: +A
                    content['statEnergyL2'] = bool((content['status'] >> 8) & 32)        # Current flow L2. True: -A, False: +A
                    content['statEnergyL3'] = bool((content['status'] >> 8) & 64)        # Current flow L3. True: -A, False: +A
                    content['statRotaryField'] = bool((content['status'] >> 8) & 128)    # True: rotary field not L1->L2->L3, False: ok
                    content['statBackstop'] = bool((content['status'] >> 8) & 256)       # True: backstop active, False: backstop not active
                    content['statCalFault'] = bool((content['status'] >> 8) & 512)       # True: calibration relevant fatal fault, False: ok
                    content['statVoltageL1'] = bool((content['status'] >> 8) & 1024)     # True: Voltage L1 present, False: not present
                    content['statVoltageL2'] = bool((content['status'] >> 8) & 2048)     # True: Voltage L2 present, False: not present
                    content['statVoltageL3'] = bool((content['status'] >> 8) & 4096)     # True: Voltage L3 present, False: not present
                except Exception:
                    pass

            # Convert some special OBIS values into nicer format
            # EMH ED300L: add additional OBIS codes
            if code == '1-0:96.5.0*255':
                val = int(content['valueRaw'], 16)
                content['value'] = bin(val >> 8)    # Status as binary string, so not decoded into status bits as above
            # end TODO

            # don't return multiple code, only the last one -> overwrite earlier data
            # self.result[code].append(content)
            self.result[code] = [content]
            logger.debug(f"found {code} with {content}")


#
# cyclic parser
#


class SmlParser():
    def __init__(self, config: dict):
        self.fp = SmlFrameParser(config)

    def __call__(self, data: bytes) -> dict:
        return self.parse(data)

    def parse(self, data: bytes) -> dict:
        """ parse data returned from device read """
        stream = SmlStreamReader()
        stream.add(data)

        while True:
            try:
                frame = stream.get_frame()
                if frame is None:
                    break

                self.fp(frame)

            except Exception as e:
                detail = traceback.format_exc()
                logger.warning(f'parsing data failed with error: {e}; details are {detail}')
                # at least return what was decoded up to now
                return self.fp()

        return self.fp()


def query(config) -> dict:
    """
    This function will
    1. open a serial communication line to the smartmeter
    2. reads out the block of OBIS information
    3. closes the serial communication
    4. extract obis data and format return dict

    config contains a dict with entries for
    'serial_port', 'device' and a sub-dict 'sml' with entries for
    'device', 'buffersize', 'date_offset' and additional entries for
    calculating crc ('poly', 'reflect_in', 'xor_in', 'reflect_out', 'xor_out', 'swap_crc_bytes')

    return: a dict with the response data formatted as follows:
        {
            'readout': <full readout lines>,
            '<obis1>': [{'value': <val0>, (optional) 'unit': '<unit0>'}, {'value': <val1>', 'unit': '<unit1>'}, ...],
            '<obis2>': [...],
            ...
        }
    """

    #
    # initialize module
    #

    # for the performance of the serial read we need to save the current time
    starttime = time.time()
    runtime = starttime

    try:
        reader = SmlReader(logger, config)
    except ValueError as e:
        logger.error(f'error on opening connection: {e}')
        return {}
    result = reader()

    logger.debug(f"time for reading OBIS data: {format_time(time.time() - runtime)}")
    runtime = time.time()

    # Display performance of the serial communication
    logger.debug(f"whole communication with smartmeter took {format_time(time.time() - starttime)}")

    #
    # parse data
    #

    parser = SmlParser(config)
    return parser(result)


def discover(config: dict) -> bool:
    """ try to autodiscover SML protocol """

    # as of now, this simply tries to listen to the meter
    # called from within the plugin, the parameters are either manually set by
    # the user, or preset by the plugin.yaml defaults.
    # If really necessary, the query could be called multiple times with
    # reduced baud rates or changed parameters, but there would need to be
    # the need for this.
    # For now, let's see how well this works...
    return bool(query(config))


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Query a smartmeter at a given port for SML output',
                                     usage='use "%(prog)s --help" for more information',
                                     formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('port', help='specify the port to use for the smartmeter query, e.g. /dev/ttyUSB0 or /dev/sml0')
    parser.add_argument('-v', '--verbose', help='print verbose information', action='store_true')
    parser.add_argument('-t', '--timeout', help='maximum time to wait for a message from the smartmeter', type=float, default=3.0)
    parser.add_argument('-b', '--buffersize', help='maximum size of message buffer for the reply', type=int, default=1024)

    args = parser.parse_args()

    # complete default dict
    config = {
        'lock': Lock(),
        'serial_port': '',
        'host': '',
        'port': 0,
        'connection': '',
        'timeout': 2,
        'baudrate': 9600,
        'dlms': {
            'device': '',
            'querycode': '?',
            'baudrate_min': 300,
            'use_checksum': True,
            'onlylisten': False,
            'normalize': True
        },
        'sml': {
            'buffersize': 1024
        }
    }

    config['serial_port'] = args.port
    config['timeout'] = args.timeout
    config['sml']['buffersize'] = args.buffersize

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        # create formatter and add it to the handlers
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s  @ %(lineno)d')
        # formatter = logging.Formatter('%(message)s')
        ch.setFormatter(formatter)
        # add the handlers to the logger
        logging.getLogger().addHandler(ch)
    else:
        logging.getLogger().setLevel(logging.INFO)
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        # just like print
        formatter = logging.Formatter('%(message)s')
        ch.setFormatter(formatter)
        # add the handlers to the logger
        logging.getLogger().addHandler(ch)

    logger.info("This is Smartmeter Plugin, SML module, running in standalone mode")
    logger.info("==================================================================")

    result = query(config)

    if not result:
        logger.info(f"No results from query, maybe a problem with the serial port '{config['serial_port']}' given.")
    elif len(result) > 1:
        logger.info("These are the processed results of the query:")
        try:
            del result['readout']
        except KeyError:
            pass
        try:
            import pprint
        except ImportError:
            txt = str(result)
        else:
            txt = pprint.pformat(result, indent=4)
        logger.info(txt)
    elif len(result) == 1:
        logger.info("The results of the query could not be processed; raw result is:")
        logger.info(result)
    else:
        logger.info("The query did not get any results. Maybe the serial port was occupied or there was an error.")
