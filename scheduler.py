import asyncio
import argparse
import crontab
import os
import socket

class Function():
	def __init__(self, func, *args, delete_on=float('inf'), job=None,  **kwargs):
		self.func = func
		self. args = args
		self.delete_on = delete_on
		self.kwargs = kwargs
		self.job = job #never used by this object, but relevant to keep track

	async def __call__(self):
		self.delete_on -= 1
		await self.func(*self.args, **self.kwargs)

		return self.delete_on == 0

special_times = {
	'@hourly' : '0 * * * *',
	'@daily' : '0 0 * * *',
	'@weekly' : '0 0 * * 0',
	'@monthly' : '0 0 1 * *',
	'@yearly' : '0 0 1 1 *',
	'@annually' : '0 0 1 1 *',
	'@midnight' : '0 0 * * *',

}

class Scheduler():
	def __init__(self, user=None, loop=None, auto_start=True):
		"""
		Initializes the scheduler.
		This includes a asyncio socket server running on localhost.

		arguments:
			- user : str; default: linux's user running the script;
				This argument determines which user's crontab it will be executed onto
			- loop : default : asyncio's loop; In case a different loop is desired to be used instead.
			- auto_start : default : True; Automatically starts the loop on which it will be run.
		"""
		if user is None:
			user = os.getenv("USER")

		self.cron = crontab.CronTab(user=user)
		self.file = __file__ if "/" in __file__ else os.path.dirname(os.path.realpath(__file__)) + "/" + __file__
		self.tasks = {}

		self._server = None
		self.port = None
		self.get_server()

		#removing crontabs that might have stayed (happens with a suddent shutdown,)
		self.cron.remove_all(comment=f'{self.file}')
		self.cron.write()

		if loop is None:
			self.loop = asyncio.get_event_loop()

		if auto_start:
			self.loop.create_task(self.run())

	def add_task(self, time, func, *args, task_name=None, delete_on=float('inf'), **kwargs):
		"""
		This method adds the function to the execution list.
		
		arguments:
			- time : str; Crontab's syntax is used and parsed to. If invalid, a KeyError is raised.
			- func : function; The function to be executed once the crontab calls.
			- task_name : str; default : function name;
				Alternative name for the task. If there is a task with such name already,
				a KeyError is raised
			- delete_on : int; default : infinite; How many times the task is supposed to be executed.
			- *args : are parsed to the function as arguments.
			- **kwargs : are parsed to the function as karguments.
		"""
		if task_name is None:
			task_name = func.__name__

		if task_name in self.tasks:
			raise KeyError("Task already scheduled")

		job = self.cron.new(
			command=f'python3 {self.file} --crontab --port {self.port} --function {task_name}',
			comment=f'{self.file}' #used to delete at restart
		)

		if time in special_times:
			time = special_times[time]

		for n, field in enumerate(time.split(" ")):
			job.slices[n].parse(field)

		self.tasks[func.__name__] = Function(func, job=job, delete_on=delete_on, *args, **kwargs)

		self.cron.write()

	def remove(self, task):
		self.cron.remove(self.tasks[task].job)
		self.cron.write()
		del self.tasks[task]

	async def run_task(self, task):
		if await self.tasks[task](): #executing data
			self.remove(task)

	def get_server(self):
		if self._server is None:			
			server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			port = 5000

			while True:
				try:
					server.bind(('localhost', port))
					server.listen(8)
					server.setblocking(False)
					self.port = port
					self._server = server
					return server
				except OSError:
					port += 1

		return self._server

	def cleanup(self):
		"""
		Removes the tasks from crontab and object as well as closing the socket server
		"""
		for task in list(self.tasks.keys())[:]:
			self.remove(task)
		self._server.close()

	async def handle_client(self, client):
		request = (await self.loop.sock_recv(client, 255)).decode('utf8')
		client.close()

		try:
			await self.run_task(request)
		except TypeError as e:
			#this means the function finished execution and only then
			#noticed it's not async
			if "can't be used in 'await' expression" in e.args[0]:
				pass	
			else:
				raise e
		except KeyError as e:
			print(e)

	async def run(self):
		client, _ = await self.loop.sock_accept(self.get_server())
		self.loop.create_task(self.handle_client(client))

async def test():
	print('test function triggered by crontab. You may ^C')

if __name__ == '__main__':
	parser = argparse.ArgumentParser()
	parser.add_argument("--crontab", action='store_true')
	parser.add_argument("--port", type=int)
	parser.add_argument("--function", type=str)

	parser.add_argument("--test", action='store_true', help="Testing the script")

	args = parser.parse_args()

	if args.crontab:
		#Contrab uses this arg to tell a process must be executed
		s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		s.connect(('localhost', args.port))
		s.send(args.function.encode('utf8'))
		s.close()
	
	if args.test:
		s = Scheduler()
		s.add_task(time="* * * * *", func=test, delete_on=1)

		loop = asyncio.get_event_loop()
		try:
			loop.run_forever()
		except KeyboardInterrupt:
			pass
		finally:
			s.cleanup()
			print('\nfinished finally; tasks cleaned up.')
