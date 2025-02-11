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
<plugin key="SessyBattery" name="Sessy battery" author="Jan-Jaap Kostelijk" version="0.1.6" externallink="https://github.com/JanJaapKo/SessyBattery">
    <description>
        <h2>Sessy Battery plugin</h2><br/>
        Connects to Sessy batteries and P1 dongle.
        <h2>Configuration</h2>
        Configuration of the plugin is a 2 step action: the plugin here in Domoticz and a json file in the plugin directory.<br/><br/>
        
    </description>
    <params>
        <param field="Mode1" label="Minimum power [W]" width="75px" default="200">
            <description>Minimum and maximum allowed power per battery, for both charge and discharge</description>
        </param>
        <param field="Mode3" label="Maximum power [W]" width="75px" default="2200"/>
		<param field="Mode4" label="Debug" width="75px">
            <options>
                <option label="Verbose" value="Verbose"/>
                <option label="True" value="Debug"/>
                <option label="False" value="Normal" default="true"/>
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
import logging
import json
import time
import requests
from datetime import datetime, timedelta
import exceptions

P1_FACTOR = 10 # number of battery polls before polling P1
dt_format = "%Y-%m-%d %H:%M:%S"

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
    # 21: sensor type 'Text', 'P1 tarif'
    p1TarifUnit = 21
    # 22: sensor type '`P1 smart meter', 'Total energy'
    batEnergyUnit = 22
    # 23: sensor type 'switch', 'Power strategy'
    batStrategyUnit = 23
    # 24: sensor type '?', 'Power setpoint'
    batPowerSetpointUnit = 24
    # 24: sensor type '?', 'Error/warning'
    batErrorWarning = 25
    # 24: sensor type 'switch', 
    batStrategyOverridden = 26

    runCounter = 6
    p1Counter = P1_FACTOR
    system_name  = "Sessy system"
    
    def onStart(self):
        self.log_filename = "sessy_"+Parameters["Name"]+".log"
        Domoticz.Log('Plugin starting new version')
        #read out parameters for local connection
        self.runCounter = int(Parameters['Mode2'])
        self.log_level = Parameters['Mode4']
        self.systemPercent = 0
        self.systemPower = 0
        self.systemPowerDelivered = 0
        self.systemPowerStored = 0
        self.systemEnergyDelivered = 0
        self.systemEnergyStored = 0
        self.powerStrat = 0
        self.powerSetpoint = 0
        self.minPower = int(Parameters['Mode1'])
        self.maxPower = int(Parameters['Mode3'])

        logging.basicConfig(format='%(asctime)s - %(levelname)-8s - %(filename)-18s - %(message)s', filename=self.log_filename,level=logging.INFO)
        if self.log_level == 'Debug':
            #logging.basicConfig(format='%(asctime)s - %(levelname)-8s - %(filename)-18s - %(message)s', filename=self.log_filename,level=logging.DEBUG)
            logging.basicConfig(level=logging.DEBUG)
            Domoticz.Log("Starting Sessy Battery plugin, logging to file {0}".format(self.log_filename))
            Domoticz.Debugging(2)
            DumpConfigToLog()
        if self.log_level == 'Verbose':
            Domoticz.Debugging(1+2+4+8+16+64)
            DumpConfigToLog()
            #logging.basicConfig(format='%(asctime)s - %(levelname)-8s - %(filename)-18s - %(message)s', filename=self.log_filename,level=logging.DEBUG)
            logging.basicConfig(level=logging.DEBUG)

        Domoticz.Log("starting plugin version "+Parameters["Version"])
        logging.info("starting plugin version "+Parameters["Version"])
        #Domoticz.Heartbeat(10)
        
        #read config parameters from disk
        source_path = Parameters['HomeFolder']
        config_file = source_path + 'config.json'
        config_map = ""
        with open(config_file) as f:
            try:
                config_map = json.load(f)
            except json.decoder.JSONDecodeError as theError:
                Domoticz.Error("JSON error in config file. Error: '" + str(theError.msg) + "' at position: line " + str(theError.lineno) + " column "+ str(theError.colno))
                logging.error("JSON error in config file. Error: '" + str(theError.msg) + "' at position: line " + str(theError.lineno) + " column "+ str(theError.colno))
                return
        logging.debug("config map = "+ str(config_map))
        
        # create the p1 meter first
        self.createP1Units("Sessy P1")
        self.p1unit = SessyP1(config_map["p1meter"][0])
        p1data = self.p1unit.getDetails()
        logging.debug("P1 meter details: " + str(p1data))
        Domoticz.Log("connected to P1 meter '" + self.p1unit.name + "', status is '"+ p1data["status"] + "'")
        logging.debug("connected to P1 meter '" + self.p1unit.name + "', status is '"+ p1data["status"] + "'")
        self.updateP1Units("Sessy P1", p1data)

        # create battery units
        self.num_batteries = len(config_map["batteries"])
        Domoticz.Log("Found " + str(self.num_batteries) + " batteries")
        logging.debug("Found " + str(self.num_batteries) + " batteries")
        
        self.devices_dict = {}
        devices_names = self.get_device_names(config_map)
        for battery in config_map["batteries"]:
            self.devices_dict[battery["name"]] = SessyBattery(battery)
            self.createBatteryUnits(battery["name"])
            data = self.devices_dict[battery["name"]].getPowerStatus()
            logging.debug("initial data query power status '" + battery["name"] + "': " + str(data))
            energy = self.devices_dict[battery["name"]].getEnergyStatus()
            self.updateBatteryUnits(battery["name"], data, energy)
            logging.debug("initial data query energy status '" + battery["name"] + "': " + str(energy))
            self.updatePowerStrategy(battery["name"], self.devices_dict[battery["name"]].getPowerStrategy())
        
        #create system units
        self.createSystemUnits(self.system_name)
        self.updateSystemUnits(self.system_name, len(config_map["batteries"]))
        self.updatePowerStrategy(self.system_name, "")
        self.enabled = True # onStart executed succesfull, enable heartbeats
        return

    def onHeartbeat(self):
        self.runCounter = self.runCounter - 1
        if self.runCounter <= 0:
            logging.debug("Poll unit")
            if not self.enabled:
                Domoticz.Log("Skipping updates since onStart not properly completed")
                return
            self.runCounter = int(Parameters['Mode2'])
            for battery in self.devices_dict:
                logging.debug("polling battery: '" +battery+"'")
                for i in range(1, 4):
                    try:
                        powerData = self.devices_dict[battery].getPowerStatus()
                        if powerData['status'] == 'ok':
                            break
                    except exceptions.RequestError as e:
                        Domoticz.Error(f"an error occured while reading data from {battery}: {e}")
                        logging.error(f"an error occured while reading data from {battery}: {e}")
                        #return
                    except requests.exceptions.RequestException as exp:
                        logging.error("RequestException: " + str(exp))
                        Domoticz.Error("RequestException: " + str(exp))
                        #return
                    time.sleep(i ** 3)
                else:
                    raise exceptions.TooManyRetries
                for i in range(1, 4):
                    try:
                        energyData = self.devices_dict[battery].getEnergyStatus()
                        if energyData['status'] == 'ok':
                            break
                    except exceptions.RequestError as e:
                        Domoticz.Error(f"an error occured while reading data from {battery}: {e}")
                        logging.error(f"an error occured while reading data from {battery}: {e}")
                        #return
                    except requests.exceptions.RequestException as exp:
                        logging.error("RequestException: " + str(exp))
                        Domoticz.Error("RequestException: " + str(exp))
                        #return
                    time.sleep(i ** 3)
                else:
                    raise exceptions.TooManyRetries
                self.updateBatteryUnits(battery, powerData, energyData)
                self.updatePowerStrategy(battery, self.devices_dict[battery].getPowerStrategy())
                if datetime.now().minute == 1:
                    # check if there is data
                    self.devices_dict[battery].getDynamicSchedule()
            self.updateSystemUnits("Sessy system", len(self.devices_dict))
            self.updatePowerStrategy(self.system_name, "")

            self.p1Counter = self.p1Counter - 1
            if self.p1Counter <= 0:
                self.p1Counter = P1_FACTOR
                p1data = self.p1unit.getDetails()
                logging.debug("P1 meter details: " + str(p1data))
                self.updateP1Units("Sessy P1", p1data)

        logging.debug("Polling unit in " + str(self.runCounter) + " heartbeats.")

    def onCommand(self, DeviceID, Unit, Command, Level, Hue):
        logging.debug("onCommand called for Device '" + str(DeviceID) + "', Unit '" + str(Unit) + "': Parameter '" + str(Command) + "', Level: " + str(Level))
        if Unit == self.batStrategyUnit:
            strat = PowerStrategy("")
            strat.state = Level/10
            if DeviceID == self.system_name: #if it's the system device, send update to all
                for battery in self.devices_dict:
                    logging.debug( "commanding battery: '" +battery+"' with strategy '"+str(strat)+"'")
                    self.devices_dict[battery].setStrategy(str(strat))
            else:
                logging.debug( "commanding battery: '" +DeviceID+"' with strategy '"+str(strat)+"'")
                self.devices_dict[DeviceID].setStrategy(str(strat))
        if Unit == self.batPowerSetpointUnit:
            if DeviceID == self.system_name: #if it's the system device, send update to all
                setpoint = Level/len(self.devices_dict) #average out the total setpoint over individul batteries
                for battery in self.devices_dict:
                    logging.debug( "commanding battery: '" +battery+"' with setpoint '"+str(Level)+"'")
                    self.devices_dict[battery].setPowerSetpoint(setpoint)
            else:
                logging.debug( "commanding battery: '" +DeviceID+"' with setpoint '"+str(Level)+"'")
                self.devices_dict[DeviceID].setPowerSetpoint(Level)
        self.runCounter = 1 # force update second next heartbeat to allow a bit of time to react
        self.onHeartbeat()
        
    def onStop(self):
        logging.info("stopping plugin")

    def get_device_names(self, configmap):
        """find the amount of stored devices"""
        devices = {}
        for x in configmap["p1meter"]:
            devices[str(x["name"])] = "p1meter"
        for x in configmap["batteries"]:
            devices[str(x["name"])] = "battery"
        logging.debug("get_device_names, list of configured devices: " + str(devices))
        return devices

    def createBatteryUnits(self, deviceId):
        #check, per device, if it has units. If not,create them 
        logging.debug("Creating units for: '" + deviceId +"'")
        if deviceId not in Devices or (self.batPercentageUnit not in Devices[deviceId].Units):
            Domoticz.Unit(Name=deviceId + ' - Battery percentage', Unit=self.batPercentageUnit, TypeName="General", Subtype=6, Used=1, DeviceID=deviceId).Create()
        if deviceId not in Devices or (self.batEnergyDeliveredUnit not in Devices[deviceId].Units):
            Domoticz.Unit(Name=deviceId + " - Battery delivered power", Unit=self.batEnergyDeliveredUnit, Type=243, Subtype=29, Switchtype=4, Used=1, DeviceID=deviceId).Create()
        if deviceId not in Devices or (self.batEnergyStoredUnit not in Devices[deviceId].Units):
            Domoticz.Unit(Name=deviceId + " - Battery stored power", Unit=self.batEnergyStoredUnit, Type=243, Subtype=29, DeviceID=deviceId).Create()
        if deviceId not in Devices or (self.batBatteryGeneralStateUnit not in Devices[deviceId].Units):
            Domoticz.Unit(Name=deviceId + ' - Battery general state', Unit=self.batBatteryGeneralStateUnit, TypeName="General", Subtype=19, DeviceID=deviceId).Create()
        if deviceId not in Devices or (self.batBatteryDetailedStateUnit not in Devices[deviceId].Units):
            Domoticz.Unit(Name=deviceId + ' - Battery detailed state', Unit=self.batBatteryDetailedStateUnit, TypeName="General", Subtype=19, DeviceID=deviceId).Create()
        if deviceId not in Devices or (self.batPowerUnit not in Devices[deviceId].Units):
            Domoticz.Unit(Name=deviceId + ' - Battery in/output power', Unit=self.batPowerUnit, Type=250, Subtype=1, DeviceID=deviceId).Create()
        if deviceId not in Devices or (self.batPhase1VoltageUnit not in Devices[deviceId].Units):
            Domoticz.Unit(Name=deviceId + ' - Battery voltage L1', DeviceID=deviceId, Unit=(self.batPhase1VoltageUnit), Type=243, Subtype=8).Create()
        if deviceId not in Devices or (self.batPhase1CurrentUnit not in Devices[deviceId].Units):
            Domoticz.Unit(Name=deviceId + ' - Battery current L1', DeviceID=deviceId, Unit=(self.batPhase1CurrentUnit), Type=243, Subtype=23).Create()
        if deviceId not in Devices or (self.batPhase2VoltageUnit not in Devices[deviceId].Units):
            Domoticz.Unit(Name=deviceId + ' - Battery voltage L2', DeviceID=deviceId, Unit=(self.batPhase2VoltageUnit), Type=243, Subtype=8).Create()
        if deviceId not in Devices or (self.batPhase2CurrentUnit not in Devices[deviceId].Units):
            Domoticz.Unit(Name=deviceId + ' - Battery current L2', DeviceID=deviceId, Unit=(self.batPhase2CurrentUnit), Type=243, Subtype=23).Create()
        if deviceId not in Devices or (self.batPhase3VoltageUnit not in Devices[deviceId].Units):
            Domoticz.Unit(Name=deviceId + ' - Battery voltage L3', DeviceID=deviceId, Unit=(self.batPhase3VoltageUnit), Type=243, Subtype=8).Create()
        if deviceId not in Devices or (self.batPhase3CurrentUnit not in Devices[deviceId].Units):
            Domoticz.Unit(Name=deviceId + ' - Battery current L3', DeviceID=deviceId, Unit=(self.batPhase3CurrentUnit), Type=243, Subtype=23).Create()
        if deviceId not in Devices or (self.batStrategyUnit not in Devices[deviceId].Units):
            Options = {"LevelActions" : "|||||",
                "LevelNames" : "|NoM|Dynamic|Open API|Off|Sessy Connect|Eco|Mixed/unknown",
                "LevelOffHidden" : "true",
                "SelectorStyle" : "1"}
            Domoticz.Unit(Name=deviceId + ' - Power strategy', DeviceID=deviceId, Unit=self.batStrategyUnit, TypeName="Selector Switch", Options=Options).Create()
        if deviceId not in Devices or (self.batPowerSetpointUnit not in Devices[deviceId].Units):
            Options = {'ValueStep':'100', 'ValueMin':str(self.minPower), 'ValueMax':str(self.maxPower), 'ValueUnit':'W'}
            Options = {'ValueStep':'100', 'ValueMin':'-2200', 'ValueMax':'2200', 'ValueUnit':'W'}
            Domoticz.Unit(Name=deviceId + ' - Battery power setpoint', Unit=self.batPowerSetpointUnit, Type=242, Subtype=1, Options=Options, DeviceID=deviceId).Create()
        if deviceId not in Devices or (self.batErrorWarning not in Devices[deviceId].Units):
            Domoticz.Unit(Name=deviceId + ' - Battery error/warning', Unit=self.batErrorWarning, TypeName="Text", Image=7, DeviceID=deviceId).Create()
        if deviceId not in Devices or (self.batStrategyOverridden not in Devices[deviceId].Units):
            Domoticz.Unit(Name=deviceId + ' - Battery strategy overridden', Unit=self.batStrategyOverridden, TypeName="Switch", DeviceID=deviceId).Create()

    def updatePowerStrategy(self, deviceId, data):
        if deviceId == self.system_name:
            powerStrat = self.powerStrat // len(self.devices_dict)
            remainder = self.powerStrat % len(self.devices_dict)
            # TODO need a proper fix to find if all devices have the same mode
            logging.debug("input: self.powerStrat = "+str(self.powerStrat) + " num devs: "+str(len(self.devices_dict))+" calculated strategy = "+str(powerStrat) + " and remainder "+str(remainder))
            if remainder == 0:
                UpdateDevice(deviceId, self.batStrategyUnit, powerStrat, str(powerStrat*10))
            else:
                UpdateDevice(deviceId, self.batStrategyUnit, 70, str(70))
            self.powerStrat = 0
        else:
            powerStrat = PowerStrategy(data["strategy"])
            self.powerStrat += powerStrat.state
            UpdateDevice(deviceId, self.batStrategyUnit, powerStrat.state, str(powerStrat.state*10))
        return

    def updateBatteryUnits(self, deviceId, powerData, energyData):
        logging.debug("Updating units for: '" + deviceId +"'")
        if "sessy" in powerData:
            if "state_of_charge" in powerData["sessy"]:
                #battery state of charge. Percentage with high number of decimals, needs to be trimmed
                perc = round(powerData["sessy"]["state_of_charge"]*100,1)
                self.systemPercent += perc
                logging.debug(f"self.systemPercent = {self.systemPercent}, perc = {perc}" )
                UpdateDevice(deviceId, self.batPercentageUnit, perc, str(perc))
            if "power" in powerData["sessy"] and "sessy_energy" in energyData:
                #power going in (negative) or out (positive) of the battery
                power = round(powerData["sessy"]["power"],1) * -1 #domoticz wants it the other way around, apparantly.....
                consPower = abs(power) if power < 0 else 0 # negative power is going into battery
                prodPower = abs(power) if power > 0 else 0 # positive power is going out of battery
                self.systemPower += power
                RETURN1 = energyData["sessy_energy"]["export_wh"]
                USAGE1 = energyData["sessy_energy"]["import_wh"]
                RETURN2 ="0"
                USAGE2 ="0"
                self.systemPowerDelivered += prodPower
                self.systemPowerStored += consPower
                self.systemEnergyDelivered += RETURN1
                self.systemEnergyStored += USAGE1
                UpdateDevice(deviceId, self.batEnergyDeliveredUnit, 0, str(prodPower)+";"+str(RETURN1)) 
                UpdateDevice(deviceId, self.batEnergyStoredUnit, 0, str(consPower)+";"+str(USAGE1)) 
                powerString = str(USAGE1)+";"+USAGE2+";"+str(RETURN1)+";"+RETURN2+";"+str(consPower)+";"+str(prodPower)
                #logging.debug("Powerstring = " + powerString)
                UpdateDevice(deviceId, self.batPowerUnit, 0, powerString)
            if "power_setpoint" in powerData["sessy"]:
                powerSetpoint = powerData["sessy"]["power_setpoint"]
                self.powerSetpoint += powerSetpoint
                UpdateDevice(deviceId, self.batPowerSetpointUnit, powerSetpoint, str(powerSetpoint))
            if "system_state" in powerData["sessy"]:
                UpdateDevice(deviceId, self.batBatteryGeneralStateUnit, 1, str(powerData["sessy"]["system_state"]))
            if "system_state_details" in powerData["sessy"]:
                UpdateDevice(deviceId, self.batBatteryDetailedStateUnit, 1, str(powerData["sessy"]["system_state_details"]))
            else:
                UpdateDevice(deviceId, self.batBatteryDetailedStateUnit, 1, "all ok")
            if "strategy_overridden" in powerData["sessy"]:
                state = SwitchMode(str(powerData["sessy"]["strategy_overridden"]))
                UpdateDevice(deviceId, self.batStrategyOverridden, state.state, str(state))
        if "renewable_energy_phase1" in powerData:
            if "voltage_rms" in powerData["renewable_energy_phase1"]:
                UpdateDevice(deviceId, self.batPhase1VoltageUnit, 0, str(round(powerData["renewable_energy_phase1"]["voltage_rms"]/1000,0)))
            if "current_rms" in powerData["renewable_energy_phase1"]:
                UpdateDevice(deviceId, self.batPhase1CurrentUnit, 0, str(round(powerData["renewable_energy_phase1"]["current_rms"]/1000,1)))
        if "renewable_energy_phase2" in powerData:
            if "voltage_rms" in powerData["renewable_energy_phase2"]:
                UpdateDevice(deviceId, self.batPhase2VoltageUnit, 0, str(round(powerData["renewable_energy_phase2"]["voltage_rms"]/1000,0)))
            if "current_rms" in powerData["renewable_energy_phase1"]:
                UpdateDevice(deviceId, self.batPhase2CurrentUnit, 0, str(round(powerData["renewable_energy_phase2"]["current_rms"]/1000,0)))
        if "renewable_energy_phase3" in powerData:
            if "voltage_rms" in powerData["renewable_energy_phase3"]:
                UpdateDevice(deviceId, self.batPhase3VoltageUnit, 0, str(round(powerData["renewable_energy_phase3"]["voltage_rms"]/1000,0)))
            if "current_rms" in powerData["renewable_energy_phase3"]:
                UpdateDevice(deviceId, self.batPhase3CurrentUnit, 0, str(round(powerData["renewable_energy_phase3"]["current_rms"]/1000,1)))
                
        return

    def createSystemUnits(self, deviceId):
        #check, per device, if it has units. If not,create them 
        logging.debug("Creating units for: '" + deviceId +"'")
        if deviceId not in Devices or (self.batPercentageUnit not in Devices[deviceId].Units):
            Domoticz.Unit(Name=deviceId + ' - Battery percentage', Unit=self.batPercentageUnit, TypeName="General", Subtype=6, Used=1, DeviceID=deviceId).Create()
        if deviceId not in Devices or (self.batEnergyUnit not in Devices[deviceId].Units):
            Domoticz.Unit(Name=deviceId + ' - Battery energy', Unit=self.batEnergyUnit, Type=243, Subtype=29,  Used=1, DeviceID=deviceId).Create()
        if deviceId not in Devices or (self.batPowerUnit not in Devices[deviceId].Units):
            Domoticz.Unit(Name=deviceId + ' - Battery in/output power', Unit=self.batPowerUnit, Type=250, Subtype=1, Used=1, DeviceID=deviceId).Create()
        if deviceId not in Devices or (self.batStrategyUnit not in Devices[deviceId].Units):
            Options = {"LevelActions" : "|||||",
                "LevelNames" : "|NoM|Dynamic|Open API|Off|Sessy Connect|Eco|Mixed/unknown",
                "LevelOffHidden" : "true",
                "SelectorStyle" : "1"}
            Domoticz.Unit(Name=deviceId + ' - Power strategy', DeviceID=deviceId, Unit=self.batStrategyUnit, TypeName="Selector Switch", Options=Options).Create()
        if deviceId not in Devices or (self.batPowerSetpointUnit not in Devices[deviceId].Units):
            Options = {'ValueStep':'100', 'ValueMin':str(-1 * self.maxPower * len(self.devices_dict)), 'ValueMax':str(self.maxPower * len(self.devices_dict)), 'ValueUnit':'W'}
            #Options = {'ValueStep':'100', 'ValueMin':'-2200', 'ValueMax':'4400', 'ValueUnit':'W'}
            logging.debug("options to create power setpoint: "+ str(Options))
            Domoticz.Unit(Name=deviceId + ' - Battery power setpoint', Unit=self.batPowerSetpointUnit, Type=242, Subtype=1, Options=Options, DeviceID=deviceId).Create()

    def updateSystemUnits(self, deviceId, numBatteries):
        logging.debug("Updating units for: '" + deviceId +"'")
        # overall SoC %
        perc = round(self.systemPercent / numBatteries, 1)
        logging.debug(f"perc: = {perc}, self.systemPercent={self.systemPercent}, numBatteries={numBatteries}")
        UpdateDevice(deviceId, self.batPercentageUnit, perc, str(perc))
        # update P1 meter
        USAGE1 = self.systemEnergyStored
        USAGE2 = 0
        RETURN1 = self.systemEnergyDelivered
        RETURN2 = 0
        CONS = self.systemPowerStored
        PROD = self.systemPowerDelivered
        powerString = str(USAGE1) +";"+ str(USAGE2) +";"+ str(RETURN1) +";"+ str(RETURN2) +";"+ str(CONS) + ";"+ str(PROD) #+";"+ datetime.now().strftime(dt_format)
        #logging.debug("compiled powerString: "+powerString)
        UpdateDevice(deviceId, self.batPowerUnit, 0, powerString)
        #update energy device
        newCounter = calculateNewEnergy(deviceId, self.batEnergyUnit, self.systemPower)
        powerString = str(self.systemPower)+";" + str(newCounter)
        UpdateDevice(deviceId, self.batEnergyUnit, 0, powerString)
        
        UpdateDevice(deviceId, self.batPowerSetpointUnit, self.powerSetpoint, str(self.powerSetpoint))
        
        # reset variables used to sum up values from individual batteries
        self.systemPercent = 0
        self.systemPower = 0
        self.systemPowerDelivered = 0
        self.systemPowerStored = 0
        self.systemEnergyDelivered = 0
        self.systemEnergyStored = 0
        self.powerSetpoint = 0
        

    def createP1Units(self, deviceId):
        #check, per device, if it has units. If not,create them 
        logging.debug("Creating units for: '" + deviceId +"'")
        if deviceId not in Devices or (self.p1TarifUnit not in Devices[deviceId].Units):
            Domoticz.Unit(Name=deviceId + ' - Tarif', Unit=self.p1TarifUnit, TypeName="General", Subtype=19, Used=1, DeviceID=deviceId).Create()

    def updateP1Units(self, deviceId, data):
        logging.debug("Updating units for: '" + deviceId +"'")
        if "tariff_indicator" in data:
            #1 is low tarif, 2 is high tarif
            UpdateDevice(deviceId, self.p1TarifUnit, 1, str(data["tariff_indicator"]))

