
import device
from subprocess import Popen, PIPE, TimeoutExpired, run
import subprocess
import platform
import re
import os
import time
from concurrent.futures import ThreadPoolExecutor
from subprocess import TimeoutExpired, PIPE, Popen
import signal
import sys
from multiprocessing.connection import Client, Listener, wait, Pipe
from multiprocessing import Queue, Process, Pool, Process, Lock, Value, Array, Manager

__t_pool = ThreadPoolExecutor()


def __cmd_list(cmd, fn=None):
    print('[ cmd ] ', cmd, end='\n')
    if fn is None:
        run(cmd, shell=True)
    else:
        with Popen(cmd, stdout=PIPE, stderr=PIPE, shell=True,
                   preexec_fn=os.setsid, encoding='utf-8') as pipe:
            try:
                res = pipe.communicate()[0]
                fn(res)
            except KeyboardInterrupt as e:
                os.killpg(pipe.pid, signal.SIGINT)
            except TimeoutExpired as e:
                os.killpg(pipe.pid, signal.SIGINT)


def __input_cmd(serial_no, source='', subcmd='', *args):
    '''
    The sources are:
        mouse
        keyboard
        joystick
        touchnavigation
        touchpad
        trackball
        stylus
        dpad
        gesture
        touchscreen
        gamepad
    '''
    if len(subcmd) == 0:
        raise BaseException('subcmd must be not empty')
    s = ''
    for i in args:
        s = s+' '+str(i)
    cmd = 'adb -s %s shell input %s %s %s' % (serial_no, source, subcmd, s)
    __cmd_list(cmd)


def input_roll_cmd(serial_no, *args):
    ''' roll <dx> <dy> (Default: trackball)'''
    __input_cmd(serial_no,  'trackball', 'roll', *args)


def input_press_cmd(serial_no, *args):
    ''' press(Default: trackball)'''
    __input_cmd(serial_no, 'trackball', 'press', *args)


def input_tap_cmd(serial_no, *args):
    '''tap <x> <y> (Default: touchscreen)'''
    __input_cmd(serial_no, 'touchscreen', 'tap', *args)


def input_keyevent_cmd(serial_no, *args):
    ''' keyevent [--longpress] <key code number or name> ... (Default: keyboard)
    keyevent map list: https://developer.android.com/reference/android/view/KeyEvent.html
    '''
    __input_cmd(serial_no,  'keyboard', 'keyevent', * args)


def input_text_cmd(serial_no, *args):
    '''adb shell input text hello'''
    __input_cmd(serial_no, 'touchscreen', 'text', *args)


def input_swipe_cmd(serial_no, *args):
    '''swipe <x1> <y1> <x2> <y2> [duration(ms)] (Default: touchscreen)'''
    __input_cmd(serial_no, 'swipe', *args)


