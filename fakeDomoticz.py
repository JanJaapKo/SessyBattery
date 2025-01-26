#
#   Fake Domoticz - Domoticz Python plugin stub
#
#   With thanks to Frank Fesevur, 2017
#
#   Very simple module to make local testing easier
#   It "emulates" Domoticz.Log(), Domoticz.Error and Domoticz.Debug()
#   It also emulates the Device and Unit from the Ex framework
#
from datetime import datetime
Devices = dict()
Parameters = {"Mode1": 200, "Mode2": 6, "Mode3" : 2200, "Mode4": "Debug", "Mode5": "", "Mode6": "Debug", "Port": 8443, "Username": "mail@domain.com" , "Password": "aNicerp@ssword", "Version" : "0.0.0", "HomeFolder":"/home/pi/domoticz/plugins/SessyBattery/", "Name": "fakeDomoticz"}
config = dict()

class myUnit:
    def __init__(self,Name="label", Unit=0, Type=0, TypeName ="", Subtype=0, Switchtype="", Options="", DeviceID="deviceURL", Used=0, Image=0):
        self.Name=Name
        self.Unit=Unit
        self.Type=Type
        self.TypeName=TypeName
        self.Subtype=Subtype
        self.Switchtype=Switchtype
        self.DeviceID=DeviceID
        self.Used=Used

    def Create(self):
        print("Creating unit "+str(self.Name)+" for deviceID "+str(self.DeviceID))

    @property
    def LastUpdate(self):
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
class Domoticz:
    def __init__(self):
        self.Units = []
        self.Devices = dict()
        return

    def Log(self, s):
        print(s)

    def Status(self, s):
        print(s)

    def Error(self, s):
        print(s)

    def Debug(self, s):
        print(s)
    
    def Debugging(self, level):
        print("debugging set to "+ str(level))
    
    def Heartbeat(self, level):
        print("heartbeat set to "+ str(level))
    
    def Device(self, DeviceID=""):
        self.Devices[DeviceID] = DeviceID
        print("creating DeviceID: "+ DeviceID)

    def Unit(self, Name="label", Unit=0, Type=0, TypeName="", Subtype=0, Switchtype="", Options="", DeviceID="deviceURL", Used=0, Image=0):
        newUnit = myUnit(Name, Unit, Type, TypeName, Subtype, Switchtype, Options, DeviceID, Used)
        #self.Devices[DeviceID].Units.append(newUnit)
        self.Units.append(newUnit)
        return newUnit

    def Configuration(self):
        return config
