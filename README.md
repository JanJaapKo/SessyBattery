# Sessy Battery - Domoticz Python plugin
Domoticz plugin for Sessy batteries

## Prerequisites

- Follow the Domoticz guide on [Using Python Plugins](https://www.domoticz.com/wiki/Using_Python_plugins) to enable the plugin framework.

The following Python modules installed
```
sudo apt-get update
sudo apt-get install python3-requests
sudo pip3 install numpy
```

## Installation

1. Clone repository into your domoticz plugins folder
```
cd domoticz/plugins
git clone https://github.com/JanJaapKo/SessyBattery
```
to update:
```
cd domoticz/plugins/SessyBattery
git pull https://github.com/JanJaapKo/SessyBattery
```
2. Restart domoticz
3. Go to "Hardware" page and add new item with type "SessyBattery"


## Configuration
At first setup, the plugin needs to connect to the Dyson cloud provider to get the credentials to acces the machine. Since early 2021 a 2-factor authentication is 