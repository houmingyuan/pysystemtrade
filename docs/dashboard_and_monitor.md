This document describes how to monitor pysystemtrade in a production environment.

It will make no sense unless you've already read:

- [Using pysystemtrade in production](/docs/production.md)

Table of Contents
=================

* [Web Dashboard](#web-dashboard)
* [System monitor](#system-monitor)
* [Handling of crashed processes](#handling-of-crashed-processes)
* [Running a remote dashboard or monitor](#running-a-remote-dashboard-or-monitor)

Created by [gh-md-toc](https://github.com/ekalinin/github-markdown-toc)


# Web Dashboard

*The dashboard is currently a work in progress - functionality is still being added.*

At the moment, the dashboard provides basic diagnostic "traffic lights" to show status of various system components. The content of the reports is also reproduced.

If you have installed all the Python dependencies listed in the `pyproject.toml` file, the web dashboard is ready to be started:

```
cd pysystemtrade/dashboard
python3 app.py
```

Visit `http://localhost:5000/` to view the dashboard. To remap this location or to make it accessible from outside machines (do this at your own peril!) you need to do the following:

- Bash terminal (linux): `sudo ufw allow 5000`
- Add the following parameter to your private_control_config.yaml `dashboard_visible_on_lan: True`

To listen on a different port (for example on macOS, where port 5000 is used by AirPlay Receiver), set the `DASHBOARD_PORT` environment variable:

```
cd pysystemtrade/dashboard
DASHBOARD_PORT=5057 python3 app.py
```

The page refreshes itself automatically. The interval (in seconds) is read from `dashboard_refresh_seconds` in `private_control_config.yaml`, defaulting to 60; set it to 0 to disable auto refresh. The time of the last successful refresh, and any endpoint that failed, are shown at the top of the page.

The dashboard renders each report on demand from the same data and reporting code as the CLI reports. Early in the life of a system there may be no held positions or sampled spread data, in which case the affected tabs (for example Risk and Costs) show empty tables rather than failing. An instrument with stale or missing contract data is shown in the Rolls tab with a `Data error` status and no roll buttons, instead of breaking the whole view.

### Load test

`dashboard/load_test.py` measures how long the dashboard takes to load, per endpoint and per tab, using a real headless browser (Playwright driving the system Chrome). It also warns about any request to an external host, since the dashboard is meant to be self-contained.

```
# start a dashboard on a free port, test it, then stop it
python3 dashboard/load_test.py --start-server

# test an already running dashboard
python3 dashboard/load_test.py --base-url http://127.0.0.1:5057

# three cycles, subset of tabs, also save raw results as json
python3 dashboard/load_test.py --start-server --repeat 3 --tabs rolls,costs --json /tmp/dash.json
```

# System monitor

Alternatively, there is a simple monitoring tool which also outputs an .html file and only shows which processes are running. To use it, add the following two commands to your crontab on reboot, or run manually eg using [screen](https://linuxize.com/post/how-to-use-linux-screen/):

```
cd ~pysystemtrade/private/; python3 -m http.server
cd ~pysystemtrade/syscontrol/; python3 monitor.py
```

Once your machine has started you should be able to go to `http://192.168.1.13:8000/` (change the IP address as required) on any LAN connected machine and see the status of the system.

# Handling of crashed processes

Whilst running the monitor and dashboard will also handle any 'crashed' processes (those where the PID that is registered is killed without the process being properly close); it will email the user, update the web log, and mark the process as close so it can be run again. **It will not automatically respawn the processes!** (you will have to do that manually or wait until the crontab does so the next day).

# Running a remote dashboard or monitor

You may prefer to run your monitor or dashboard from another machine. Let's assume the trading server (the machine that is being monitored), is also the machine that is hosting your MongoDB instance, and has an IP address of 192.168.0.13; and the remote monitoring machine is on 192.168.0.10:

- Add an ip address to the `bind_ip` line in the `/etc/mongod.conf` file to allow connections from other machines `eg bind_ip=localhost, 192.168.0.10` or change your call to MongoDB eg in linux `mongod --dbpath /home/rob/data/mongodb --bind_ip_all` (**warning, insecure unless you have other security eg firewall**). This is required
- set up ssh so that it does not require password login from the remote machine, only ssh-key (**again, has security implications so make sure you know what you are doing!**). This is necessary for remote process monitoring to work via ssh.
- Add the monitoring machine IP (192.168.0.10) to the whitelist for your IB gateway software.
- You may need to change your firewall settings to open up ports 27017 (MongoDB) and 4001 (IB, unless you use a different port); eg in linux using UFW (`sudo ufw enable`, `sudo ufw allow 27017 from 192.168.0.10`) or iptables

Then on the monitoring machine:

- You may need to change your firewall settings to open up ports 27017 (MongoDB) and 4001 (IB, unless you use a different port).
- you will need to modify the `private_config.yaml` system configuration file so it connects to a different IP address eg `mongo_host: 192.168.0.13`
- you will need to modify the `private_config.yaml` system configuration file so it connects to a different IP address eg `ib_ipaddress: 192.168.0.13` 
- add the following to your `private_config.yaml` file so that the process monitoring works correctly

`trading_server_ip: 192.168.0.13`
`trading_server_username: 'rob'`
`trading_server_ssh_port: 22` (optional, defaults to port 22)
