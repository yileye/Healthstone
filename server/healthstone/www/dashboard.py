#!/usr/bin/env python3
# Healthstone System Monitor - (C) 2015-2017 Patrick Lambert - http://healthstone.ca

#
# BEGIN CONFIGURATION
#

# Access code to access the dashboard [string]
AccessCode = "1234"

# Delete log entries after a week [True|False]
DeleteOldEntries = False

# Dark, large text theme for dashboard displays [True|False]
DarkTheme = False

# Send notifications for systems that lose contacts [True|False]
NotifyOnLostContact = True

# Send notifications for systems that raise alarms [True|False]
NotifyOnAlarms = True

# Send a Pushbullet notification using this API key [API key|False]
NotifyPushbullet = False

# Create a NodePoint ticket using this URL, API key, product and release numbers [url|False]
NotifyNodePointURL = False
NotifyNodePointKey = "XXXXXXX"
NotifyNodePointProduct = "1"
NotifyNodePointRelease = "1.0"

# Send an email notification using this SMTP server, To address, and From address [smtp server|False]
NotifySMTPServer = False
NotifySMTPFrom = "me@example.com"
NotifySMTPTo = "you@example.com"

# Send an AWS SNS notification. Requires an API key and the 'boto3' Python library to be installed [topic urn|False]
NotifySNSTopic = False
NotifySNSAccessKey = ""
NotifySNSAccessSecret = ""
NotifySNSRegion = ""

#
# END CONFIGURATION
#

import sys
import os
import json
import sqlite3
import time
import cgi
import re
import socket
import urllib.request
import urllib.parse
import smtplib
import hashlib
from email.mime.text import MIMEText

VERSION = "2.0.6"
query = cgi.FieldStorage()
now = int(time.time())
login = False

def sha256(msg):
    return hashlib.sha256(str.encode(msg)).hexdigest()

#
# Headers
#
if query.getvalue("output") and query.getvalue("name"):
	print("Content-Type: text/plain; charset=utf-8")	
elif query.getvalue("api"):
	print("Content-Type: application/javascript; charset=utf-8")
else:
	print("Content-Type: text/html; charset=utf-8")

if query.getvalue("ac"): # Login from form
	if query.getvalue("ac") == AccessCode:
		print("Set-Cookie: ac=" + sha256(AccessCode))
		login = True
if 'HTTP_COOKIE' in os.environ: # Login from cookies
	cookies = os.environ['HTTP_COOKIE']
	cookies = cookies.split('; ')
	for cookie in cookies:
		cookie = cookie.split('=')
		if cookie[0] == 'ac' and cookie[1] == sha256(AccessCode):
			login = True
print()

#
# Database initialization
#
try:
	db = sqlite3.connect("../db/dashboard.db")
except:
	print("Could not connect to database. Make sure this script has write access to the '../db/' folder.")
	quit(1)

def queryDB(query, args): # Query DB and return all rows
	cur = db.cursor()
	cur.execute(query, args)
	rows = cur.fetchall()
	return rows

def execDB(query, args): # Exec DB function
	db.execute(query, args)
	db.commit()

try:
	execDB("CREATE TABLE IF NOT EXISTS systems (ip TEXT, name TEXT, cpu INT, interval INT, alarm INT, output TEXT, time INT);", [])
	execDB("CREATE TABLE IF NOT EXISTS history (name TEXT, cpu INT, time INT);", [])
	execDB("CREATE TABLE IF NOT EXISTS lostcontact (name TEXT);", [])
	execDB("CREATE TABLE IF NOT EXISTS log (sev INT, name TEXT, event TEXT, time INT);", [])
	execDB("CREATE TABLE IF NOT EXISTS probes (name TEXT, ip TEXT, type INT);", [])
except:
	print("Could not create required database schema. Try deleting all files in the '../db/' folder.")
	quit(1)

