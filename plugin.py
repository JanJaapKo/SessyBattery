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
<plugin key="SessyBattery" name="Sessy battery" author="Jan-Jaap Kostelijk" version="1.0.1" externallink="https://github.com/JanJaapKo/SessyBattery">
    <description>
        <h2>Sessy Battery plugin</h2><br/>
        Connects to Sessy batteries and P1 dongle.
        <h2>Configuration</h2>
        Configuration of the plugin is a 2 step action: the plugin here in Domoticz and a json file in the plugin directory.<br/><br/>
        IMPORTANT: remove the pwd from the json file after first start, the plugin will move it to the Domoticz configuration and encrypt it there. If you don't do this, your password will be stored in plaintext in the json file.<br/><br/>
        
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
import os
import re
from datetime import datetime, timedelta
import exceptions

# Optional encryption support (Fernet symmetric encryption)
try:
    from cryptography.fernet import Fernet, InvalidToken
    _HAS_CRYPTO = True
except ImportError:
    # cryptography not installed; fall back to plaintext password usage
    try:
        Domoticz.Error("python-cryptography not installed: passwords will be used in plaintext. Install python3-cryptography to enable encryption.")
        logging.error("python-cryptography not installed: passwords will be used in plaintext. Install python3-cryptography to enable encryption.")
    except Exception:
        pass
    Fernet = None
    InvalidToken = Exception
    _HAS_CRYPTO = False

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
    # 25: sensor type '?', 'Error/warning'
    batErrorWarning = 25
    # 26: sensor type 'switch', 
    batStrategyOverridden = 26
    # 27: sensor type 'Electric (Instant+Counter)', 'P1 energy'
    p1EnergyUnit = 27
    # 28: sensor type 'Usage (Electric)', 'P1 total power'
    p1PowerTotalUnit = 28
    # 29: sensor type 'Usage (Electric)', 'P1 power consumed'
    p1PowerConsumedUnit = 29
    # 30: sensor type 'Usage (Electric)', 'P1 power produced'
    p1PowerProducedUnit = 30
    # 31: sensor type 'Text', 'P1 DSMR version'
    p1DsmrVersionUnit = 31
    # 32: sensor type 'Text', 'P1 equipment identifier'
    p1EquipmentIdentifierUnit = 32
    # 33: sensor type 'Text', 'P1 timestamp'
    p1DateTimeUnit = 33
    # 34: sensor type 'Voltage', 'P1 voltage L1'
    p1VoltageL1Unit = 34
    # 35: sensor type 'Voltage', 'P1 voltage L2'
    p1VoltageL2Unit = 35
    # 36: sensor type 'Voltage', 'P1 voltage L3'
    p1VoltageL3Unit = 36
    # 37: sensor type 'Ampere (1 Phase)', 'P1 current L1'
    p1CurrentL1Unit = 37
    # 38: sensor type 'Ampere (1 Phase)', 'P1 current L2'
    p1CurrentL2Unit = 38
    # 39: sensor type 'Ampere (1 Phase)', 'P1 current L3'
    p1CurrentL3Unit = 39
    # 40: sensor type 'Usage (Electric)', 'P1 power consumed L1'
    p1PowerConsumedL1Unit = 40
    # 41: sensor type 'Usage (Electric)', 'P1 power consumed L2'
    p1PowerConsumedL2Unit = 41
    # 42: sensor type 'Usage (Electric)', 'P1 power consumed L3'
    p1PowerConsumedL3Unit = 42
    # 43: sensor type 'Usage (Electric)', 'P1 power produced L1'
    p1PowerProducedL1Unit = 43
    # 44: sensor type 'Usage (Electric)', 'P1 power produced L2'
    p1PowerProducedL2Unit = 44
    # 45: sensor type 'Usage (Electric)', 'P1 power produced L3'
    p1PowerProducedL3Unit = 45
    # 46: sensor type 'Text', 'P1 power failures'
    p1PowerFailureUnit = 46
    # 47: sensor type 'Text', 'P1 long power failures'
    p1LongPowerFailureUnit = 47
    # 48: sensor type 'Text', 'P1 voltage sag L1'
    p1VoltageSagL1Unit = 48
    # 49: sensor type 'Text', 'P1 voltage sag L2'
    p1VoltageSagL2Unit = 49
    # 50: sensor type 'Text', 'P1 voltage sag L3'
    p1VoltageSagL3Unit = 50
    # 51: sensor type 'Text', 'P1 voltage swell L1'
    p1VoltageSwellL1Unit = 51
    # 52: sensor type 'Text', 'P1 voltage swell L2'
    p1VoltageSwellL2Unit = 52
    # 53: sensor type 'Text', 'P1 voltage swell L3'
    p1VoltageSwellL3Unit = 53
    # 54: sensor type 'Text', 'P1 gas meter value'
    p1GasMeterUnit = 54
    # 55: sensor type 'Text', 'P1 gas meter timestamp'
    p1GasMeterTimeUnit = 55

    runCounter = 6
    p1Counter = P1_FACTOR
    system_name  = "Sessy system"

    def _get_password_config_key(self, config):
        """Return a stable Domoticz configuration key for storing an encrypted password."""
        name = str(config.get("name", "")).strip().lower()
        ip = str(config.get("ip", "")).strip()
        key = f"sessy_pwd_{name}_{ip}"
        key = re.sub(r'[^a-z0-9_]', '_', key)
        return key

    def _init_encryption(self):
        """Initialize Fernet encryption using a key file in the plugin folder."""
        self._fernet = None
        if not _HAS_CRYPTO:
            Domoticz.Log("Cryptography library not available, passwords will be used in plaintext.")
            logging.info("Cryptography library not available, passwords will be used in plaintext.")
            return

        key_path = os.path.join(Parameters.get('HomeFolder', ''), 'sessy_fernet.key')
        try:
            if os.path.exists(key_path):
                with open(key_path, 'rb') as f:
                    key = f.read()
            else:
                key = Fernet.generate_key()
                with open(key_path, 'wb') as f:
                    f.write(key)
            self._fernet = Fernet(key)
        except Exception as e:
            Domoticz.Error("Failed to initialize encryption key: " + str(e))
            logging.error("Failed to initialize encryption key: " + str(e))
            self._fernet = None

    def _encrypt_password(self, plaintext):
        if not self._fernet:
            raise RuntimeError("Encryption not initialized")
        return self._fernet.encrypt(plaintext.encode('utf-8')).decode('utf-8')

    def _decrypt_password(self, token):
        if not self._fernet:
            raise RuntimeError("Encryption not initialized")
        if isinstance(token, str):
            token = token.encode('utf-8')
        return self._fernet.decrypt(token).decode('utf-8')

    def _get_password_from_config(self, config):
        """Return password, using Domoticz configuration storage to keep it encrypted."""
        pwd = config.get("pwd", "")

        key = self._get_password_config_key(config)
        stored = None
        try:
            stored = getConfigItem(key, Default=None)
        except Exception:
            stored = None

        if stored and isinstance(stored, str):
            if self._fernet:
                try:
                    return self._decrypt_password(stored)
                except InvalidToken:
                    Domoticz.Error(f"Failed decrypting password for '{config.get('name')}' (invalid token). Using config file password.")
                    logging.error(f"Failed decrypting password for '{config.get('name')}' (invalid token). Using config file password.")
                except Exception as e:
                    Domoticz.Error(f"Failed decrypting password for '{config.get('name')}': {e}. Using config file password.")
                    logging.error(f"Failed decrypting password for '{config.get('name')}': {e}. Using config file password.")
            else:
                logging.debug("Encryption not available, using plaintext password from config file.")

        if self._fernet and pwd:
            try:
                enc = self._encrypt_password(pwd)
                setConfigItem(key, enc)
                Domoticz.Log(f"Encrypted password for '{config.get('name')}' stored in Domoticz configuration.")
                logging.info(f"Encrypted password for '{config.get('name')}' stored in Domoticz configuration.")
            except Exception as e:
                Domoticz.Error(f"Failed to encrypt/store password for '{config.get('name')}': {e}")
                logging.error(f"Failed to encrypt/store password for '{config.get('name')}': {e}")
        return pwd

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

        #logging.basicConfig(format='%(asctime)s - %(levelname)-8s - %(filename)-18s - %(message)s', filename=self.log_filename,level=logging.INFO)
        if self.log_level == 'Debug':
            logging.basicConfig(format='%(asctime)s - %(levelname)-8s - %(filename)-18s - %(message)s', filename=self.log_filename,level=logging.DEBUG)
            Domoticz.Debugging(2)
            DumpConfigToLog()
        elif self.log_level == 'Verbose':
            logging.basicConfig(format='%(asctime)s - %(levelname)-8s - %(filename)-18s - %(message)s', filename=self.log_filename,level=logging.DEBUG)
            Domoticz.Debugging(1+2+4+8+16+64)
            DumpConfigToLog()
        else:
            logging.basicConfig(format='%(asctime)s - %(levelname)-8s - %(filename)-18s - %(message)s', filename=self.log_filename,level=logging.INFO)

        Domoticz.Log("Starting Sessy Battery plugin version "+Parameters["Version"]+", logging to file {0}".format(self.log_filename))
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

        # Initialize encryption and migrate plaintext passwords into Domoticz configuration
        self._init_encryption()
        for entry in config_map.get("p1meter", []):
            entry["pwd"] = self._get_password_from_config(entry)
        for entry in config_map.get("batteries", []):
            entry["pwd"] = self._get_password_from_config(entry)

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
        found_devices = []
        for battery in config_map["batteries"]:
            try:
                # Try to create and contact the device
                device = SessyBattery(battery)
                # Try a simple status call to check if reachable
                device.getPowerStatus()
                self.devices_dict[battery["name"]] = device
                found_devices.append(battery["name"])
                self.createBatteryUnits(battery["name"])
                data = self.devices_dict[battery["name"]].getPowerStatus()
                logging.debug("initial data query power status '" + battery["name"] + "': " + str(data))
                energy = self.devices_dict[battery["name"]].getEnergyStatus()
                self.updateBatteryUnits(battery["name"], data, energy)
                logging.debug("initial data query energy status '" + battery["name"] + "': " + str(energy))
                self.updatePowerStrategy(battery["name"], self.devices_dict[battery["name"]].getPowerStrategy())
            except Exception as e:
                logging.warning(f"Device '{battery['name']}' not found or unreachable: {e}")
                Domoticz.Log(f"Device '{battery['name']}' not found or unreachable: {e}")

        expected = len(config_map["batteries"])
        found = len(found_devices)
        logging.info(f"Found {found} out of {expected} batteries: {found_devices}")
        Domoticz.Log(f"Found {found} out of {expected} batteries: {found_devices}")
        
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
        logging.info("onCommand called for Device '" + str(DeviceID) + "', Unit '" + str(Unit) + "': Parameter '" + str(Command) + "', Level: " + str(Level))
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
                    try:
                        self.devices_dict[battery].setPowerSetpoint(setpoint)
                    except exceptions.RequestError as e:
                        logging.error(f"an error occured while commanding {battery}: {e}")
                        Domoticz.Error(f"an error occured while commanding {battery}: {e}")
            else:
                logging.debug( "commanding battery: '" +DeviceID+"' with setpoint '"+str(Level)+"'")
                try:
                    self.devices_dict[DeviceID].setPowerSetpoint(Level)
                except exceptions.RequestError as e:
                    logging.error(f"an error occured while commanding {DeviceID}: {e}")
                    Domoticz.Error(f"an error occured while commanding {DeviceID}: {e}")
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
            Domoticz.Unit(Name=deviceId + ' - Tariff indicator', Unit=self.p1TarifUnit, TypeName="General", Subtype=19, Used=0, DeviceID=deviceId).Create()
        if deviceId not in Devices or (self.p1EnergyUnit not in Devices[deviceId].Units):
            Domoticz.Unit(Name=deviceId + ' - Energy counters', Unit=self.p1EnergyUnit, Type=243, Subtype=29, Used=1, DeviceID=deviceId).Create()
        if deviceId not in Devices or (self.p1PowerTotalUnit not in Devices[deviceId].Units):
            Domoticz.Unit(Name=deviceId + ' - Total power', Unit=self.p1PowerTotalUnit, Type=250, Subtype=1, Used=1, DeviceID=deviceId).Create()
        if deviceId not in Devices or (self.p1PowerConsumedUnit not in Devices[deviceId].Units):
            Domoticz.Unit(Name=deviceId + ' - Power consumed', Unit=self.p1PowerConsumedUnit, Type=250, Subtype=1, Used=0, DeviceID=deviceId).Create()
        if deviceId not in Devices or (self.p1PowerProducedUnit not in Devices[deviceId].Units):
            Domoticz.Unit(Name=deviceId + ' - Power produced', Unit=self.p1PowerProducedUnit, Type=250, Subtype=1, Used=0, DeviceID=deviceId).Create()
        if deviceId not in Devices or (self.p1MeterStateUnit not in Devices[deviceId].Units):
            Domoticz.Unit(Name=deviceId + ' - Meter state', Unit=self.p1MeterStateUnit, TypeName="General", Subtype=19, Used=0, DeviceID=deviceId).Create()
        if deviceId not in Devices or (self.p1DsmrVersionUnit not in Devices[deviceId].Units):
            Domoticz.Unit(Name=deviceId + ' - DSMR version', Unit=self.p1DsmrVersionUnit, TypeName="General", Subtype=19, Used=0, DeviceID=deviceId).Create()
        if deviceId not in Devices or (self.p1EquipmentIdentifierUnit not in Devices[deviceId].Units):
            Domoticz.Unit(Name=deviceId + ' - Equipment identifier', Unit=self.p1EquipmentIdentifierUnit, TypeName="General", Subtype=19, Used=0, DeviceID=deviceId).Create()
        if deviceId not in Devices or (self.p1DateTimeUnit not in Devices[deviceId].Units):
            Domoticz.Unit(Name=deviceId + ' - Latest timestamp', Unit=self.p1DateTimeUnit, TypeName="General", Subtype=19, Used=0, DeviceID=deviceId).Create()
        if deviceId not in Devices or (self.p1VoltageL1Unit not in Devices[deviceId].Units):
            Domoticz.Unit(Name=deviceId + ' - Voltage L1', Unit=self.p1VoltageL1Unit, Type=243, Subtype=8, Used=0, DeviceID=deviceId).Create()
        if deviceId not in Devices or (self.p1VoltageL2Unit not in Devices[deviceId].Units):
            Domoticz.Unit(Name=deviceId + ' - Voltage L2', Unit=self.p1VoltageL2Unit, Type=243, Subtype=8, Used=0, DeviceID=deviceId).Create()
        if deviceId not in Devices or (self.p1VoltageL3Unit not in Devices[deviceId].Units):
            Domoticz.Unit(Name=deviceId + ' - Voltage L3', Unit=self.p1VoltageL3Unit, Type=243, Subtype=8, Used=0, DeviceID=deviceId).Create()
        if deviceId not in Devices or (self.p1CurrentL1Unit not in Devices[deviceId].Units):
            Domoticz.Unit(Name=deviceId + ' - Current L1', Unit=self.p1CurrentL1Unit, Type=243, Subtype=23, Used=0, DeviceID=deviceId).Create()
        if deviceId not in Devices or (self.p1CurrentL2Unit not in Devices[deviceId].Units):
            Domoticz.Unit(Name=deviceId + ' - Current L2', Unit=self.p1CurrentL2Unit, Type=243, Subtype=23, Used=0, DeviceID=deviceId).Create()
        if deviceId not in Devices or (self.p1CurrentL3Unit not in Devices[deviceId].Units):
            Domoticz.Unit(Name=deviceId + ' - Current L3', Unit=self.p1CurrentL3Unit, Type=243, Subtype=23, Used=0, DeviceID=deviceId).Create()
        if deviceId not in Devices or (self.p1PowerConsumedL1Unit not in Devices[deviceId].Units):
            Domoticz.Unit(Name=deviceId + ' - Power consumed L1', Unit=self.p1PowerConsumedL1Unit, Type=250, Subtype=1, Used=0, DeviceID=deviceId).Create()
        if deviceId not in Devices or (self.p1PowerConsumedL2Unit not in Devices[deviceId].Units):
            Domoticz.Unit(Name=deviceId + ' - Power consumed L2', Unit=self.p1PowerConsumedL2Unit, Type=250, Subtype=1, Used=0, DeviceID=deviceId).Create()
        if deviceId not in Devices or (self.p1PowerConsumedL3Unit not in Devices[deviceId].Units):
            Domoticz.Unit(Name=deviceId + ' - Power consumed L3', Unit=self.p1PowerConsumedL3Unit, Type=250, Subtype=1, Used=0, DeviceID=deviceId).Create()
        if deviceId not in Devices or (self.p1PowerProducedL1Unit not in Devices[deviceId].Units):
            Domoticz.Unit(Name=deviceId + ' - Power produced L1', Unit=self.p1PowerProducedL1Unit, Type=250, Subtype=1, Used=0, DeviceID=deviceId).Create()
        if deviceId not in Devices or (self.p1PowerProducedL2Unit not in Devices[deviceId].Units):
            Domoticz.Unit(Name=deviceId + ' - Power produced L2', Unit=self.p1PowerProducedL2Unit, Type=250, Subtype=1, Used=0, DeviceID=deviceId).Create()
        if deviceId not in Devices or (self.p1PowerProducedL3Unit not in Devices[deviceId].Units):
            Domoticz.Unit(Name=deviceId + ' - Power produced L3', Unit=self.p1PowerProducedL3Unit, Type=250, Subtype=1, Used=0, DeviceID=deviceId).Create()
        if deviceId not in Devices or (self.p1PowerFailureUnit not in Devices[deviceId].Units):
            Domoticz.Unit(Name=deviceId + ' - Power failures', Unit=self.p1PowerFailureUnit, TypeName="General", Subtype=19, Used=0, DeviceID=deviceId).Create()
        if deviceId not in Devices or (self.p1LongPowerFailureUnit not in Devices[deviceId].Units):
            Domoticz.Unit(Name=deviceId + ' - Long power failures', Unit=self.p1LongPowerFailureUnit, TypeName="General", Subtype=19, Used=0, DeviceID=deviceId).Create()
        if deviceId not in Devices or (self.p1VoltageSagL1Unit not in Devices[deviceId].Units):
            Domoticz.Unit(Name=deviceId + ' - Voltage sag L1', Unit=self.p1VoltageSagL1Unit, TypeName="General", Subtype=19, Used=0, DeviceID=deviceId).Create()
        if deviceId not in Devices or (self.p1VoltageSagL2Unit not in Devices[deviceId].Units):
            Domoticz.Unit(Name=deviceId + ' - Voltage sag L2', Unit=self.p1VoltageSagL2Unit, TypeName="General", Subtype=19, Used=0, DeviceID=deviceId).Create()
        if deviceId not in Devices or (self.p1VoltageSagL3Unit not in Devices[deviceId].Units):
            Domoticz.Unit(Name=deviceId + ' - Voltage sag L3', Unit=self.p1VoltageSagL3Unit, TypeName="General", Subtype=19, Used=0, DeviceID=deviceId).Create()
        if deviceId not in Devices or (self.p1VoltageSwellL1Unit not in Devices[deviceId].Units):
            Domoticz.Unit(Name=deviceId + ' - Voltage swell L1', Unit=self.p1VoltageSwellL1Unit, TypeName="General", Subtype=19, Used=0, DeviceID=deviceId).Create()
        if deviceId not in Devices or (self.p1VoltageSwellL2Unit not in Devices[deviceId].Units):
            Domoticz.Unit(Name=deviceId + ' - Voltage swell L2', Unit=self.p1VoltageSwellL2Unit, TypeName="General", Subtype=19, Used=0, DeviceID=deviceId).Create()
        if deviceId not in Devices or (self.p1VoltageSwellL3Unit not in Devices[deviceId].Units):
            Domoticz.Unit(Name=deviceId + ' - Voltage swell L3', Unit=self.p1VoltageSwellL3Unit, TypeName="General", Subtype=19, Used=0, DeviceID=deviceId).Create()
        if deviceId not in Devices or (self.p1GasMeterUnit not in Devices[deviceId].Units):
            Domoticz.Unit(Name=deviceId + ' - Gas meter value', Unit=self.p1GasMeterUnit, TypeName="General", Subtype=19, Used=0, DeviceID=deviceId).Create()
        if deviceId not in Devices or (self.p1GasMeterTimeUnit not in Devices[deviceId].Units):
            Domoticz.Unit(Name=deviceId + ' - Gas meter timestamp', Unit=self.p1GasMeterTimeUnit, TypeName="General", Subtype=19, Used=0, DeviceID=deviceId).Create()

    def updateP1Units(self, deviceId, data):
        logging.debug("Updating units for: '" + deviceId +"'")
        if "tariff_indicator" in data:
            #1 is low tarif, 2 is high tarif
            UpdateDevice(deviceId, self.p1TarifUnit, 1, str(data["tariff_indicator"]))
        if "state" in data:
            UpdateDevice(deviceId, self.p1MeterStateUnit, 1, str(data["state"]))
        if "dsmr_version" in data:
            UpdateDevice(deviceId, self.p1DsmrVersionUnit, 1, str(data["dsmr_version"]))
        if "equipment_identifier" in data:
            UpdateDevice(deviceId, self.p1EquipmentIdentifierUnit, 1, str(data["equipment_identifier"]))
        if "date_time" in data:
            UpdateDevice(deviceId, self.p1DateTimeUnit, 1, str(data["date_time"]))
        if "power_total" in data:
            UpdateDevice(deviceId, self.p1PowerTotalUnit, 0, str(data["power_total"]))
        if "power_consumed" in data:
            UpdateDevice(deviceId, self.p1PowerConsumedUnit, 0, str(data["power_consumed"]))
        if "power_produced" in data:
            UpdateDevice(deviceId, self.p1PowerProducedUnit, 0, str(data["power_produced"]))
        if all(key in data for key in ["power_consumed_tariff1", "power_consumed_tariff2", "power_produced_tariff1", "power_produced_tariff2", "power_consumed", "power_produced"]):
            energyValue = ";".join([str(data["power_consumed_tariff1"]), str(data["power_consumed_tariff2"]), str(data["power_produced_tariff1"]), str(data["power_produced_tariff2"]), str(data["power_consumed"]), str(data["power_produced"])])
            UpdateDevice(deviceId, self.p1EnergyUnit, 0, energyValue)
        if "voltage_l1" in data:
            UpdateDevice(deviceId, self.p1VoltageL1Unit, 0, str(round(data["voltage_l1"]/1000, 1)))
        if "voltage_l2" in data:
            UpdateDevice(deviceId, self.p1VoltageL2Unit, 0, str(round(data["voltage_l2"]/1000, 1)))
        if "voltage_l3" in data:
            UpdateDevice(deviceId, self.p1VoltageL3Unit, 0, str(round(data["voltage_l3"]/1000, 1)))
        if "current_l1" in data:
            UpdateDevice(deviceId, self.p1CurrentL1Unit, 0, str(round(data["current_l1"]/1000, 3)))
        if "current_l2" in data:
            UpdateDevice(deviceId, self.p1CurrentL2Unit, 0, str(round(data["current_l2"]/1000, 3)))
        if "current_l3" in data:
            UpdateDevice(deviceId, self.p1CurrentL3Unit, 0, str(round(data["current_l3"]/1000, 3)))
        if "power_consumed_l1" in data:
            UpdateDevice(deviceId, self.p1PowerConsumedL1Unit, 0, str(data["power_consumed_l1"]))
        if "power_consumed_l2" in data:
            UpdateDevice(deviceId, self.p1PowerConsumedL2Unit, 0, str(data["power_consumed_l2"]))
        if "power_consumed_l3" in data:
            UpdateDevice(deviceId, self.p1PowerConsumedL3Unit, 0, str(data["power_consumed_l3"]))
        if "power_produced_l1" in data:
            UpdateDevice(deviceId, self.p1PowerProducedL1Unit, 0, str(data["power_produced_l1"]))
        if "power_produced_l2" in data:
            UpdateDevice(deviceId, self.p1PowerProducedL2Unit, 0, str(data["power_produced_l2"]))
        if "power_produced_l3" in data:
            UpdateDevice(deviceId, self.p1PowerProducedL3Unit, 0, str(data["power_produced_l3"]))
        if "power_failure_any_phase" in data:
            UpdateDevice(deviceId, self.p1PowerFailureUnit, 1, str(data["power_failure_any_phase"]))
        if "long_power_failure_any_phase" in data:
            UpdateDevice(deviceId, self.p1LongPowerFailureUnit, 1, str(data["long_power_failure_any_phase"]))
        if "voltage_sag_count_l1" in data:
            UpdateDevice(deviceId, self.p1VoltageSagL1Unit, 1, str(data["voltage_sag_count_l1"]))
        if "voltage_sag_count_l2" in data:
            UpdateDevice(deviceId, self.p1VoltageSagL2Unit, 1, str(data["voltage_sag_count_l2"]))
        if "voltage_sag_count_l3" in data:
            UpdateDevice(deviceId, self.p1VoltageSagL3Unit, 1, str(data["voltage_sag_count_l3"]))
        if "voltage_swell_count_l1" in data:
            UpdateDevice(deviceId, self.p1VoltageSwellL1Unit, 1, str(data["voltage_swell_count_l1"]))
        if "voltage_swell_count_l2" in data:
            UpdateDevice(deviceId, self.p1VoltageSwellL2Unit, 1, str(data["voltage_swell_count_l2"]))
        if "voltage_swell_count_l3" in data:
            UpdateDevice(deviceId, self.p1VoltageSwellL3Unit, 1, str(data["voltage_swell_count_l3"]))
        if "gas_meter_value" in data:
            gas_value = data["gas_meter_value"]
            try:
                gas_reading = round(float(gas_value) / 1000, 3)
            except Exception:
                gas_reading = gas_value
            UpdateDevice(deviceId, self.p1GasMeterUnit, 1, str(gas_reading))
        if "gas_meter_value_time" in data:
            UpdateDevice(deviceId, self.p1GasMeterTimeUnit, 1, str(data["gas_meter_value_time"]))

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
    #dynamicScheduleAPI = '/api/v1/dynamic/schedule'
    dynamicScheduleAPI = '/api/v2/dynamic/schedule'
    #dynamicScheduleAPI = '/api/v1/energy/status'
    energyAPI = '/api/v1/energy/status'
    powerAPI = '/api/v1/power/status'
    strategyAPI = '/api/v1/power/active_strategy'
    powerSetpointAPI = '/api/v1/power/setpoint'

    def getDynamicSchedule(self):
        dt_format = "%Y-%m-%d"
        data = self.GetDataFromDevice(self.dynamicScheduleAPI)
        logging.debug("dynamic schedule for '" + str(SessyBase.name) + "': '"+str(data))
        if "dynamic_schedule" not in data or len(data["dynamic_schedule"]) < 1:
            raise exceptions.ScheduleError("power strategy", datetime.now().strftime(dt_format))
        # if "power_strategy" not in data or len(data["power_strategy"]) < 1:
            # raise exceptions.ScheduleError("power strategy", datetime.now().strftime(dt_format))
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
        if state.upper() == 'TRUE': self._state = self.ON
    
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
    Domoticz.Debug("Config will be dumped to log file")
    logging.debug("Parameter count: " + str(len(Parameters)))
    for x in Parameters:
        if Parameters[x] != "":
            logging.debug( "Parameter '" + x + "':'" + str(Parameters[x]) + "'")
    Configurations = getConfigItem()
    logging.debug("Configuration count: " + str(len(Configurations)))
    for x in Configurations:
        if Configurations[x] != "":
            logging.debug( "Configuration '" + x + "':'" + str(Configurations[x]) + "'")
    logging.debug("Device count: " + str(len(Devices)))
    for x in Devices:
        logging.debug("Device:           " + str(x) + " - " + str(Devices[x]))
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
                    logging.info("nValue supplied is not an integer. Device: "+str(Device)+ " unit "+str(Unit)+" nValue "+str(nValue))
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
        logging.error("trying to update a non-existent unit "+str(Unit)+" from device "+str(Device))
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
