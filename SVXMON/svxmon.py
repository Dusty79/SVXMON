# -*- coding: utf-8 -*-
bot_version = '0.40 beta.'
import subprocess, threading, os, sys, time, re
from sys import argv
from os.path import abspath, dirname
import telebot
from telebot import types
try:
	import configparser
except ImportError:
	import ConfigParser as configparser
try:
	from queue import Queue, Empty
except ImportError:
	from Queue import Queue, Empty

"""
Variables
"""
TX_ON_message = 'Turning the transmitter ON'
TX_OFF_message = 'Turning the transmitter OFF'
COS_ON_message = 'The squelch is OPEN'
COS_OFF_message = 'The squelch is CLOSED'
Alarm_keywords = ['ERROR', 'WARNING', 'Error', 'timed out']
Info_keywords = ['Connecting to', 'Connection established to', 'Disconnected from', 'ctivating', 'CONNECT', 'acro', 'digit']
Extinfo_keywords = ['onnect', 'odule', 'ogic', 'link', 'uthentic', 'node']
allow_char = r'[^\*#0-9DSQp]'
allow_shortcut_char = r'[^\_a-z0-9]'

do_search = False
do_implement = False
active_module = ''
active_logic_list = []
active_link_list = []
dialog_is_running = False
tmp_option_name = ''

lock = threading.Lock()
svx_cmd_queue = Queue()
trxqueue = Queue()
outqueue = Queue()
botmodules = dict()

"""
Section of functions of the configuration file
"""
def get_config(path):
	"""
	Returns the config object
	"""
	print('Search config: ' + path)
	if not os.path.isfile(path):
		print('Config is not found. Abort.')
		sys.exit()
	config = configparser.ConfigParser()
	config.read(path)
	return config
 
def get_setting(path, section, setting, type):
	"""
	Return a setting
	"""
	if type == 'str':
		value = config.get(section, setting)
	elif type == 'int':
		value = config.getint(section, setting)
	elif type == 'float':
		value = config.getfloat(section, setting)
	elif type == 'bool':
		value = config.getboolean(section, setting)
	return value
 
def update_setting(path, section, setting, value):
	"""
	Update a setting
	"""
	cfg = get_config(path)
	if not cfg.has_section(section):
		cfg.add_section(section)
	cfg.set(section, setting, value)
	with open(path, "w") as config_file:
		cfg.write(config_file)
 
def delete_setting(path, section, setting):
	"""
	Delete a setting
	"""
	cfg = get_config(path)
	cfg.remove_option(section, setting)
	with open(path, "w") as config_file:
		cfg.write(config_file)

"""
Reading values to variables
"""
svxmonpath = dirname(abspath(argv[0]))
cfg_path = svxmonpath + '/svxmon_settings.cfg'
config = get_config(cfg_path)

TOKEN = get_setting(cfg_path, 'Settings', 'token', 'str')
CHID = get_setting(cfg_path, 'Settings', 'chid', 'int')
svxpath = get_setting(cfg_path, 'Settings', 'svxpath', 'str')

svxautostart = get_setting(cfg_path, 'Options', 'svxautostart', 'bool')
show_alarm_messages = get_setting(cfg_path, 'Options', 'show_alarm_messages', 'bool')
show_info_messages = get_setting(cfg_path, 'Options', 'show_info_messages', 'bool')
show_extinfo_messages = get_setting(cfg_path, 'Options', 'show_extinfo_messages', 'bool')
tx_stucktout = get_setting(cfg_path, 'Options', 'tx_stucktout', 'int')
rx_stucktout = get_setting(cfg_path, 'Options', 'rx_stucktout', 'int')

with_svx_start = get_setting(cfg_path, 'Commands', 'with_svx_start', 'str')
with_tx_stuck = get_setting(cfg_path, 'Commands', 'with_tx_stuck', 'str')
with_tx_unstuck = get_setting(cfg_path, 'Commands', 'with_tx_unstuck', 'str')
with_rx_stuck = get_setting(cfg_path, 'Commands', 'with_rx_stuck', 'str')
with_rx_unstuck = get_setting(cfg_path, 'Commands', 'with_rx_unstuck', 'str')

files = os.listdir(svxmonpath + '/Modules')
scripts = filter(lambda x: x.endswith('.py'), files)

"""
Telebot variables
"""
URL = 'https://api.telegram.org/bot'
bot = telebot.TeleBot(TOKEN, threaded=False)