#
# Notifications
#
def notify(title, text):
	if NotifyPushbullet: # Pushbullet notification
		post_params = {
			'type': 'note',
			'title': 'Healthstone checks: ' + title,
			'body': text
		}
		post_args = urllib.parse.urlencode(post_params)
		data = post_args.encode()
		request = urllib.request.Request(url='https://api.pushbullet.com/v2/pushes', headers={'Authorization': 'Bearer ' + NotifyPushbullet}, data=data)
		result = urllib.request.urlopen(request)
	if NotifyNodePointURL: # NodePoint notification
		data = "api=add_ticket&key=" + NotifyNodePointKey + "&product_id=" + NotifyNodePointProduct + "&release_id=" + NotifyNodePointRelease + "&title=" + urllib.parse.quote("Healthstone checks: " + title, '') + "&description=" + urllib.parse.quote(text, '')
		result = urllib.request.urlopen(NotifyNodePointURL + "/?" + data)
	if NotifySMTPServer: # Email notification
		msg = MIMEText(text.replace('&gt;','>'))
		msg['Subject'] = 'Healthstone checks: ' + title
		msg['From'] = NotifySMTPFrom
		msg['To'] = NotifySMTPTo
		s = smtplib.SMTP(NotifySMTPServer)
		s.send_message(msg)
		s.quit()
	if NotifySNSTopic: # SNS notification
		import boto3
		sns = boto3.client('sns', aws_access_key_id=NotifySNSAccessKey, aws_secret_access_key=NotifySNSAccessSecret, region_name=NotifySNSRegion)
		sns.publish(TopicArn=NotifySNSTopic, Subject='Healthstone checks: ' + title, Message=text)


#
# Update list of lost contacts
#
lostcontact = []
rows = queryDB("SELECT name FROM lostcontact", [])
for row in rows:
	lostcontact.append(row[0])
rows = queryDB("SELECT * FROM systems", [])
for row in rows:
	if (row[6] + row[3] * 2 + 15) < time.time() and row[1] not in lostcontact:
		execDB("INSERT INTO lostcontact VALUES (?)", [row[1]])
		if DeleteOldEntries:
			execDB("DELETE FROM log WHERE name = ? AND time < ?", [row[1], now - 604800])
		execDB("INSERT INTO log VALUES (?, ?, ?, ?)", [1, row[1], "Lost contact with host.", now])
		if NotifyOnLostContact:
			notify("Lost contact with " + row[1], "Last contact: " + time.strftime("%Y/%m/%d %H:%M:%S", time.localtime(row[6])))

#
# If run from command line, only check probes
#
if 'REQUEST_METHOD' not in os.environ:
	print("Checking probes...")
	rows = queryDB("SELECT * FROM probes", [])
	for row in rows:
		if row[2] == 0: # ICMP check
			response = os.system("ping -c 1 -w2 " + row[1] + " > /dev/null")
		else: # TCP check
			s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			s.settimeout(2)
			try:
				s.connect((row[1], row[2]))
				s.close()
				response = 0
			except:
				response = 1
		print(row[0] + ": " + str(response))
		if response == 0:
			found = False
			rows2 = queryDB("SELECT * FROM systems WHERE name = ?", [row[0]])
			for row2 in rows2:
				execDB("UPDATE systems SET cpu = -1, interval = 60, alarm = 0, output = 'Probe', time = ?, ip = ? WHERE name = ?", [now, row[1], row[0]])
				found = True
			if not found:
				execDB("INSERT INTO systems VALUES(?, ?, -1, 60, 0, 'Probe', ?)", [row[1], row[0], now])
			rows2 = queryDB("SELECT * FROM lostcontact WHERE name = ?", [row[0]])
			for row2 in rows2:
				execDB("INSERT INTO log VALUES (?, ?, ?, ?)", [0, row[0], "Contact restored with host.", now])
			execDB("DELETE FROM lostcontact WHERE name = ?", [row[0]])
	quit(0)