def capture_event(serial_no):
    cmd = 'adb -s {}  shell getevent -lp'.format(serial_no)
    ret = os.popen(cmd).readlines()
    xmin = 0.0
    xmax = 0.0
    ymin = 0.0
    ymax = 0.0
    screen_width = 0.0
    screen_height = 0.0

    def get_value(line):
        elems = line.split(',')
        for e in elems:
            if 'min' in e:
                min_str = e.strip().split(" ")[1]
            elif 'max' in e:
                max_str = e.strip().split(" ")[1]
        return (float(min_str), float(max_str))

    for line in ret[1:]:
        if 'ABS_MT_POSITION_X' in line:
            (xmin, xmax) = get_value(line)
        elif 'ABS_MT_POSITION_Y' in line:
            (ymin, ymax) = get_value(line)
    cmd = 'adb -s {}  shell wm size'.format(serial_no)
    ret = os.popen(cmd).readlines()[0].split(':')[1].strip().split('x')
    screen_width = float(ret[0].strip())
    screen_height = float(ret[1].strip())
    # print(xmin, xmax, ymin, ymax, screen_width, screen_height)
    # 360.3336422613531,1997.8537836682342
    cmd = 'adb -s {}  shell getevent -tl'.format(serial_no)
    with Popen(cmd, stdout=PIPE, stderr=PIPE, shell=True,
               preexec_fn=os.setsid, encoding='utf-8') as pipe:
        try:
            # i = 0
            line_y = ''
            line_x = ''
            for line in iter(lambda: pipe.stdout.readline(), ''):
                if 'ABS_MT_POSITION_X' in line:
                    ABS_MT_POSITION_X = line.split(
                        "ABS_MT_POSITION_X")[-1].strip()
                    raw_x = (int(ABS_MT_POSITION_X, 16) - xmin) * \
                        screen_width / (xmax - xmin)
                    # print(ABS_MT_POSITION_X,int(ABS_MT_POSITION_X,16),raw_x)
                    line_x = line.replace(ABS_MT_POSITION_X, str(raw_x))
                    line = line.replace(ABS_MT_POSITION_X, str(raw_x))
                elif 'ABS_MT_POSITION_Y' in line:
                    ABS_MT_POSITION_Y = line.split(
                        "ABS_MT_POSITION_Y")[-1].strip()
                    raw_y = (int(ABS_MT_POSITION_Y, 16) - ymin) * \
                        screen_height / (ymax - ymin)
                    line_y = line.replace(ABS_MT_POSITION_Y, str(raw_y))
                    line = line.replace(ABS_MT_POSITION_Y, str(raw_y))
                elif 'BTN_TOUCH' in line and 'DOWN' in line:
                    print('='*100)
                    sys.stdout.write(line_x)
                    sys.stdout.write(line_y)
                    sys.stdout.write(line)
                elif 'BTN_TOUCH' in line and 'UP' in line:
                    sys.stdout.write(line_x)
                    sys.stdout.write(line_y)
                    sys.stdout.write(line)
                    pass
                # sys.stdout.write('[{}] {}'.format(i, line))
                # i += 1
        except KeyboardInterrupt as e:
            os.killpg(pipe.pid, signal.SIGINT)
        except TimeoutExpired as e:
            os.killpg(pipe.pid, signal.SIGINT)
            # out_bytes = pipe.communicate()[0]
    # server_start(cmd,child_conn,queue)
    # client_start(parent_conn,queue)


switch_to_queue = False
parent_conn, child_conn = Pipe()
queue = Queue()
address = ('localhost', 6000)
family = 'AF_UNIX'


def server_start(cmd, child_conn=None, queue=None):
    def task(conn):
        print('server side start')
        # if switch_to_queue and queue:
        #     for i in range(0,10):
        #         queue.put('[queue] coming from server side')
        #         time.sleep(1)
        # elif conn:
        #     for i in range(0,10):
        #         conn.send('[pip] coming from server side...{}'.format(i))
        #         time.sleep(0.3)
        #     conn.send('exit')

        with Client(address) as client:
            for i in range(0, 10):
                client.send('push {} msg to client '.format(i))

    p = Process(target=task, args=(child_conn,))
    p.start()
    # p.join()
    # with ProcessPoolExecutor() as proc_exe:
    #     proc_exe.submit(task)


def client_start(conn=None, queue=None):
    print('client side start')
    result = None
    # while True:
    #     if switch_to_queue and queue:
    #         result = queue.get()
    #     elif conn:
    #         result = conn.recv()
    #         print('result:',result)
    #         if 'exit' in result:
    #             break

    with Listener(address) as listener:
        with listener.accept() as conn:
            while True:
                try:
                    ret = conn.recv()
                except EOFError as e:
                    print('error:', e.__cause__)
                    break
                else:
                    print('result:', ret)
    print('client side end')


def main():
    d = device.get_devices()[0]
    # capture_event(device.get_devices()[0])
    # input_cmd(d, 'text', 'afdsf', 'adfafs')
    input_keyevent_cmd(d, '223')
    input_keyevent_cmd(d, '224')


if __name__ == '__main__':
    main()