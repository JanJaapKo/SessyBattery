# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is furnished
# to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# Author: Jan-Jaap Kostelijk
#
# Domoticz plugin to handle communction to Dyson devices
#
"""
<plugin key="DysonPureLink" name="Sessy battery" author="Jan-Jaap Kostelijk" version="0.0.2" externallink="https://github.com/JanJaapKo/SessyBattery">
    <description>
        <h2>Sessy Battery plugin</h2><br/>
        Connects to Sessy batteries and P1 dongle.
        <h2>Configuration</h2>
        Configuration of the plugin is a 2 step action: the plugin here in Domoticz and a json file in the plugin directory.<br/><br/>
        
    </description>
    <params>
		<param field="Mode4" label="Debug" width="75px">
            <options>
                <option label="Verbose" value="Verbose"/>
                <option label="True" value="Debug"/>
                <option label="False" value="Normal" default="true"/>
                <option label="Reset cloud data" value="Reset"/>
            </options>
        </param>
        <param field="Mode2" label="Refresh interval" width="75px">
            <options>
                <option label="20s" value="2"/>
                <option label="1m" value="6"/>
                <option label="5m" value="30" default="true"/>
                <option label="10m" value="60"/>
                <option label="15m" value="90"/>
            </options>
        </param>
    </params>
</plugin>
"""

try:
	import DomoticzEx as Domoticz
	debug = False
except ImportError:
	import fakeDomoticz as Domoticz
	debug = True
import json
import time

class SessyBatteryPlugin:
    #define class variables
    enabled = False
    #unit numbers for devices to create
    fanModeUnit = 1
    nightModeUnit = 2
    fanSpeedUnit = 3
    fanOscillationUnit = 4
    standbyMonitoringUnit = 5
    filterLifeUnit = 6
    qualityTargetUnit = 7
    tempHumUnit = 8
    volatileUnit = 9
    particlesUnit = 10
    sleepTimeUnit = 11
    fanStateUnit = 12
    fanFocusUnit = 13
    fanModeAutoUnit = 14
    particles2_5Unit = 15
    particles10Unit = 16
    nitrogenDioxideDensityUnit = 17
    heatModeUnit = 18
    heatTargetUnit = 19
    heatStateUnit = 20
    particlesMatter25Unit = 21
    particlesMatter10Unit = 22
    resetFilterLifeUnit = 23
    deviceStatusUnit = 24

    runCounter = 6
