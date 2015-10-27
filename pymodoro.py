import sys
import yaml
import argparse
import time
import datetime
import notify2
import threading
import termios
import fcntl
import Queue


class KeyboardCheckThread(threading.Thread):
    def __init__(self, event_queue, exit_signal):
        super(KeyboardCheckThread, self).__init__()
        self.event_queue = event_queue
        self.exit_signal = exit_signal

    def run(self): 
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        new = termios.tcgetattr(fd)
        new[3] = new[3] & ~termios.ICANON & ~termios.ECHO
        termios.tcsetattr(fd, termios.TCSANOW, new)

        oldflags = fcntl.fcntl(fd, fcntl.F_GETFL)
        fcntl.fcntl(fd, fcntl.F_SETFL, oldflags)

        while self.exit_signal.isSet() is False:
            key = sys.stdin.read(1)
            if key in ['q','Q']:
                self.exit_signal.set()
            self.event_queue.put(key)

        termios.tcsetattr(fd, termios.TCSAFLUSH, old)
        fcntl.fcntl(fd, fcntl.F_SETFL, oldflags)


class Timer(object):
    _states = ["Work", "Short Break", "Long Break", "Paused"]

    def __init__(self, work_time, short_break, reps, long_break, update_interval, event_queue, exit_signal):
        self.work_time = work_time
        self.short_break = short_break
        self.reps = reps
        self.long_break = long_break
        self.update_interval = update_interval
        self.event_queue = event_queue
        self.exit_signal = exit_signal

        self.countdown = {
                "mins": 0,
                "seconds": 0}
        self.state = "Work"
        self.paused_state = "Work"

        self.start_timestamp = None
        self.end_timestamp = None
        self.rep_count = 0

        notify2.init('pymodoro.py')

    def start(self):
        key = None
        self.change_state("Work", self.work_time)

        while key not in ['q', 'Q']:
            
            if self.state == "Paused":
                # Pause until we get another p/P
                self.update_display()
                self.end_timestamp = datetime.datetime.now() + datetime.timedelta(minutes=self.countdown["mins"], seconds=self.countdown["seconds"])
                if key in ['p','P']:
                    # Unpause
                    self.state = self.paused_state
                    self.send_notification()

            else:
                if key in ['p','P']:
                    self.paused_state = self.state
                    self.state = "Paused"
                    self.send_notification()

                elif key in ['+']:
                    self.add_1_minute()
                elif key in ['n','N']:
                    # Jump to next phase
                    self.end_timestamp = datetime.datetime.now()

                remaining_seconds = self.calculate_remaining_seconds()
                if remaining_seconds <= 0:
                    # Change state
                    if self.state in ["Long Break", "Short Break"]:
                        self.change_state("Work", self.work_time)
                    elif self.state == "Work":
                        self.rep_count += 1
                        if self.rep_count < self.reps:
                            self.change_state("Short Break", self.short_break)
                        else:
                            self.rep_count = 0
                            self.change_state("Long Break", self.long_break)
                else:
                    # Clock is still running down.  See if we need to send a notification
                    self.check_status_for_notification()

            self.update_display()
            try:
                key = self.event_queue.get(timeout=1)
                self.event_queue.task_done()
            except:
                # No event received, no problem.
                key = None

        self.exit_signal.set()

    def update_display(self):
        help = "[P]ause [+]1Minute [N]ext [Q]uit"
        sys.stdout.write("{0:15} | {1:2}:{2:02}    {3}\r".format(self.state, self.countdown["mins"], self.countdown["seconds"], help))
        sys.stdout.flush()

    def check_status_for_notification(self):
        """
        Send a notification every 5 minutes.
        """
        if (datetime.datetime.now() - self.start_timestamp).total_seconds() > 60 \
                and self.countdown["mins"] % 5 ==  0 \
                and self.countdown["seconds"] == 0:
            self.send_notification()

    def send_notification(self):
        n = None
        if self.state == "Paused":
            n = notify2.Notification("Paused.  {0}:{1:02} minutes remaining.".format(self.countdown["mins"], self.countdown["seconds"]))
        else:
            n = notify2.Notification("{0} for {1}:{2:02}".format(self.state, self.countdown["mins"], self.countdown["seconds"]))
        n.show()

    def change_state(self, new_state, minutes):
        self.state = new_state
        self.start_timestamp = datetime.datetime.now()
        self.end_timestamp = self.start_timestamp + datetime.timedelta(minutes=minutes)
        self.calculate_remaining_seconds()
        # Show notification
        n = notify2.Notification("Start {0} for {1} minutes".format(self.state, self.countdown["mins"]))
        n.show()

    def calculate_remaining_seconds(self):
        remaining_seconds = (self.end_timestamp - datetime.datetime.now()).total_seconds()
        remaining_seconds = int(round(remaining_seconds))
        self.countdown["mins"] = int(remaining_seconds / 60.0)
        self.countdown["seconds"] = remaining_seconds % 60
        return remaining_seconds

    def add_1_minute(self):
        self.end_timestamp += datetime.timedelta(minutes=1)


def main():
    parser = argparse.ArgumentParser("pymodoro.py")
    parser.add_argument("-c", "--config", default="pymodoro.yaml")
    args = parser.parse_args()

    config = None
    with open(args.config, "r") as fh:
        config = yaml.load(fh)

    event_queue = Queue.Queue()
    exit_signal = threading.Event()

    timer = Timer(
            work_time=config["work_time"],
            short_break=config["short_break"],
            long_break=config["long_break"],
            reps=config["reps"],
            update_interval=config["update_interval"],
            event_queue=event_queue,
            exit_signal=exit_signal)

    keyboard_thread = KeyboardCheckThread(event_queue=event_queue, exit_signal=exit_signal)
    keyboard_thread.start()

    timer.start()
    keyboard_thread.join()

if __name__ == "__main__":
    sys.exit(main())
