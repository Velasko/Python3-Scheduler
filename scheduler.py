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

	def __call__(self):
		self.delete_on -= 1
		self.func(*self.args, **self.kwargs)

		return self.delete_on == 0

class Scheduler():
	def __init__(self, user=None, loop=None, auto_start=True):
		if user is None:
			user = os.getenv("USER")

		self.cron = crontab.CronTab(user=user)
		self.file = os.path.dirname(os.path.realpath(__file__)) + "/" + __file__
		self.tasks = {}

		self._server = None
		self.port = None
		self.get_server()

		if loop is None:
			self.loop = asyncio.get_event_loop()

		if auto_start:
			self.loop.create_task(self.run())

	def add_task(self, time, func, *args, task_name=None, delete_on=float('inf'), **kwargs):
		if task_name is None:
			task_name = func.__name__

		job = self.cron.new(
			command=f'python3 {self.file} --crontab --port {self.port} --function {task_name}',
			comment=f'{self.file}:{func.__name__}'
		)

		for n, field in enumerate(time.split(" ")):
			job.slices[n].parse(field)

		self.tasks[func.__name__] = Function(func, job=job, delete_on=delete_on, *args, **kwargs)

		self.cron.write()

	def remove(self, task):
		self.cron.remove(self.tasks[task].job)
		self.cron.write()
		del self.tasks[task]

	def run_task(self, task):
		if self.tasks[task](): #executing data
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
					print(port)
					self._server = server
					return server
				except OSError:
					port += 1

		return self._server

	def cleanup(self):
		for task in list(self.tasks.keys())[:]:
			self.remove(task)
		self._server.close()

	async def handle_client(self, client):
		request = (await self.loop.sock_recv(client, 255)).decode('utf8')
		client.close()

		try:
			self.run_task(request)
		except KeyError:
			pass

	async def _run(self):
		client, _ = await self.loop.sock_accept(self.get_server())
		self.loop.create_task(self.handle_client(client))

def test():
	print('test function executed. You may ^C')

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
		finally:
			s.cleanup()
			print(s.tasks)
			print('finished finally')