class SessyBase():
    def __init__(self, config):
        logging.debug("init Sessy device: " + str(config))
        self.__name = config["name"]
        self.ip = config["ip"]
        self.user = config["user"]
        self.pwd = config["pwd"]
        self.base_url = 'http://'+ self.user + ':' + self.pwd + '@' + self.ip 

    @property
    def name(self):
        return self.__name

    def GetDataFromDevice(self, api):
        logging.debug("get data from: " + self.base_url + api)
        response = requests.get(self.base_url + api, timeout=6)
        if response.status_code != 200:
            logging.error("error during GET: status code"+str(response.status_code)+", status: "+response.json()['status']+", error: "+response.json()['error'])
            raise exceptions.RequestError(response.status_code, response.json()['error'])
        return response.json()

    def PostDataToDevice(self, api, json):
        logging.debug("post data to: " + self.base_url + api)
        response = requests.post(self.base_url + api, json = json)
        return response

class SessyBattery(SessyBase):
    dynamicScheduleAPI = '/api/v1/dynamic/schedule'
    #dynamicScheduleAPI = '/api/v1/energy/status'
    energyAPI = '/api/v1/energy/status'
    powerAPI = '/api/v1/power/status'
    strategyAPI = '/api/v1/power/active_strategy'
    powerSetpointAPI = '/api/v1/power/setpoint'

    def getDynamicSchedule(self):
        dt_format = "%Y-%m-%d"
        data = self.GetDataFromDevice(self.dynamicScheduleAPI)
        logging.debug("dynamic scheule for '" + str(SessyBase.name) + "': '"+str(data))
        if "power_strategy" not in data or len(data["power_strategy"]) < 1:
            raise exceptions.ScheduleError("power strategy", datetime.now().strftime(dt_format))
        if "energy_prices" not in data or len(data["energy_prices"]) < 1:
            raise exceptions.ScheduleError("energy prices", datetime.now().strftime(dt_format))
        return data

    def getEnergyStatus(self):
        data = self.GetDataFromDevice(self.energyAPI)
        logging.debug("energy status for '" + str(SessyBase.name) + "': '"+str(data))
        return data

    def getPowerStatus(self):
        data = self.GetDataFromDevice(self.powerAPI)
        logging.debug("power status for '" + str(SessyBase.name) + "': '"+str(data))
        return data

    def setPowerSetpoint(self, setpoint):
        body = {"setpoint":setpoint}
        data = self.PostDataToDevice(self.powerSetpointAPI, body)
        logging.debug("power setpoint for '" + str(SessyBase.name) + "': '"+str(data))
        if data.status_code != 200:
            raise exceptions.RequestError(data.status_code, data.json()['error'])
        return data

    def getPowerStrategy(self):
        data = self.GetDataFromDevice(self.strategyAPI)
        logging.debug("power strategy for '" + str(SessyBase.name) + "': '"+str(data))
        return data

    def setStrategy(self, strategy):
        body = {"strategy":strategy}
        data = self.PostDataToDevice(self.strategyAPI, body)
        logging.debug("power strategy for '" + str(SessyBase.name) + "': '"+str(data))
        return data

