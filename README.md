# Stromnetz Graz for Home Assistant
[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/custom-components/hacs)

This component syncs the history of the energy consumption recorded by the Energy Meter with homeassistant.


## Supported Configuration
This integration was only tested with a webportal account that has only one 'installation', one 'meter' and quaterly hour update enabled.

## Update rate
The update rate is not configurable (every 30 min) as Stromnetz Graz typically only adds new data after midnight for the previous day.

## History
When adding this integration the full historical data of the selected meter is synced and added as a statistics entry.
As the energy tab in Home Assistant only shows data at a hourly resolution the quater hour data is binned to a single hour.





## Installation

1. Ensure that [HACS](https://hacs.xyz) is installed.

2. Todo

## TODO
- configure quater hour
- allow for energy price
- make sure timezone is correct
- finish readme



## Contributing

 ```  
"mounts": [
    // Custom configuration directory
    "source=C:\\Users\\al3xi\\Documents\\GIT\\homassistant-stromnetz-graz-1\\custom_components\\stromnetz_graz,target=${containerWorkspaceFolder}/config/custom_components/stromnetz_graz,type=bind"
  ],```
  