#
# Connection from Healthstone agents
#
if query.getvalue("output") and query.getvalue("name"):
	cpu = 0
	alarm = 1
	interval = 300
	if query.getvalue("cpu"):
		cpu = int(float(query.getvalue("cpu")))
	if query.getvalue("alarms"):
		if query.getvalue("alarms").lower() == "false" or query.getvalue("alarms") == "0":
			alarm = 0
	if query.getvalue("interval"):
		interval = int(query.getvalue("interval"))
	found = False
	rows = queryDB("SELECT * FROM systems WHERE name = ?", [cgi.escape(query.getvalue("name"))])
	for row in rows:
		if row[4] == 0 and alarm == 1:
			if DeleteOldEntries:
				execDB("DELETE FROM log WHERE name = ? AND time < ?", [row[1], now - 604800])
			execDB("INSERT INTO log VALUES (?, ?, ?, ?)", [2, row[1], cgi.escape(query.getvalue("output")), now])
			if NotifyOnAlarms:
				notify("Alarms raised on " + row[1], cgi.escape(query.getvalue("output")))
		found = True
	if found:
		execDB("UPDATE systems SET cpu = ?, interval = ?, alarm = ?, output = ?, time = ?, ip = ? WHERE name = ?", [cpu, interval, alarm, cgi.escape(query.getvalue("output")), now, os.environ["REMOTE_ADDR"], cgi.escape(query.getvalue("name"))])
	else:
		execDB("INSERT INTO systems VALUES (?, ?, ?, ?, ?, ?, ?)", [os.environ["REMOTE_ADDR"], cgi.escape(query.getvalue("name")), cpu, interval, alarm, cgi.escape(query.getvalue("output")), now])
		execDB("INSERT INTO log VALUES (?, ?, ?, ?)", [0, cgi.escape(query.getvalue("name")), "New host added.", now])
	execDB("INSERT INTO history VALUES (?, ?, ?)", [cgi.escape(query.getvalue("name")), cpu, now])
	execDB("DELETE FROM history WHERE name = ? AND time < ?", [cgi.escape(query.getvalue("name")), now - (50 * interval)])
	rows = queryDB("SELECT * FROM lostcontact WHERE name = ?", [cgi.escape(query.getvalue("name"))])
	for row in rows:
		execDB("INSERT INTO log VALUES (?, ?, ?, ?)", [0, cgi.escape(query.getvalue("name")), "Contact restored with host.", now])		
	execDB("DELETE FROM lostcontact WHERE name = ?", [cgi.escape(query.getvalue("name"))])
	if query.getvalue("template"):
		try:
			f = open("../templates/" + re.sub(r'\W+', '', str(query.getvalue("template"))) + ".template", "r")
			for line in f:
				print(line)
			f.close()
		except:
			print("Invalid template requested.")
	else:
		print("OK")
	db.close()
	quit(0)

#
# JSON API
#
if query.getvalue("api"):
	output = {'status': "Ok."}
	if not login:
		output['status'] = "Error: Access code not provided."
	elif query.getvalue("api") == "systems": # List systems
		output['systems'] = []
		rows = queryDB("SELECT * FROM systems ORDER BY time DESC", [])
		for row in rows:
			output['systems'].append({'ip': row[0], 'name': row[1], 'cpu': row[2], 'interval': row[3], 'alarms': row[4], 'details': row[5], 'time': row[6]})
	elif query.getvalue("api") == "probes": # List probes
		output['probes'] = []
		rows = queryDB("SELECT * FROM probes", [])
		for row in rows:
			output['probes'].append({'name': row[0], 'ip': row[1], 'type': row[2]})
	elif query.getvalue("api") == "lostcontact": # List lost contact
		output['lostcontact'] = []
		rows = queryDB("SELECT * FROM lostcontact", [])
		for row in rows:
			output['lostcontact'].append({'name': row[0]})
	elif query.getvalue("api") == "log": # List log entries
		output['log'] = []
		rows = queryDB("SELECT * FROM log ORDER BY time DESC LIMIT 500", [])
		for row in rows:
			output['log'].append({'severity': row[0], 'name': row[1], 'event': row[2], 'time': row[3]})
	else:
		output['status'] = "Error: Unknown call."
	print(json.dumps(output, sort_keys = False, indent = 4))
	quit(0)

#
# Dashboard display
#
f = open("top.html", "r")
for line in f:
	print(line.replace("##TIME##", time.strftime("%Y/%m/%d %H:%M:%S")))
f.close()
if DarkTheme:
	print("""
<style>
html,body,.container,tr,td,.panel
{
    color: #FFFFFF !important;
    background-color: #000000 !important;
}
td
{
    font-size: 18px !important;
}
.navbar
{
	display: none;
}
</style><br>
""")

if not login: # Login form
	print("<p><form method='POST' action='.'><div class='row text-center'><div class='col-md-3'></div><div class='col-md-6'><input type='password' class='form-control' name='ac' placeholder='Access code'><br><input type='submit' class='btn btn-primary' value='Login'></div></div><div class='col-md-3'></div></form></p>")

