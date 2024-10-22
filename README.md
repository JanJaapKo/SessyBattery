# Sessy Battery - Domoticz Python plugin
Domoticz plugin for Sessy batteries

Preliminary version, breaking changes to be expected!<br>
reads state and percentage of batteries<br><br>
planned developments:
- implement al measurements per battery
- implement summary for all batteries (like total power, SoC etc)
- implement data from p1 meter
- implement OpenAPI spec to allow controlling the batteries from Domoticz

## Prerequisites

- Follow the Domoticz guide on [Using Python Plugins](https://www.domoticz.com/wiki/Using_Python_plugins) to enable the plugin framework.

The following Python modules installed
```
sudo apt-get update
sudo apt-get install python3-requests
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
First fill the ```config.json``` file in the plugin directory with the connection details for the batteries and the P1 unit.
Then create the hardware needed in the Domoticz hardware page. Default configuration works, but can be altered when desired.