class SessyP1(SessyBase):
    detailsAPI = '/api/v2/p1/details'
    #self.data = None

    def getDetails(self):
        self.data = self.GetDataFromDevice(self.detailsAPI)
        logging.debug("p1 status for '" + str(SessyBase.name) + "': '"+str(self.data))
        return self.data

    @property
    def tarif(self):
        return self.data["tariff_indicator"]

class PowerStrategy():
    """enum for power strategy"""
    
    NOM = 'POWER_STRATEGY_NOM' # zero on the meter
    ROI = 'POWER_STRATEGY_ROI' # dynamic
    API = 'POWER_STRATEGY_API' # open
    IDLE = 'POWER_STRATEGY_IDLE' # off
    SESSY = 'POWER_STRATEGY_SESSY_CONNECT' # sessy connect
    ECO = 'POWER_STRATEGY_ECO' # eco
    MIXED = 'MIXED' # unknown or not all sessys same state
    _state = None
    
    def __init__(self, state):
        """go from string to state object"""
        if state.upper() == 'POWER_STRATEGY_NOM': self._state = self.NOM
        if state.upper() == 'POWER_STRATEGY_ROI': self._state = self.ROI
        if state.upper() == 'POWER_STRATEGY_API': self._state = self.API
        if state.upper() == 'POWER_STRATEGY_IDLE': self._state = self.IDLE
        if state.upper() == 'POWER_STRATEGY_SESSY_CONNECT': self._state = self.SESSY
        if state.upper() == 'POWER_STRATEGY_ECO': self._state = self.ECO
        if state.upper() == '': self._state = self.MIXED
    
    def __repr__(self):
        return self._state
        
    @property
    def state(self):
        if self._state == self.NOM: return 1
        if self._state == self.ROI: return 2
        if self._state == self.API: return 3
        if self._state == self.IDLE: return 4
        if self._state == self.SESSY: return 5
        if self._state == self.ECO: return 6
        if self._state == self.MIXED: return 7

    @state.setter
    def state(self, stateNum):
        if stateNum == 7 : self._state = self.MIXED
        if stateNum == 1 : self._state = self.NOM
        if stateNum == 2 : self._state = self.ROI
        if stateNum == 3 : self._state = self.API
        if stateNum == 4 : self._state = self.IDLE
        if stateNum == 5 : self._state = self.SESSY
        if stateNum == 6 : self._state = self.ECO