elif query.getvalue("agents"): # Agents/probes page
	if query.getvalue("agents") == "2": # Add new probe
		try:
			execDB("INSERT INTO probes VALUES (?, ?, ?)", [cgi.escape(query.getvalue("probe-name")).replace('"', "'"), cgi.escape(query.getvalue("probe-ip")).replace('"', "'"), int(query.getvalue("probe-type"))])
			execDB("INSERT INTO systems VALUES(?, ?, -1, 60, 0, 'Probe', ?)", [cgi.escape(query.getvalue("probe-ip")).replace('"', "'"), cgi.escape(query.getvalue("probe-name")).replace('"', "'"), now])
			print("<p><center><b>Probe successfully added.</b></center></p>")
		except:
			print("<p><center><b>Could not add probe to the database.</b></center></p>")
	if query.getvalue("agents") == "3": # Delete a probe
		try:
			execDB("DELETE FROM probes WHERE ip = ? AND type = ?", [cgi.escape(query.getvalue("probe-ip")), int(query.getvalue("probe-type"))])
			execDB("DELETE FROM systems WHERE ip = ? AND cpu = -1", [cgi.escape(query.getvalue("probe-ip"))])
			print("<p><center><b>Probe successfully removed.</b></center></p>")
		except:
			print("<p><center><b>Could not remove probe from the database.</b></center></p>")
	f = open("agents.html", "r")
	for line in f:
		print(line)
	f.close()
	print("<p><h4>Add a new probe:</h4><div class='row'><form method='POST' action='./'><input type='hidden' name='agents' value='2'><div class='col-sm-3'><input type='text' name='probe-name' placeholder='Name' class='form-control' required></div><div class='col-sm-3'><input type='text' name='probe-ip' placeholder='IP address' class='form-control' required></div><div class='col-sm-3'><select name='probe-type' class='form-control'><option value=0>ICMP</option><option value=80>HTTP</option><option value=443>HTTPS</option><option value=22>SSH</option><option value=3389>RDP</option></select></div><div class='col-sm-3'><input type='submit' value='Add' class='form-control'></div></div></p>")
	print("<p><table class='table table-striped' id='probes'><thead><tr><th>Name</th><th>IP</th><th>Type</th></thead><tbody>")
	rows = queryDB("SELECT * FROM probes ORDER BY name", [])
	for row in rows:
		print("<tr><td>" + row[0] + "</td><td>" + row[1] + "</td><td>" + str(row[2]) + "<a style='float:right' href=\"./?agents=3&probe-ip=" + cgi.escape(row[1]) + "&probe-type=" + str(row[2]) + "\"><font color='red'><b>X</b></font></a></td></tr>")
	print("</tbody></table></p>")
	if not DarkTheme:
		print("<script>$(document).ready(function(){$('#probes').DataTable({'order':[[1,'asc']]});});</script>")

