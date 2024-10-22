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
# Domoticz plugin to handle communction to Sessy bateries
#
"""
<plugin key="SessyBattery" name="Sessy battery" author="Jan-Jaap Kostelijk" version="0.0.4" externallink="https://github.com/JanJaapKo/SessyBattery">
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
                <option label="1m" value="6" default="true"/>
                <option label="5m" value="30"/>
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
    from fakeDomoticz import *
    from fakeDomoticz import Domoticz
    Domoticz = Domoticz()
    debug = True

import json
import time
import requests

class SessyBatteryPlugin:
    #define class variables
    enabled = False

    #unit numbers for devices to create
    #  1: Sensor type 'Percentage' and call it 'Sessy battery percentage'
    batPercentageUnit = 1
    #  2: Sensor type 'Usage (Electric)' and call it 'Sessy battery power'
    batPowerUnit = 2
    #  3: Sensor type 'Electric (Instant+Counter)' and call it 'Sessy Battery Energy Delivered' Go to Utility select the device and set 'type' to 'Return' and 'Energy read' to Computed
    batEnergyDeliveredUnit = 3
    #  4: Sensor type 'Electric (Instant+Counter)' and call it 'Sessy Battery Energy Stored' Go to Utility select the device and set 'type' to 'Usage' and set 'Energy read' to Computed
    batEnergyStoredUnit = 4
    #  5: Sensor type 'Text' and call it 'Sessy battery state'
    batBatteryGeneralStateUnit = 5
    #  6: Sensor type 'Text' and call it 'Sessy battery detailed state'
    batBatteryDetailedStateUnit = 6
    #  7: Sensor type 'Custom Sensor' and call it 'Mains frequency'
    batFrequencyUnit = 7
    #  8: Sensor type 'Voltage' and call it 'Mains phase 1 voltage'
    batPhase1VoltageUnit = 8
    #  9: Sensor type 'Ampere (1 Phase)'and call it 'Mains phase 1 Current'
    batPhase1CurrentUnit = 9
    # 10: Sensor type 'Usage (Electric)' and call it 'Mains phase 1 power'
    batPhase1PowerUnit = 10
    # 11: Sensor type 'Voltage' and call it 'Mains phase 2 voltage'
    batPhase2VoltageUnit = 11
    # 12: Sensor type 'Ampere (1 Phase)'and call it 'Mains phase 2 Current'
    batPhase2CurrentUnit = 12
    # 13: Sensor type 'Usage (Electric)' and call it 'Mains phase 2 power'
    batPhase2PowerUnit = 13
    # 14: Sensor type 'Voltage' and call it 'Mains phase 3 voltage'
    batPhase3VoltageUnit = 14
    # 15: Sensor type 'Ampere (1 Phase)'and call it 'Mains phase 3 Current'
    batPhase3CurrentUnit = 15
    # 16: Sensor type 'Usage (Electric)' and call it 'Mains phase 3 power'
    batPhase3PowerUnit = 16
    # 17: Sensor type 'Text' and call it 'Sessy P1 meter state'
    p1MeterStateUnit = 17
    # 18: Sensor type 'Text' and call it 'Sessy battery update state'
    batUpdateStateUnit = 18
    # 19: Sensor type 'Text' and call it 'Sessy serial update state'
    batSerialUpdateUnit = 19
    # 20: Sensor type 'Text' and call it 'P1 meter update state'
    p1UpdateState = 20

    runCounter = 6
    
    def onStart(self):
        Domoticz.Debug("onStart called")
        #read out parameters for local connection
        self.runCounter = int(Parameters['Mode2'])
        self.log_level = Parameters['Mode4']

        if self.log_level == 'Debug':
            Domoticz.Debugging(2)
            DumpConfigToLog()
        if self.log_level == 'Verbose':
            Domoticz.Debugging(1+2+4+8+16+64)
            DumpConfigToLog()

        Domoticz.Log("starting plugin version "+Parameters["Version"])
        Domoticz.Heartbeat(10)
        
        #read config parameters from disk
        source_path = Parameters['HomeFolder']
        config_file = source_path + 'config.json'
        config_map = ""
        with open(config_file) as f:
            config_map = json.load(f)
            Domoticz.Debug("config map = "+ str(config_map))
        
        self.num_batteries = len(config_map["batteries"])
        Domoticz.Log("Found " + str(self.num_batteries) + " batteries")
        
        self.devices_dict = {}
        devices_names = self.get_device_names(config_map)
        for battery in config_map["batteries"]:
            self.devices_dict[battery["name"]] = SessyBattery(battery)
            self.createBatteryUnits(battery["name"])
            data = self.devices_dict[battery["name"]].GetDataFromDevice()
            Domoticz.Debug("initial data query '" + battery["name"] + "': " + str(data))
            self.updateBatteryUnits(battery["name"], data)
        
        return

    def onHeartbeat(self):
        self.runCounter = self.runCounter - 1
        if self.runCounter <= 0:
            Domoticz.Debug("Poll unit")
            self.runCounter = int(Parameters['Mode2'])
            for battery in self.devices_dict:
                    Domoticz.Debug("polling battery: '" +battery+"'")
                    data = self.devices_dict[battery].GetDataFromDevice()
                    self.updateBatteryUnits(battery, data)

        Domoticz.Debug("Polling unit in " + str(self.runCounter) + " heartbeats.")
        
    def onStop(self):
        Domoticz.Debug("stopping plugin")

    def get_device_names(self, configmap):
        """find the amount of stored devices"""
        devices = {}
        for x in configmap["p1meter"]:
            devices[str(x["name"])] = "p1meter"
        for x in configmap["batteries"]:
            devices[str(x["name"])] = "battery"
        Domoticz.Debug("get_device_names, list of configured devices: " + str(devices))
        return devices

    def createBatteryUnits(self, deviceId):
        #check, per device, if it has units. If not,create them 
        Domoticz.Debug("Creating units for: '" + deviceId +"'")
        if deviceId not in Devices or (self.batPercentageUnit not in Devices[deviceId].Units):
            Domoticz.Unit(Name=deviceId + ' - Battery percentage', Unit=self.batPercentageUnit, TypeName="General", Subtype=6, DeviceID=deviceId).Create()
        if deviceId not in Devices or (self.batBatteryGeneralStateUnit not in Devices[deviceId].Units):
            Domoticz.Unit(Name=deviceId + ' - Battery general state', Unit=self.batBatteryGeneralStateUnit, TypeName="General", Subtype=19, DeviceID=deviceId).Create()
        if deviceId not in Devices or (self.batBatteryDetailedStateUnit not in Devices[deviceId].Units):
            Domoticz.Unit(Name=deviceId + ' - Battery detailed state', Unit=self.batBatteryDetailedStateUnit, TypeName="General", Subtype=19, DeviceID=deviceId).Create()

    def updateBatteryUnits(self, device, data):
        if "sessy" in data:
                if "state_of_charge" in data["sessy"]:
                    #battery state of charge. Percentage with high number of decimals, needs to be trimmed
                    perc = round(data["sessy"]["state_of_charge"]*100,1)
                    UpdateDevice(device, self.batPercentageUnit, perc, str(perc))
                if "system_state" in data["sessy"]:
                    UpdateDevice(device, self.batBatteryGeneralStateUnit, 1, str(data["sessy"]["system_state"]))
                if "system_state_details" in data["sessy"]:
                    UpdateDevice(device, self.batBatteryDetailedStateUnit, 1, str(data["sessy"]["system_state_details"]))
                else:
                    UpdateDevice(device, self.batBatteryDetailedStateUnit, 1, "all ok")
                    
        return

class SessyBattery():
    def __init__(self, config):
        self.__name = config["name"]
        self.ip = config["ip"]
        self.user = config["user"]
        self.pwd = config["pwd"]
        self.url = 'http://'+ self.user + ':' + self.pwd + '@' + self.ip + '/api/v1/power/status'

    def GetDataFromDevice(self):
       response = requests.get(self.url)
       #jsonData = json.loads(response.text)
       return response.json()

    @property
    def name(self):
        return self.__name


global _plugin
_plugin = SessyBatteryPlugin()

def onStart():
    global _plugin
    _plugin.onStart()

def onStop():
    global _plugin
    _plugin.onStop()

def onConnect(Connection, Status, Description):
    global _plugin
    _plugin.onConnect(Connection, Status, Description)

def onDisconnect(Connection):
    global _plugin
    _plugin.onDisconnect(Connection)

def onMessage(Connection, Data):
    global _plugin
    _plugin.onMessage(Connection, Data)

def onCommand(DeviceID, Unit, Command, Level, Color):
    global _plugin
    _plugin.onCommand(DeviceID, Unit, Command, Level, Color)

def onNotification(Name, Subject, Text, Status, Priority, Sound, ImageFile):
    global _plugin
    _plugin.onNotification(Name, Subject, Text, Status, Priority, Sound, ImageFile)

def onHeartbeat():
    global _plugin
    _plugin.onHeartbeat()

def onDeviceRemoved(DeviceID, Unit):
    global _plugin
    _plugin.onDeviceRemoved(DeviceID, Unit)
       
# Configuration Helpers
def getConfigItem(Key=None, Default={}):
   Value = Default
   try:
       Config = Domoticz.Configuration()
       if (Key != None):
           Value = Config[Key] # only return requested key if there was one
       else:
           Value = Config      # return the whole configuration if no key
   except KeyError:
       Value = Default
   except Exception as inst:
       Domoticz.Error("Domoticz.Configuration read failed: '"+str(inst)+"'")
   return Value
   
def setConfigItem(Key=None, Value=None):
    Config = {}
    if type(Value) not in (str, int, float, bool, bytes, bytearray, list, dict):
        Domoticz.Error("A value is specified of a not allowed type: '" + str(type(Value)) + "'")
        return Config
    try:
       Config = Domoticz.Configuration()
       if (Key != None):
           Config[Key] = Value
       else:
           Config = Value  # set whole configuration if no key specified
       Config = Domoticz.Configuration(Config)
    except Exception as inst:
       Domoticz.Error("Domoticz.Configuration operation failed: '"+str(inst)+"'")
    return Config

    # Generic helper functions
def DumpConfigToLog():
    Domoticz.Debug("Parameter count: " + str(len(Parameters)))
    for x in Parameters:
        if Parameters[x] != "":
            Domoticz.Debug( "Parameter '" + x + "':'" + str(Parameters[x]) + "'")
    Configurations = getConfigItem()
    Domoticz.Debug("Configuration count: " + str(len(Configurations)))
    for x in Configurations:
        if Configurations[x] != "":
            Domoticz.Debug( "Configuration '" + x + "':'" + str(Configurations[x]) + "'")
    Domoticz.Debug("Device count: " + str(len(Devices)))
    for x in Devices:
        Domoticz.Debug("Device:           " + str(x) + " - " + str(Devices[x]))
    return

def UpdateDevice(Device, Unit, nValue, sValue, AlwaysUpdate=False, Name=""):
    # Make sure that the Domoticz device still exists (they can be deleted) before updating it
    if (Device in Devices and Unit in Devices[Device].Units):
        if (Devices[Device].Units[Unit].nValue != nValue) or (Devices[Device].Units[Unit].sValue != sValue) or AlwaysUpdate:
                Domoticz.Log("Updating device '"+Devices[Device].Units[Unit].Name+ "' with current sValue '"+Devices[Device].Units[Unit].sValue+"' to '" +sValue+"'")
            #try:
                Devices[Device].Units[Unit].nValue = nValue
                Devices[Device].Units[Unit].sValue = sValue
                if Name != "":
                    Devices[Device].Units[Unit].Name = Name
                Devices[Device].Units[Unit].Update()
                
                #logging.debug("Update "+str(nValue)+":'"+str(sValue)+"' ("+Devices[Device].Units[Unit].Name+")")
            # except:
                # Domoticz.Error("Update of device failed: "+str(Unit)+"!")
                # logging.error("Update of device failed: "+str(Unit)+"!")
    else:
        Domoticz.Error("trying to update a non-existent unit "+str(Unit)+" from device "+str(Device))
    return