"""
Section of functions of the bot
"""
def svxlink_start():
	print('SvxLink with monitoring is starting...')

	line = ''
	error_line = ''
	global do_search
	do_search = True
	global do_implement
	global active_module
	global active_logic_list
	global active_link_list

	global svx_process
	svx_process = subprocess.Popen(svxpath, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
	stuck_search = threading.Thread(name='stuck_search', target=trx_watchdog, args=(trxqueue,))
	stuck_search.daemon = True
	stuck_search.start()

	while do_search:
		line = svx_process.stdout.readline()
		if line == '' and svx_process.poll() is not None:
			with lock:
				do_search = False
			stuck_search.join()
			error_line = 'SVXLINK STOPPED'
			print(error_line)
			bot.send_message(CHID, error_line)
			active_module = ''
			active_logic_list = []
			active_link_list = []
			do_implement = True
			continue
		line = line.rstrip()
		if line:
			print(line)
			if error_line == '':
				if 'SvxLink v' in line:
					error_line = 'SVXLINK STARTED'
					svx_mon_alarm(error_line)
					with_start_svx_exec()
					continue
				elif 'Shutting down application' in line:
					error_line = 'SVXLINK STOPPED from console'
					svx_mon_alarm(error_line)
					active_module = ''
					active_logic_list = []
					active_link_list = []
					do_implement = True
					continue
			if 'Activating module' in line:
				active_module = line.rstrip('...').partition('Activating module ')[-1]
			elif 'Deactivating module' in line:
				active_module = ''
			if 'Connection established to' in line:
				changing_logic = line.partition(': Connection established to ')[0]
				if not changing_logic in active_logic_list:
					active_logic_list.append(changing_logic)
			elif 'Disconnected from' in line:
				changing_logic = line.partition(': Disconnected from ')[0]
				if changing_logic in active_logic_list:
					active_logic_list.remove(changing_logic)
			if 'Activating link' in line:
				changing_link = line.partition('Activating link ')[-1]
				if not changing_link in active_link_list:
					active_link_list.append(changing_link)
			elif 'Deactivating link' in line:
				changing_link = line.partition('Deactivating link ')[-1]
				if changing_link in active_link_list:
					active_link_list.remove(changing_link)
			if 'EchoLink QSO state' in line:
				changing_node = line.partition(': EchoLink QSO state changed to ')
				if changing_node[-1] == 'CONNECTED':
					changing_link = changing_node[0]
					if not changing_link in active_link_list:
						active_link_list.append(changing_link)
				elif changing_node[-1] == 'DISCONNECTED':
					changing_link = changing_node[0]
					if changing_link in active_link_list:
						active_link_list.remove(changing_link)
			if show_alarm_messages and error_line == '':
				for keyword in Alarm_keywords:
					if keyword in line:
						error_line = '!!!: ' + line
						svx_mon_alarm(error_line)
						break
			if show_info_messages and error_line == '':
				for keyword in Info_keywords:
					if keyword in line:
						error_line = 'i: ' + line
						svx_mon_alarm(error_line)
						break
			if show_extinfo_messages and error_line == '':
				for keyword in Extinfo_keywords:
					if keyword in line:
						error_line = '?: ' + line
						svx_mon_alarm(error_line)
						break

			if error_line == '':
				trxqueue.put((line))

		line = ''
		error_line = ''

def svx_mon_alarm(error_line):
	print(error_line)
	bot.send_message(CHID, error_line)

def trx_watchdog_response(wdline, way, type):
	print(wdline)
	bot.send_message(CHID, wdline)
	if type == 'alarm':
		if way == 'tx':
			if with_tx_stuck != '':
				bot.send_message(CHID, 'The command with TX stuck is executed:\n' + with_tx_stuck)
				svx_command(with_tx_stuck, False)
		elif way == 'rx':
			if with_rx_stuck != '':
				bot.send_message(CHID, 'The command with RX stuck is executed:\n' + with_rx_stuck)
				svx_command(with_rx_stuck, False)
	elif type == 'dealarm':
		if way == 'tx':
			if with_tx_unstuck != '':
				bot.send_message(CHID, 'The command with TX unstuck is executed:\n' + with_tx_unstuck)
				svx_command(with_tx_unstuck, False)
		elif way == 'rx':
			if with_rx_unstuck != '':
				bot.send_message(CHID, 'The command with RX unstuck is executed:\n' + with_rx_unstuck)
				svx_command(with_rx_unstuck, False)

def trx_watchdog(trxqueue):
	print('trx_watchdog is starting...')
	tx = dict()
	rx = dict()
	line = ''
	wdline = ''

	while do_search:
		try:
			line = trxqueue.get(timeout=1)
		except Empty:
			pass
		else:
			if line:
				if TX_ON_message in line:
					line_begin = line.split(':', 1)[0]
					if line_begin not in tx:
						tx[line_begin]={}
						tx[line_begin]['stuck'] = False
					tx[line_begin]['start_time'] = time.time()
				elif TX_OFF_message in line:
					line_begin = line.split(':', 1)[0]
					if line_begin not in tx:
						tx[line_begin]={}
						tx[line_begin]['stuck'] = False
					tx[line_begin]['start_time'] = 0

				if COS_ON_message in line:
					line_begin = line.split(':', 1)[0]
					if line_begin not in rx:
						rx[line_begin]={}
						rx[line_begin]['stuck'] = False
					rx[line_begin]['start_time'] = time.time()
				elif COS_OFF_message in line:
					line_begin = line.split(':', 1)[0]
					if line_begin not in rx:
						rx[line_begin]={}
						rx[line_begin]['stuck'] = False
					rx[line_begin]['start_time'] = 0
				line = ''
				trxqueue.task_done()

		for key in tx:
			if tx[key]['start_time'] != 0:
				if (time.time()-tx[key]['start_time']) > tx_stucktout and not tx[key]['stuck']:
					tx[key]['stuck'] = True
					wdline = 'ALARM:\n' + key + ' IS STUCK!'
					trx_watchdog_response(wdline, 'tx', 'alarm')
					continue
			elif tx[key]['start_time'] == 0 and tx[key]['stuck']:
				tx[key]['stuck'] = False
				wdline = 'INFO:\n' + key + ' IS UNSTUCK!'
				trx_watchdog_response(wdline, 'tx', 'dealarm')

		for key in rx:
			if rx[key]['start_time'] != 0:
				if (time.time()-rx[key]['start_time']) > rx_stucktout and not rx[key]['stuck']:
					rx[key]['stuck'] = True
					wdline = 'ALARM:\n' + key + ' IS STUCK!'
					trx_watchdog_response(wdline, 'rx', 'alarm')
					continue
			elif rx[key]['start_time'] == 0 and rx[key]['stuck']:
				rx[key]['stuck'] = False
				wdline = 'INFO:\n' + key + ' IS UNSTUCK!'
				trx_watchdog_response(wdline, 'rx', 'dealarm')

def svxlink_mon_start():
	if do_implement:
		try:
			global svxmon
			svxmon = threading.Thread(name='svxmon', target=svxlink_start)
			svxmon.start()
		except Exception as err:
			err = str(err)
			print('ERROR: ' + err)
			bot.send_message(CHID, 'Failure attempt of a start SvxLink.\nERROR:\n' + err)
	else:
		bot.send_message(CHID, 'Failure. SvxLink monitor is busy.\nThe command to start SvxLink is discarded.')

def svx_command(command, confirm):
	global do_implement
	if command != '':
		if check_svx_command(command):
			if do_search:
				if confirm:
					bot.send_message(CHID, 'The command is accepted: ' + command)
				svx_cmd_queue.put(command)
			elif command == 'S':
				bot.send_message(CHID, 'The command to start SvxLink is received.')
				svxlink_mon_start()
			else:
				bot.send_message(CHID, 'Failure. SvxLink is not launched.\nThe message: "' + command + '" - is discarded.')
		else:
			print('Invalid command: ' + command)
			bot.send_message(CHID, 'Invalid command: ' + command)

def svx_command_implement(svx_cmd_queue):
	global svx_process
	global do_implement
	while True:
		try: command = svx_cmd_queue.get(timeout=1)
		except Empty:
			pass
		else:
			if do_implement:
				for character in command:
					if character != 'S':
						if character == 'p':
							time.sleep(1)
						elif character == 'Q':
							do_implement = False
						svx_process.stdin.write(character)
			else:
				bot.send_message(CHID, 'Failure. SvxLink monitor is busy.\nThe message: "' + command + '" - is discarded.')

def check_svx_command(command):
	if re.search(allow_char, command):
		return False
	else:
		return True

def check_shortcut_name(command):
	if re.search(allow_shortcut_char, command):
		return False
	else:
		return True

def with_start_svx_exec():
	if with_svx_start != '':
		bot.send_message(CHID, 'The command with start of SvxLink is executed:\n' + with_svx_start)
		svx_command(with_svx_start, True)

def check_sender(msg):
	if msg.date < botstarttime:
		return False
	if msg.chat.id == CHID:
		return True
	else:
		bot.send_message(CHID, ('Unauthorized attempt to command from:\nID: '\
		 + str(msg.chat.id) + ', ' + format(msg.chat.first_name) + ' '\
		 + format(msg.chat.last_name)))
		bot.send_message(msg.chat.id, 'Refused. You are not the administrator of this link.')
		return False

def shortcut(commandname):
	commandname = commandname.strip("/")
	global config
	section = 'Shortcuts'
	if not config.has_section(section):
		return False
	elif not config.has_option(section, commandname):
		return False
	else:
		command = config.get(section, commandname)
		main_menu('Return to main menu.')
		bot.send_message(CHID, 'Attempt to launch a shortcut: ' + commandname)
		svx_command(command, True)
		return True

def main_menu(note):
	global dialog_is_running
	dialog_is_running = False
	global tmp_option_name
	tmp_option_name = ''
	if not note:
		note = 'Return to main menu.'
	markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
	itembtn_svx_start = types.KeyboardButton('start SvxLink')
	itembtn_svx_stop = types.KeyboardButton('stop SvxLink')
	itembtn_svx_status = types.KeyboardButton('SvxLink status')
	itembtn_settings_status = types.KeyboardButton('viewing of current settings')
	itembtn_shortcut_status = types.KeyboardButton('viewing of current shortcuts')
	itembtn_bot_modules = types.KeyboardButton('bot modules')
	itembtn_help = types.KeyboardButton('help')
	markup.row(itembtn_svx_start, itembtn_svx_stop, itembtn_svx_status)
	markup.row(itembtn_settings_status, itembtn_shortcut_status)
	markup.row(itembtn_bot_modules, itembtn_help)
	bot.send_message(CHID, note, reply_markup=markup)
	print(note)

def operation_result(note):
	global dialog_is_running
	if not note:
		note = 'Cancel of operation.'
	dialog_is_running = False
	note = '\n'.join([note, 'Return to main menu.'])
	main_menu(note)

"""
Section of functions of the additional bot modules
"""
def enqueue_output(out, outqueue):
	for line in iter(out.readline, ''):
		line = re.sub("\s*\n\s*", ' ', line.strip())# удаляем пробелы в начале и в конце строки и символы переноса строки
		outqueue.put(line)
	out.close()

def botmodule_output(outqueue):
	while True:
		try: line = outqueue.get(timeout=1)
		except Empty:
			pass
		else:
			bot.send_message(CHID, line)

"""
Section of the bot hendlers
"""
@bot.message_handler(commands=['start'])
def start(message):
	global dialog_is_running
	if check_sender(message) and not dialog_is_running:
		main_menu('OK, I am ready. :-)\nSend command /help for info.')

@bot.message_handler(commands=['help'])
def help(message):
	global dialog_is_running
	if check_sender(message) and not dialog_is_running:
		main_menu('This bot will help you to control your SvxLink node.\n\nYou can control a bot sending these commands:\n/svx_start - to start SvxLink\n/svx_stop - to stop SvxLink\n/svx_status - to request SvxLink status\n/settings_status - for viewing of current settings\n/edit_options - for editing options of a configuration\n/edit_commands - for editing commands\n/shortcut_status - for viewing of current shortcuts\n/add_shortcut - for add new shortcut\n/edit_shortcut - for editing current shortcuts\n/del_shortcut - for deleting current shortcuts\n/cancel - for canceling of the current operation\n/bot_modules - for work with bot additional modules\n/help - this help\n\nSvxLink supports the commands consisting of characters of "*", "#", "D", "S", "Q", "p" and digits 0-9.')

@bot.message_handler(commands=['svx_start'])
def svx_start(message):
	global dialog_is_running
	if check_sender(message) and not dialog_is_running:
		main_menu('The command to start SvxLink is received.')
		if not do_search:
			svxlink_mon_start()
		else:
			bot.send_message(CHID, 'Failure. SvxLink is already launched.')

@bot.message_handler(commands=['svx_stop'])
def svx_stop(message):
	global dialog_is_running
	if check_sender(message) and not dialog_is_running:
		main_menu('The command to stop SvxLink is received.')
		if do_search:
			try:
				svx_command('Q', False)
				global svxmon
				svxmon.join()
			except Exception as err:
				err = str(err)
				print('ERROR: ' + err)
				bot.send_message(CHID, 'Failure attempt of a stop SvxLink.\nERROR:\n' + err)
		else:
			bot.send_message(CHID, 'Failure. SvxLink is not launched.')

@bot.message_handler(commands=['svx_status'])
def svx_status(message):
	global dialog_is_running
	if check_sender(message) and not dialog_is_running:
		main_menu('The command to check state of SvxLink is received.')
		if do_search:
			global active_module
			activemodulestr = 'There are no activated modules.'
			if active_module != '':
				activemodulestr = 'The last activated module: ' + active_module
			global active_logic_list
			activelogicstr = 'There are no connections for links.'
			if active_logic_list:
				activelogicstr = 'Ready connections for links: ' + str(active_logic_list).strip('[]')
			global active_link_list
			activelinkstr = 'There are no activated links.'
			if active_link_list:
				activelinkstr = 'The last activated links: ' + str(active_link_list).strip('[]')
			status_string =  '\n'.join(['SvxLink is launched.', activelogicstr, activemodulestr, activelinkstr])
			bot.send_message(CHID, status_string)
		else:
			bot.send_message(CHID, 'SvxLink is not launched.')

@bot.message_handler(commands=['edit_options'])
def edit_options(message):
	global dialog_is_running
	if check_sender(message) and not dialog_is_running:
		section = 'Options'
		options = config.options(section)
		options_string = ''
		markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
		for option in options:
			markup.add(types.KeyboardButton(option))
			option_line = ' = '.join([option, config.get(section, option)])
			options_string = ''.join([options_string, option_line, '\n'])
		itembtn_cancel = types.KeyboardButton('cancel of operation')
		markup.add(itembtn_cancel)
		sent = bot.send_message(CHID, 'What option do you want to change?\nCurrent values:\n\n' + options_string + '\n\nSend an option name.\n\nSend other for operation canceling.', reply_markup=markup)
		bot.register_next_step_handler(sent, edit_option_name)
		dialog_is_running = True

def edit_option_name(message):
	global dialog_is_running
	if check_sender(message) and dialog_is_running:
		if not ('cancel') in message.text:
			print('Attempt to change an option: ' + message.text)
			markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
			section = 'Options'
			if config.has_option(section, message.text):
				option_type = str(type(globals()[message.text]))
				option_type = option_type.strip('<>').split(' ', 1)[1]
				option_type = option_type.strip("'")
				if option_type == 'bool':
					itembtn_true = types.KeyboardButton('True')
					markup.add(itembtn_true)
					itembtn_false = types.KeyboardButton('False')
					markup.add(itembtn_false)
			itembtn_cancel = types.KeyboardButton('cancel of operation')
			markup.add(itembtn_cancel)
			global tmp_option_name
			tmp_option_name = message.text
			sent = bot.send_message(CHID, 'Attempt to change an option: ' + message.text + '\nSend its new value.', reply_markup=markup)
			bot.register_next_step_handler(sent, edit_option_val)
		else:
			operation_result('Cancel option edit.')

def edit_option_val(message):
	global dialog_is_running
	if check_sender(message) and dialog_is_running:
		if not ('cancel') in message.text:
			global tmp_option_name
			message.text = ' = '.join([tmp_option_name, message.text])
			print('Attempt to change an option: ' + message.text)
			try:
				section = 'Options'
				msg = message.text.split(' = ')
				if len(msg) == 2:
					option = msg[0]
					value = msg[1]
					global config
					if config.has_option(section, option):
						option_type = str(type(globals()[option]))
						option_type = option_type.strip('<>').split(' ', 1)[1]
						option_type = option_type.strip("'")
						previous_value = get_setting(cfg_path, section, option, option_type)
						update_setting(cfg_path, section, option, value)
						with lock:
							try:
								config = get_config(cfg_path)
								globals()[option] = get_setting(cfg_path, section, option, option_type)
								operation_result('Option are successfully updated:\n' + option + ' = ' + str(value))
							except Exception as err:
								print('Error:\n' + str(err))
								update_setting(cfg_path, section, option, previous_value)
								config = get_config(cfg_path)
								globals()[option] = get_setting(cfg_path, section, option, option_type)
								operation_result('Error:\n' + str(err) + '\nThe previous value is returned:\n' + option + ' = ' + str(previous_value))
					else:
						print('Cancel option edit.')
						operation_result('Incorrect option name. Cancel option edit.')
				else:
					print('Cancel option edit.')
					operation_result('Cancel option edit.')
			except Exception as err:
				print('Cancel option edit: \n' + err)
				operation_result('Cancel option edit.')
		else:
			operation_result('Cancel option edit.')

@bot.message_handler(commands=['edit_commands'])
def edit_commands(message):
	global dialog_is_running
	if check_sender(message) and not dialog_is_running:
		section = 'Commands'
		options = config.options(section)
		options_string = ''
		markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
		for option in options:
			markup.add(types.KeyboardButton(option))
			option_line = ' = '.join([option, config.get(section, option)])
			options_string = ''.join([options_string, option_line, '\n'])
		itembtn_cancel = types.KeyboardButton('cancel of operation')
		markup.add(itembtn_cancel)
		sent = bot.send_message(CHID, 'What command do you want to change?\nCurrent values:\n\n' + options_string + '\n\nSend an command name.\n\nSend other for operation canceling.', reply_markup=markup)
		bot.register_next_step_handler(sent, edit_command_name)
		dialog_is_running = True

def edit_command_name(message):
	global dialog_is_running
	if check_sender(message) and dialog_is_running:
		if not ('cancel') in message.text:
			print('Attempt to change an command: ' + message.text)
			markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
			itembtn_del_val = types.KeyboardButton('delete of current value')
			itembtn_cancel = types.KeyboardButton('cancel of operation')
			markup.add(itembtn_del_val, itembtn_cancel)
			global tmp_option_name
			tmp_option_name = message.text
			sent = bot.send_message(CHID, 'Attempt to change an command: ' + message.text + '\nSend its new value.', reply_markup=markup)
			bot.register_next_step_handler(sent, edit_command_val)
		else:
			operation_result('Cancel option edit.')

def edit_command_val(message):
	global dialog_is_running
	if check_sender(message) and dialog_is_running:
		if not ('cancel') in message.text:
			global tmp_option_name
			if 'delete of current value' in message.text:
				message.text = ''
			message.text = ' = '.join([tmp_option_name, message.text])
			print('Attempt to change an command: ' + message.text)
			try:
				section = 'Commands'
				msg = message.text.split(' = ')
				option = msg[0]
				option = option.strip('= ')
				if len(msg) < 2:
					value = ''
				else:
					value = msg[1]
				if check_svx_command(value) or value == '':
					global config
					if config.has_option(section, option):
						option_type = 'str'
						previous_value = get_setting(cfg_path, section, option, option_type)
						update_setting(cfg_path, section, option, value)
						with lock:
							try:
								config = get_config(cfg_path)
								globals()[option] = get_setting(cfg_path, section, option, option_type)
								operation_result('Command are successfully updated:\n' + option + ' = ' + str(value))
							except Exception as err:
								print('Error:\n' + str(err))
								update_setting(cfg_path, section, option, previous_value)
								config = get_config(cfg_path)
								globals()[option] = get_setting(cfg_path, section, option, option_type)
								operation_result('Error:\n' + str(err) + '\nThe previous value is returned:\n' + option + ' = ' + str(previous_value))
					else:
						print('Cancel command edit.')
						operation_result('Incorrect command name. Cancel command edit.')
				else:
					print('Cancel command edit.')
					operation_result('Incorrect command. Cancel command edit.')
			except Exception as err:
				print('Cancel command edit: \n' + err)
				operation_result('Cancel option edit.')
		else:
			operation_result('Cancel option edit.')

@bot.message_handler(commands=['settings_status'])
def settings_status(message):
	global dialog_is_running
	if check_sender(message) and not dialog_is_running:
		global config
		options_string = ''
		section = 'Options'
		options = config.options(section)
		options_string = ''.join([options_string, '\n[',section, ']\n'])
		for option in options:
			option_line = ' = '.join([option, config.get(section, option)])
			options_string = ''.join([options_string, option_line, '\n'])
		section = 'Commands'
		options = config.options(section)
		options_string = ''.join([options_string, '\n[',section, ']\n'])
		for option in options:
			option_line = ' = '.join([option, config.get(section, option)])
			options_string = ''.join([options_string, option_line, '\n'])
		markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
		itembtn_edit_options = types.KeyboardButton('editing options')
		itembtn_edit_commands = types.KeyboardButton('editing commands')
		itembtn_return = types.KeyboardButton('return to main menu')
		markup.row(itembtn_edit_options)
		markup.row(itembtn_edit_commands)
		markup.row(itembtn_return)
		sent = bot.send_message(CHID, 'Current values of settings:\n' + options_string + '\nFor change of settings send commands /edit_options or /edit_commands.', reply_markup=markup)

@bot.message_handler(commands=['shortcut_status'])
def shortcut_status(message):
	global dialog_is_running
	if check_sender(message) and not dialog_is_running:
		section = 'Shortcuts'
		options = config.options(section)
		options_string = ''
		markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
		for option in options:
			option_line = ' = '.join([option, config.get(section, option)])
			option_line = '/' + option_line
			markup.add(types.KeyboardButton('/' + option))
			options_string = ''.join([options_string, option_line, '\n'])
		itembtn_add_shortcut = types.KeyboardButton('add new shortcut')
		itembtn_edit_shortcut = types.KeyboardButton('edit of shortcuts')
		itembtn_del_shortcut = types.KeyboardButton('delete of shortcuts')
		itembtn_return = types.KeyboardButton('return to main menu')
		markup.add(itembtn_add_shortcut, itembtn_edit_shortcut, itembtn_del_shortcut, itembtn_return)
		bot.send_message(CHID, 'Current values of shortcuts:\n\n' + options_string + '\nFor change of shortcuts send commands /add_shortcut, /edit_shortcut or /del_shortcut.', reply_markup=markup)

@bot.message_handler(commands=['add_shortcut'])
def add_shortcut(message):
	global dialog_is_running
	if check_sender(message) and not dialog_is_running:
		section = 'Shortcuts'
		options = config.options(section)
		options_string = ''
		for option in options:
			option_line = ' = '.join([option, config.get(section, option)])
			options_string = ''.join([options_string, option_line, '\n'])
		markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
		itembtn_cancel = types.KeyboardButton('cancel of operation')
		markup.row(itembtn_cancel)
		sent = bot.send_message(CHID, 'What shortcut do you want to add?\nCurrent values:\n\n' + options_string + '\nSend an shortcut name and its new value.\nPlease, use this format:\n\nshortcut_name = value\n\nSend other for operation canceling.', reply_markup=markup)
		bot.register_next_step_handler(sent, add_shortcut_val)
		dialog_is_running = True

def add_shortcut_val(message):
	global dialog_is_running
	if check_sender(message) and dialog_is_running:
		if not ('cancel') in message.text:
			print('Attempt to add an shortcut: ' + message.text)
			section = 'Shortcuts'
			msg = message.text.split(' = ')
			option = msg[0]
			option = option.strip('= ')
			if len(msg) < 2:
				value = ''
			else:
				value = msg[1]
			if (check_svx_command(value) or value == '') and check_shortcut_name(option):
				global config
				section = 'Shortcuts'
				option_type = 'str'
				update_setting(cfg_path, section, option, value)
				with lock:
					try:
						config = get_config(cfg_path)
						globals()[option] = get_setting(cfg_path, section, option, option_type)
						operation_result('Shortcut are successfully added:\n' + option + ' = ' + str(value))
					except Exception as err:
						print('Error:\n' + str(err))
						operation_result('Error:\n' + str(err))
			else:
				print('Cancel shortcut edit.')
				operation_result('Incorrect shortcut. Cancel shortcut edit.')
		else:
			operation_result('Cancel shortcut edit.')

@bot.message_handler(commands=['edit_shortcut'])
def edit_shortcut(message):
	global dialog_is_running
	if check_sender(message) and not dialog_is_running:
		section = 'Shortcuts'
		options = config.options(section)
		options_string = ''
		markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
		for option in options:
			markup.add(types.KeyboardButton(option))
			option_line = ' = '.join([option, config.get(section, option)])
			options_string = ''.join([options_string, option_line, '\n'])
		itembtn_cancel = types.KeyboardButton('cancel of operation')
		markup.add(itembtn_cancel)
		sent = bot.send_message(CHID, 'What shortcut do you want to change?\nCurrent values:\n\n' + options_string + '\nSend an shortcut name.\n\nSend other for operation canceling.', reply_markup=markup)
		bot.register_next_step_handler(sent, edit_shortcut_name)
		dialog_is_running = True

def edit_shortcut_name(message):
	global dialog_is_running
	if check_sender(message) and dialog_is_running:
		if not ('cancel') in message.text:
			print('Attempt to change an shortcut: ' + message.text)
			markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
			itembtn_cancel = types.KeyboardButton('cancel of operation')
			markup.add(itembtn_cancel)
			global tmp_option_name
			tmp_option_name = message.text
			sent = bot.send_message(CHID, 'Attempt to change an shortcut: ' + message.text + '\nSend its new value.', reply_markup=markup)
			bot.register_next_step_handler(sent, edit_shortcut_val)
		else:
			operation_result('Cancel option edit.')

def edit_shortcut_val(message):
	global dialog_is_running
	if check_sender(message) and dialog_is_running:
		if not ('cancel') in message.text:
			global tmp_option_name
			message.text = ' = '.join([tmp_option_name, message.text])
			print('Attempt to change an shortcut: ' + message.text)
			try:
				section = 'Shortcuts'
				msg = message.text.split(' = ')
				option = msg[0]
				option = option.strip('= ')
				if len(msg) < 2:
					value = ''
				else:
					value = msg[1]
				if check_svx_command(value) or value == '':
					global config
					if config.has_option(section, option):
						option_type = 'str'
						previous_value = get_setting(cfg_path, section, option, option_type)
						update_setting(cfg_path, section, option, value)
						with lock:
							try:
								config = get_config(cfg_path)
								globals()[option] = get_setting(cfg_path, section, option, option_type)
								operation_result('Shortcut are successfully updated:\n' + option + ' = ' + str(value))
							except Exception as err:
								print('Error:\n' + str(err))
								update_setting(cfg_path, section, option, previous_value)
								config = get_config(cfg_path)
								globals()[option] = get_setting(cfg_path, section, option, option_type)
								operation_result('Error:\n' + str(err) + '\nThe previous value is returned:\n' + option + ' = ' + str(previous_value))
					else:
						print('Cancel shortcut edit.')
						operation_result('Incorrect shortcut name. Cancel shortcut edit.')
				else:
					print('Cancel shortcut edit.')
					operation_result('Incorrect shortcut name. Cancel shortcut edit.')
			except Exception as err:
				print('Cancel shortcut edit: \n' + err)
				operation_result('Cancel shortcut edit.')
		else:
			operation_result('Cancel shortcut edit.')

@bot.message_handler(commands=['del_shortcut'])
def del_shortcut(message):
	global dialog_is_running
	if check_sender(message) and not dialog_is_running:
		section = 'Shortcuts'
		options = config.options(section)
		options_string = ''
		markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
		for option in options:
			option_line = ' = '.join([option, config.get(section, option)])
			markup.add(types.KeyboardButton(option))
			options_string = ''.join([options_string, option_line, '\n'])
		itembtn_cancel = types.KeyboardButton('cancel of operation')
		markup.add(itembtn_cancel)
		sent = bot.send_message(CHID, 'What shortcut do you want to delete?\nCurrent values:\n\n' + options_string + '\nSend an shortcut name to delete.\n\nSend other for operation canceling.', reply_markup=markup)
		bot.register_next_step_handler(sent, del_shortcut_val)
		dialog_is_running = True

def del_shortcut_val(message):
	global dialog_is_running
	if check_sender(message) and dialog_is_running:
		if not ('cancel') in message.text:
			print('Attempt to delete shortcut: ' + message.text)
			section = 'Shortcuts'
			option = message.text
			global config
			if config.has_option(section, option):
				with lock:
					try:
						delete_setting(cfg_path, section, option)
						config = get_config(cfg_path)
						operation_result('Shortcut are successfully delete:\n' + option)
					except Exception as err:
						print('Error:\n' + str(err))
						operation_result('Error:\n' + str(err))
			else:
				print('The shortcut does not exist:\n' + option)
				operation_result('The shortcut does not exist:\n' + option)
		else:
			operation_result('Cancel delete shortcut.')

@bot.message_handler(commands=['bot_modules'])
def bot_modules(message):
	global dialog_is_running
	if check_sender(message) and not dialog_is_running:
		modules_string = ''
		markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
		if botmodules.items():
			for modulename in botmodules:
				module_line = 'module ' + modulename
				markup.add(types.KeyboardButton(module_line))
				modules_string = ''.join([modules_string, modulename, '\n'])
		itembtn_return = types.KeyboardButton('return to main menu')
		markup.row(itembtn_return)
		sent = bot.send_message(CHID, 'Current active additional bot modules:\n\n' + modules_string + '\nFor work with the additional module send keyword "module" and his name.', reply_markup=markup)
		bot.register_next_step_handler(sent, bot_modules_name)
		dialog_is_running = True

def bot_modules_name(message):
	global dialog_is_running
	if check_sender(message) and dialog_is_running:
		if not ('return to main menu') in message.text:
			markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
			itembtn_cancel = types.KeyboardButton('cancel of operation')
			markup.add(itembtn_cancel)
			global tmp_option_name
			tmp_option_name = message.text.split()[1]
			sent = bot.send_message(CHID, 'Attempt to work with bot module ' + tmp_option_name + '.\nSend instruction for module.', reply_markup=markup)
			bot.register_next_step_handler(sent, bot_modules_cmd)
		else:
			operation_result('Cancel.')

def bot_modules_cmd(message):
	global dialog_is_running
	if check_sender(message) and dialog_is_running:
		if not ('cancel') in message.text:
			global botmodules
			global tmp_option_name
			arg = re.sub("\s*\n\s*", ' ', message.text.strip())
			try:
				botmodules[tmp_option_name]['subprocess'].stdin.write(arg+'\n')
				botmodules[tmp_option_name]['subprocess'].stdin.flush()
				operation_result('The instruction is sent.')
			except Exception as err:
				print('Module error:\n' + str(err))
				operation_result('Module error:\n' + str(err))
		else:
			operation_result('Cancel of operation.')

@bot.message_handler(commands=['cancel'])
def cancel(message):
	print('cancel')
	if check_sender(message):
		main_menu('Return to main menu.')

@bot.message_handler(content_types=["text"])
def get_messages(message):
	global dialog_is_running
	print('echo: ' + message.text)
	if check_sender(message) and not dialog_is_running:
		if message.text.startswith('/'):
			if not shortcut(message.text):
				print ('Unknown command: ' + message.text)
				bot.send_message(CHID, 'Unknown command: ' + message.text)
		elif 'start SvxLink' in message.text:
			svx_start(message)
		elif 'stop SvxLink' in message.text:
			svx_stop(message)
		elif 'SvxLink status' in message.text:
			svx_status(message)
		elif 'viewing of current settings' in message.text:
			settings_status(message)
		elif 'editing options' in message.text:
			edit_options(message)
		elif 'editing commands' in message.text:
			edit_commands(message)
		elif 'viewing of current shortcuts' in message.text:
			shortcut_status(message)
		elif 'add new shortcut' in message.text:
			add_shortcut(message)
		elif 'edit of shortcuts' in message.text:
			edit_shortcut(message)
		elif 'delete of shortcuts' in message.text:
			del_shortcut(message)
		elif 'bot modules' in message.text:
			bot_modules(message)
		elif 'return to main menu' in message.text:
			cancel(message)
		elif 'cancel of operation' in message.text:
			cancel(message)
		elif 'help' in message.text:
			help(message)
		else:
			svx_command(message.text, True)


"""
Program main body section
"""

botstarttime = time.time()

main_menu('SvxLink monitoring BOT started.\nVersion ' + bot_version)

command_implement = threading.Thread(name='command_implement',target=svx_command_implement, args=(svx_cmd_queue,))
command_implement.daemon = True
command_implement.start()
do_implement = True

if svxautostart:
	if not do_search:
		bot.send_message(CHID, 'Attempt to autostart SvxLink.')
		svxlink_mon_start()

for script in scripts:
	try:
		scriptpath = svxmonpath + '/Modules/'
		cmd = ['python', str(scriptpath + script)]
		modulename = script[:-3]
		print('Module attaching: ' + scriptpath + script)
		botmodules[modulename]={}
		botmodules[modulename]['subprocess'] = subprocess.Popen(cmd, shell=False, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=1)
		botmodules[modulename]['thread'] = threading.Thread(target=enqueue_output, args=(botmodules[modulename]['subprocess'].stdout, outqueue))
		botmodules[modulename]['thread'].daemon = True
		botmodules[modulename]['thread'].setName(modulename)
		botmodules[modulename]['thread'].start()
		print('Starting thread: ' + botmodules[modulename]['thread'].getName())

	except Exception as err:
		err = str(err)
		print('ERROR: ' + err)

botmodule_out = threading.Thread(name='botmodule_out', target=botmodule_output, args=(outqueue,))
botmodule_out.daemon = True
botmodule_out.start()

#bot.polling()

poling_err = ''
while True:
	try:
		if poling_err != '':
			bot.send_message(CHID, 'Error of telebot polling was found:\n' + poling_err)
			poling_err = ''
		bot.polling(none_stop=True)
	except (KeyboardInterrupt, SystemExit) as err:
		err = str(err)
		print(err)
		bot.send_message(CHID, time.strftime("%Y/%m/%d %H:%M:%S") + '\n' + err)
		break
	except Exception as err:
		err = str(err)
		print('Error of telebot polling:\n' + err)
		poling_err = time.strftime("%Y/%m/%d %H:%M:%S") + '\n' + err
		time.sleep(15)