else: # Main dashboard
	if query.getvalue("ip") and query.getvalue("delete"): # delete an entry
		execDB("DELETE FROM systems WHERE ip = ? AND name = ?", [query.getvalue("ip"), query.getvalue("delete")])
		print("<p><center><b>The specified system has been removed from the list.</b></center></p>")

	if query.getvalue("ip") and query.getvalue("name"): # details on one system
		rows = queryDB("SELECT * FROM systems WHERE ip = ? AND name = ?", [query.getvalue("ip"), query.getvalue("name")])
		for row in rows:
			if (row[6] + row[3] * 2 + 15) < time.time():
				print("<div class='panel panel-warning'>")
			elif row[4] == 1:
				print("<div class='panel panel-danger'>")
			else:
				print("<div class='panel panel-success'>")
			print("<div class='panel-heading'><h3 class='panel-title'><span style='float:right'><i>" + time.strftime("%Y/%m/%d %H:%M:%S", time.localtime(row[6])) + "</i></span>" + row[1] + " (" + row[0] + ")</h3></div><div class='panel-body'><h4>System Profile</h4><pre>" + row[5] + "</pre><br>")
			if row[2] != -1: # Don't show CPU history for probes
				print("<h4>CPU History (Interval: " + str(float(row[3] / 60)) + " mins)</h4>")
				cpus = []
				times = []
				rows2 = queryDB("SELECT cpu,time FROM history WHERE name = ? ORDER BY time ASC LIMIT 50;", [query.getvalue("name")])
				for row2 in rows2:
					cpus.append(row2[0])
					times.append(row2[1])
				print("<canvas id='cpu' style='max-width:99%'></canvas><script>Chart.defaults.global.responsive = true; var data = { labels: [")
				i = 0
				for t in times:
					if i % 5 == 0:
						print("'" + time.strftime("%H:%M:%S", time.localtime(t)) + "'")
					else:
						print("''")
					i += 1
					if i < len(times):
						print(",")
				print("], datasets: [{ label: 'CPU History (Interval: " + str(float(row[3] / 60)) + " mins)', fillColor: '#F2FBFC', strokeColor: '#97BBCC', pointDot : false, data: [")
				i = 0
				for c in cpus:
					print(str(c))
					i += 1
					if i < len(cpus):
						print(",")
				print("] }]}; var ctx0 = document.getElementById('cpu').getContext('2d'); new Chart(ctx0).Line(data);</script>") 
			print("<br><h4>Last events</h4><table class='table table-striped' id='events'><thead><tr><th></th><th>Time</th><th>Event</th></tr></thead><tbody>")
			rows2 = queryDB("SELECT * FROM log WHERE name = ? ORDER BY time DESC LIMIT 500", [query.getvalue("name")])
			for row2 in rows2:
				print("<tr><td>")
				if int(row2[0]) == 2:
					print("<center><i class='fa fa-exclamation-triangle'></i></center>")
				elif int(row2[0]) == 1:
					print("<center><i class='fa fa-question-circle'></i></center>")
				else:
					print("<center><i class='fa fa-info'></i></center>")
				print("</td><td>" + time.strftime("%Y/%m/%d %H:%M:%S", time.localtime(row2[3])) + "</td><td>" + str(row2[2]).replace("\n"," ") + "</td></tr>")
			print("</tbody></table><script>$(document).ready(function(){$('#events').DataTable({'order':[[1,'desc']]});});</script>")
			print("<form method='GET' action='.'><input type='hidden' name='ip' value='" + row[0] + "'><input type='hidden' name='delete' value='" + row[1] + "'><input type='submit' class='btn btn-danger' value='Remove system'></form></div></div>")

	else: # list of systems
		# Large screens
		print("<div class='hidden-xs visible-md visible-sm visible-lg'><table class='table table-striped' id='systems'><thead><tr><th><i class='fa fa-laptop'></i></th><th>IP</th><th>Name</th><th>CPU</th><th>Last update</th><th>Status</th></tr></thead><tbody>")
		rows = queryDB("SELECT * FROM systems ORDER BY time DESC", [])
		for row in rows:
			print("<tr>")
			if "Microsoft Windows" in row[5]:
				print("<td><i class='fa fa-windows'></i></td>")
			elif "Linux" in row[5]:
				print("<td><i class='fa fa-linux'></i></td>")
			else:
				print("<td><i class='fa fa-laptop'></i></td>")			
			print("<td>" + row[0] + "</td><td>" + row[1] + "</td><td>")
			if row[2] == -1:
				print("-")
			else:
				print(str(row[2]) + "%")
			print("</td><td>" + time.strftime("%Y/%m/%d %H:%M:%S", time.localtime(row[6])) + "</td><td><form method='GET' action='.'><input type='hidden' name='ip' value='" + row[0] + "'><input type='hidden' name='name' value='" + row[1] + "'><input type='submit' class='btn ")
			if (row[6] + row[3] * 2 + 15) < time.time():
				print("btn-warning' value='Lost contact'>")		
			elif row[4] == 1:
				print("btn-danger' value='Alarms raised'>")
			else:
				print("btn-success' value='Ok'>")
			print("</form></td></tr>")	
		print("</tbody></table>")
		if not DarkTheme:
			print("<script>$(document).ready(function(){$('#systems').DataTable({'order':[[4,'desc']]});});</script>")	

		# Small screens
		print("</div><div class='visible-xs hidden-sm hidden-md hidden-lg'>")
		rows = queryDB("SELECT * FROM systems ORDER BY time DESC", [])
		for row in rows:
			print("<a href='./?ip=" + row[0] + "&name=" + row[1] + "'>")
			if (row[6] + row[3] * 2 + 15) < time.time():
				print("<div class='alert alert-warning' role='alert'><center>")
			elif row[4] == 1:
				print("<div class='alert alert-danger' role='alert'><center>")
			else:
				print("<div class='alert alert-success' role='alert'><center>")
			if "Microsoft Windows" in row[5]:
				print("<i class='fa fa-windows'></i>")
			elif "Linux" in row[5]:
				print("<i class='fa fa-linux'></i>")
			else:
				print("<i class='fa fa-laptop'></i>")
			print(" <b>" + row[1] + "</b> [" + row[0] + "] ")
			if row[2] != -1:
				print(str(row[2]) + "%")
			print("<br><i>" + time.strftime("%Y/%m/%d %H:%M:%S", time.localtime(row[6])) + "</i>")
			print("</center></div>")
		print("</div></a>")
		print("<br><center>" + os.popen("uptime").read().replace('\n','<br>') + "</center>")

f = open("bottom.html", "r")
for line in f:
	if query.getvalue("agents"):
		print(line.replace("##VERSION##", VERSION).replace("##LINK##", "<a href='./'>Back to dashboard</a>"))
	else:
		print(line.replace("##VERSION##", VERSION).replace("##LINK##", "<a href='./?agents=1'>Settings</a>"))
f.close()
db.close()