class SwitchMode():
    """Enum for switches"""
    OFF = 'Off'
    ON = 'On'
    _state = None
    
    def __init__(self, state):
        """go from string to state object"""
        if state.upper() == 'FALSE': self._state = self.OFF
        if state.upper() == 'TRU': self._state = self.ON
    
    def __repr__(self):
        return self._state
        
    @property
    def state(self):
        if self._state == self.OFF: return 0
        if self._state == self.ON: return 1

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

# def onDeviceRemoved(DeviceID, Unit):
    # global _plugin
    # _plugin.onDeviceRemoved(DeviceID, Unit)
       
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
                Domoticz.Debug("Updating device '"+Devices[Device].Units[Unit].Name+ "' with current sValue '"+Devices[Device].Units[Unit].sValue+"' to '" +sValue+"'")
                logging.debug("Updating device '"+Devices[Device].Units[Unit].Name+ "' with current sValue '"+Devices[Device].Units[Unit].sValue+"' to '" +sValue+"'")
            #try:
                if isinstance(nValue, int):
                    Devices[Device].Units[Unit].nValue = nValue
                else:
                    Domoticz.Log("nValue supplied is not an integer. Device: "+str(Device)+ " unit "+str(Unit)+" nValue "+str(nValue))
                    Devices[Device].Units[Unit].nValue = int(nValue)
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

