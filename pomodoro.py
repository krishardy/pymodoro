import sys
import yaml
import argparse
import time
import datetime
import notify2

class Timer(object):
    _states = ["Work", "Short Break", "Long Break", "Paused"]

    def __init__(self, work_time, short_break, reps, long_break, update_interval):
        self.work_time = work_time
        self.short_break = short_break
        self.reps = reps
        self.long_break = long_break
        self.update_interval = update_interval

        self.countdown = {
                "mins": 0,
                "seconds": 0}
        self.state = "Work"

        self.start_timestamp = None
        self.end_timestamp = None
        self.rep_count = 0

        notify2.init('pomodoro.py')

    def start(self):
        self.change_state("Work")
        while True:
            remaining_seconds = self.calculate_remaining_seconds()

            if remaining_seconds <= 0:
                # Change state
                if self.state in ["Long Break", "Short Break"]:
                    self.change_state("Work")
                elif self.state == "Work":
                    self.rep_count += 1
                    if self.rep_count < self.reps:
                        self.change_state("Short Break")
                    else:
                        self.rep_count = 0
                        self.change_state("Long Break")
                 
            sys.stdout.write("{0} | {1}:{2:02}\r".format(self.state, self.countdown["mins"], self.countdown["seconds"]))
            sys.stdout.flush()
            time.sleep(self.update_interval)

    def change_state(self, new_state):
        self.state = new_state
        self.start_timestamp = datetime.datetime.now()
        self.end_timestamp = self.start_timestamp + datetime.timedelta(minutes=self.work_time)
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

    def pause(self):
        print("Paused.  Press space to resume.")
        pass

def main():
    parser = argparse.ArgumentParser("pomodoro.py")
    parser.add_argument("-c", "--config", default="pomodoro.yaml")
    args = parser.parse_args()

    config = None
    with open(args.config, "r") as fh:
        config = yaml.load(fh)

    timer = Timer(
            work_time=config["work_time"],
            short_break=config["short_break"],
            long_break=config["long_break"],
            reps=config["reps"],
            update_interval=config["update_interval"])
    timer.start()

if __name__ == "__main__":
    sys.exit(main())
