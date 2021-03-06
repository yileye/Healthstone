About
=====

Healthstone is an open source, lightweight, self-hosted and agent based system monitoring solution able to run many customizable health checks. 
It is composed of a dashboard which runs on a Windows or Linux server, along with agents for Windows and Linux hosts that you wish to monitor. 
The Windows agent is a binary which runs as a system service and connects to this dashboard, while the Linux agent is a Python script doing the 
same thing. The dashboard can be customized to send you notifications through email, Pushbullet or NodePoint tickets when a client stops checking 
in, or if any of the configured checks fails. Configuration is retrieved in the form of templates from the dashboard by all agents. Templates are 
stored in the templates folder and can be customized for your needs.

The server component runs the dashboard against which Healthstone clients can register. It must be run on a Linux server with Python 3.x and 
Apache installed, or a Windows server with IIS (with the CGI and ISAP features) and Python 3.x installed. The dashboard also has the ability to
use probes for hosts that you want to monitor without agents. Probes are checked on a schedule every 1 minute.

https://healthstone.ca


Installation procedure
======================

* Ensure the required software is installed (Python 3.x, along with Apache for Linux or IIS for Windows).
* Download healthstone.zip onto your server and run setup.bat as a local administrator on Windows, or setup.sh as root on Linux.
* Login at http://localhost/healthstone, then click on 'Settings' to configure settings and download the agent packages.

The default access code is '1234'.


Templates
=========

When an agent connects to the dashboard, it pulls its template. You can use any number of templates, divided into any grouping you choose. The 
dashboard URL and template name is configured at installation time. For example, if you install an agent and specify "darwin" as the template it 
should use, the agent will try to fetch the file "templates/darwin.template" on the dashboard server.

Each template lists a number of modules that you wish the agents to process. Only the [General] section is mandatory, but each section kept must 
have all its keys listed. Do not use quotes or multiple lines for key values. Templates are not saved on hosts, each agent will fetch its 
specific template on every poll. Template filenames must contain only alphanumeric characters and end with .template. The same template can be 
used for Windows and Linux agents, although you may want to create multiple templates and divide them according to your network needs, such as a 
template for Windows servers, one for workstations, one for Linux, etc.

If a template has a syntax error in it, or if an invalid template is provided, the agent will revert back to a basic set of checks, with no 
module enabled and a 30 seconds poll interval.


API
===

The dashboard can provide results in a JSON format with the following calls by passing GET parameters. The two required parameters include 'ac'
for the access code and 'api' for the API call. Example: dashboard.py?api=systems&ac=1234

Here are the supported API calls:
systems: List all systems.
probes: List all probes.
lostcontact: List all systems that lost contact.
log: List the last 500 log entries.


FAQ
===

* Why can't I access the dashboard in a web browser?

Make sure Python 3.x is installed correctly. Try to run dashboard.py manually from the command line and see the resulting HTML code. Make sure it 
has write access to the ../db folder. Make sure CGI support is enabled on your web server.

* How do I use a proxy server?

On Linux, the proper http_proxy and https_proxy environment variables must be set prior to Healthstone agent starting. On Windows, add the 
Registry key proxy to HKLM/Software/Healthstone in the format: http://proxy-server.com:port.

* How do I change the dashboard or template agents use?

On Windows, edit the Registry entries in HKLM/Software/Healthstone with the new values then restart the service. On Linux, edit /etc/rc.local, 
kill the currently running agent and restart it.

* Why is the Windows agent unable to connect to my highly secure dashboard site?

Some versions of Windows will not be able to connect to a dashboard running on a web server only offering TLS 1.1 or above. Add the Registry 
setting tlsconly in HKLM/Software/Healthstone then restart the service.

* The agents don't show up on the dashboard, how do I troubleshoot the issue?

For the Linux agent, make sure the script is running with ps aux | grep healthstone. If it isn't, try to start it manually and see if any error 
occurs: /usr/bin/healthstone.py <dashboard url> <template name>. For the Windows agent, check the Event Viewer under the Application log, all 
errors should be logged there.

* I see this error in the Event Log: Cannot load Counter Name data because an invalid index?

Some Windows systems seem to have their performance cache get corrupted from time to time. Try the following in an Administrator command window: 
lodctr /r.

* Why is the Linux agent not running/stopped unexpectingly?

Check the log at /var/log/healthstone.log for hints as to why it stopped. Try to run the agent manually. The agent is set to run automatically on 
boot from /etc/rc.local.

* Agents are not reporting any check or losing contact after a template change?

Make sure your template is not corrupted or misformed. Agents are set to revert to the default configuration of 30 seconds interval with no 
module being run if they cannot parse the template successfully. There is also a limit to the amount of data passed by the agents, try turning 
verbose to false.

* I'm not getting notifications?

Check the Apache log to see if the notify function failed for some reason. This should be under /var/log/httpd/<site_name>.error_log.

* Probes are not working?

Probes rely on the dashboard component to run every minute on schedule. The setup process attempts to add a crontab entry (for Linux) or a
scheduled task (on Windows) to run the script. Check your system logs to see if the task runs properly, and fix any error that may prevent it
from running.


License
=======

The MIT License (MIT)

Copyright (c) 2015-2017 Patrick Lambert

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