def calculateNewEnergy(Device, Unit, inputPower):
    #helper method to get current energy level from device and create new value based on input power
    try:
        #read power currently on display (comes from previous update) in Watt and energy counter uptill now in Wh
        previousPower,currentCount = Devices[Device].Units[Unit].sValue.split(";") 
    except:
        #in case no values there, just assume zero
        previousPower = 0 #Watt
        currentCount = 0 #Wh
    dt_format = "%Y-%m-%d %H:%M:%S"
    try:
        dt_string = Devices[Device].Units[Unit].LastUpdate
    except:
        dt_string = datetime.now().strftime(dt_format)
    if len(dt_string) > 0:
        lastUpdateDT = datetime.fromtimestamp(time.mktime(time.strptime(dt_string, dt_format)))
    else:
        lastUpdateDT = datetime.now()
    elapsedTime = datetime.now() - lastUpdateDT
    #logging.debug("Test power, previousPower: {}, last update: {:%Y-%m-%d %H:%M}, elapsedTime: {}, elapsedSeconds: {:6.2f}".format(previousPower, lastUpdateDT, elapsedTime, elapsedTime.total_seconds()))
    
    #average current and previous power (Watt) and multiply by elapsed time (hour) to get Watt hour
    previousPower = str(previousPower).replace("w","").replace("W","")
    newCount = round(((float(previousPower) + inputPower ) / 2) * elapsedTime.total_seconds()/3600,2)
    newCounter = newCount + float(currentCount) #add the amount of energy since last update to the already logged energy
    #logging.debug("Test power, previousPower: {}, currentCount: {:6.2f}, newCounter: {:6.2f}, added: {:6.2f}".format(previousPower, float(currentCount), newCounter, newCount))
    return newCounter
