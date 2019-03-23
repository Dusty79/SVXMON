# -*- coding: utf-8 -*-
import sys, subprocess

if __name__ == "__main__":
	while True:
		argline = sys.stdin.readline()
		argline = argline.rstrip('\n')
		do_search = True
		args = ['ping', '-c', '10', argline]
		ping_process = subprocess.Popen(args, shell=False, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
		while do_search:
			outline = ping_process.stdout.readline()
			outline = outline.rstrip()
			if ping_process.poll() is not None:
				do_search = False
				print('Ping is done.')
				sys.stdout.flush()
			elif outline != '':
				print('Pinger: ' + outline)
				sys.stdout.flush()
				outline = ''
