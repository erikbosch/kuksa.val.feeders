# Example provider for VAL/VSS to DBC communication

This is a prototype based on dbc2val. Most things are hardcoded and it can currently handle only a single CAN frame
(258) as default handling for other CAN frames have not been implemented.

## What does this feeder do

* It reads an annotated VSS JSON spec
* For all annotated signals it create a subscription on KUKSA.val Databroker on target value.
* Whenever a subscribed signals is updated it uses the annotations to convert the VSS value to DBC value
* It stores all the updated values in an internal representation
* It then tries to send all CAN-frames related to the DBC signals
* It first sets default data for all dbc signals in that CAN-frame
* Then it overrides it with actual values received
* Then it is sent on CAN

*Note: For now only CAN-frame 258 supported*

## Challenges if transforming this to a real use-case

* Who is responsible for assembling the whole CAN-frame? You or some middleware? Do you need to keep track of default values?
* What to do if you do not have access to all information needed for the CAN-frame? Some may not be available in VSS!
* Who is responsible for deciding if the CAN frame shall be sent on change only or recurring?

## Example Mapping

See `vss_dbc.json` in mapping directory.

```
Vehicle.Body.Mirrors.Left.Tilt:
  datatype: int8
  type: actuator
  vss2dbc:
    signal: VCLEFT_mirrorTiltYPosition
    transform:
      math: "floor((x*40)-100)"
```


## Setup

For details on tool requirements see dbc2val. Note that this prototype currently does not have configuration options,
and no support for building a Docker container.

The data is interpreted using the [Model3CAN.dbc](./Model3CAN.dbc) [maintained by Josh Wardell](https://github.com/joshwardell/model3dbc).


## Test Setup

* Start Databroker (without authorization)
* Start dbcfeeder.py, configured to read data from `vcan0 `
* Start canprovider.py (hardcoded to use `vcan0`)
* Start kuksa-client and make sure it connects successfully to databroker


If everything works it shall be possible for you to set the target variable for `Vehicle.Body.Mirrors.Left.Tilt`,
and then verify that the actual values has been updated.

```
Test Client> setTargetValue Vehicle.Body.Mirrors.Left.Tilt 52
OK

Test Client> getValue Vehicle.Body.Mirrors.Left.Tilt
{
    "path": "Vehicle.Body.Mirrors.Left.Tilt",
    "value": {
        "value": 52,
        "timestamp": "2023-04-17T14:03:35.474168+00:00"
    }
}

```

For `canprovider.py`you should see something like:


```

user@debian:~/kuksa.val.feeders/val2dbc$ ./canprovider.py
2023-04-17 16:08:09,679 INFO can.interfaces.socketcan.socketcan: Created a socket
2023-04-17 16:08:09,679 INFO canprovider: Starting CAN feeder
2023-04-17 16:08:09,679 INFO canprovider: Using DBC reader
2023-04-17 16:08:09,679 INFO canproviderlib.dbcreader: Reading DBC file Model3CAN.dbc
2023-04-17 16:08:10,120 INFO canprovider: Using mapping: mapping/vss_3.1.1/vss_dbc.json
2023-04-17 16:08:10,122 INFO canproviderlib.dbc2vssmapper: Reading dbc configurations from mapping/vss_3.1.1/vss_dbc.json
2023-04-17 16:08:10,123 INFO canproviderlib.dbcreader: Found signal in DBC file VCLEFT_mirrorTiltXPosition in CAN frame id 0x102
2023-04-17 16:08:10,123 INFO canproviderlib.dbcreader: Found signal in DBC file VCLEFT_mirrorTiltYPosition in CAN frame id 0x102
2023-04-17 16:08:10,123 INFO canproviderlib.dbcreader: Found signal in DBC file VCRIGHT_trunkLatchStatus in CAN frame id 0x103
2023-04-17 16:08:10,124 INFO canproviderlib.dbcreader: Found signal in DBC file PTC_rightTempIGBT in CAN frame id 0x287
2023-04-17 16:08:10,124 INFO canproviderlib.dbc2vssmapper: Subscribing to Vehicle.Body.Mirrors.Left.Pan
2023-04-17 16:08:10,125 INFO canproviderlib.dbc2vssmapper: Subscribing to Vehicle.Body.Mirrors.Left.Tilt
2023-04-17 16:08:10,125 INFO canproviderlib.dbc2vssmapper: Subscribing to Vehicle.Body.Trunk.Rear.IsOpen
2023-04-17 16:08:10,125 INFO canproviderlib.dbc2vssmapper: Subscribing to Vehicle.Powertrain.ElectricMotor.Temperature
2023-04-17 16:08:10,131 INFO canprovider: Target value for Vehicle.Body.Mirrors.Left.Tilt is now: Datapoint(value=52, timestamp=datetime.datetime(2023, 4, 17, 13, 52, 41, 47807, tzinfo=datetime.timezone.utc)) of type <class 'int'>
2023-04-17 16:08:10,131 INFO canprovider: Found observation VSSObservation(dbc_name='VCLEFT_mirrorTiltYPosition', vss_name='Vehicle.Body.Mirrors.Left.Tilt', vss_value=52, dbc_value=3.8)
2023-04-17 16:08:10,131 INFO canproviderlib.dbcreader: Found signal in DBC file VCLEFT_mirrorTiltYPosition in CAN frame id 0x102
2023-04-17 16:08:10,131 INFO canproviderlib.dbc2vssmapper: Using stored information to create CAN-frame for 258
2023-04-17 16:08:10,131 INFO canproviderlib.dbc2vssmapper: We have DBC id VCLEFT_mirrorTiltXPosition with value None
2023-04-17 16:08:10,131 INFO canproviderlib.dbc2vssmapper: We have DBC id VCLEFT_mirrorTiltYPosition with value 3.8
2023-04-17 16:08:20,503 INFO canprovider: Target value for Vehicle.Body.Mirrors.Left.Tilt is now: Datapoint(value=55, timestamp=datetime.datetime(2023, 4, 17, 14, 8, 20, 502169, tzinfo=datetime.timezone.utc)) of type <class 'int'>
2023-04-17 16:08:20,504 INFO canprovider: Found observation VSSObservation(dbc_name='VCLEFT_mirrorTiltYPosition', vss_name='Vehicle.Body.Mirrors.Left.Tilt', vss_value=55, dbc_value=3.875)
2023-04-17 16:08:20,505 INFO canproviderlib.dbcreader: Found signal in DBC file VCLEFT_mirrorTiltYPosition in CAN frame id 0x102
2023-04-17 16:08:20,505 INFO canproviderlib.dbc2vssmapper: Using stored information to create CAN-frame for 258
2023-04-17 16:08:20,505 INFO canproviderlib.dbc2vssmapper: We have DBC id VCLEFT_mirrorTiltXPosition with value None
2023-04-17 16:08:20,505 INFO canproviderlib.dbc2vssmapper: We have DBC id VCLEFT_mirrorTiltYPosition with value 3.875

```
