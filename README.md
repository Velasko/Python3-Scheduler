# Python3 scheduler using linux's crontab

## Table of contents
* [Introduction](#introduction)
* [Technologies](#technologies)
* [Setup](#setup)

## Introduction

The intention of this project is an asyncio scheduler for tasks to be executed at a certain time. However, instead of having multiple functions with a sleep until the time the execution has come, it unifyies them all into a single loop and let linux itself handle when the the task should be executed.

The problem of using only python-crontab library is that it would create a new process running the python script. If the interest is still having the memory access, a simple crontab schedule wouldn't be enough.

## Technologies

* Ubuntu 20.04
* python 3.8.5
* python-crontab 2.5.1

## Code Examples

To create an scheduler:

```
from scheduler import Scheduler
sched = Scheduler()
```

To add a function to be scheduled:

```
def func(arg):
	print("do stuff here")
	print(arg)

s.add_task(time="*/5 * * * *", func, arg='argument to print')
```

Then, running the asyncio loop should be enough to get it working and executing the task executing on the background.


**Important things to keep in mind:**

* When the exection is about to end, it's best to run `s.cleanup()` in order to clear the crontab from the scheduler's tasks. I'm yet to implement a way to remove older tasks that could've been left, as a suddent shutdown might happen.

* Even though the idea is to fully support crontab's time syntax, `@reboot` doesn't makes much sense, as it should be deleted once the script is finished.