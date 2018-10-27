SvxLink Monitoring Telegram Bot

The developed complex is intended for simplification of the observation over operation a link node constructed on the basis of SvxLink and for operational annunciator of the administrator of a link in case of origin of emergency situations in its work. Its operation is based on the analysis of text lines of an output of SvxLink.
After start the bot copes commands from the client of Telegram messager.

For control of a bot send the following commands:
/svx_start - for start of SvxLink
/svx_stop - for SvxLink stop
/svx_status - for SvxLink status request
/edit_options - for change parameters of a bot
/edit_commands - for change of commands
/settings_status - for viewing of current settings
/add_shortcut - for adding of the shortcut
/edit_shortcut - for change of the shortcut
/del_shortcut - for deleting the shortcut
/shortcut_status - for viewing of the created shortcuts
/cancel - for canceling of the current operation (interrupts waiting with a bot of the response of the user)
/help - short help

SvxLink supports the commands containing characters "*", "#", "D", "S", "Q", "p" and digit from 0 to 9.Символы "*", "#", "D", 0-9 являются аналогами DTMF-сигналов, используемых для управления линком через радиоэфир, и передаются непосредственно на вход SvxLink.
The character of "Q" serves as a command on completion of SvxLink and can be used in the commands transferred by SvxLink bot on events and described in the configuration file.
The character of "p" serves for specifying of need to make a pause by transmission of the SvxLink command. One sign "p" pauses transmission of characters of a command to 1 second. Application is not restricted.
Example.
The command 981#pppD3# according to the SvxLink settings will commutate a link section and after a pause in 3 seconds will launch a macro instruction 3.
The character of "S" serves as a command for start of SvxLink and can be used in the commands transferred by SvxLink bot on events and described in the configuration file. One shall be transferred in a line and only in case of not launched SvxLink. In all other cases it is ignored.

Tracing of "stuck" on reception and transmission is carried out on all channels found during operation of a script the logician of transceivers. In case of detection of "stuck" the disturbing message to the user is given and the command which is set up in a configuration is executed.

The configuration file svxmon_settings.cfg shall be in one directory with a script. Otherwise the script will not be launched.

Description of options of the configuration file.

[Settings] - Section of settings.
token = in this field is located the token of the created bot received at a bot @BotFather.
chid = in this field is located the user id got at a bot @MyTelegramID_bot.
svxpath = path for start of SvxLink (in the description of a path it is required to specify a double slash).

[Options] - Section of changeable options.
svxautostart = whether to start SvxLink right after start of a bot (True | False).
show_alarm_messages = to send disturbing error messages in operation of a link (True | False).
show_info_messages = to send information messages about the main events (True | False).
show_extinfo_messages = to send messages with the redundant information about events (True | False).
tx_stucktout = timeout after which the transceiver of a link is considered "stuck" on transmission (sec). For example, 300 (5 minutes).
rx_stucktout = timeout after which the transceiver of a link is considered "stuck" on receive (sec.)

[Commands] - Section of commands.
with_svx_start = the command transferred to SvxLink in case of its start. For example, 981#pppppD2#. If command execution is not required, leave a field empty.
with_tx_stuck = the command transferred to SvxLink in case of "stuck" to transmission. For example, Q. If command execution is not required, leave a field empty.
with_tx_unstuck = the command transferred to SvxLink in case of "unstuck" to transmission. If command execution is not required, leave a field empty.
with_rx_stuck = the command transferred to SvxLink in case of "stuck" to receive. If command execution is not required, leave a field empty.
with_rx_unstuck = the command transferred to SvxLink in case of "unstuck" to reception. If command execution is not required, leave a field empty.

[Shortcuts] - Section of shortcuts.
The commands which are often given to a link can be issued in the form of shortcuts for quick access to them.
The name of the shortcut may contain the letters a-z, digit 0-9 and the sign of underlining. A format of the shortcut - "shortcut_name = command".
For example:
to_russia = 2#ppp196189#

The parameters described in sections [Options], [Commands] and [Shortcuts] are available to change from the client of Telegram by means of the appropriate commands. Changes become effective immediately.
