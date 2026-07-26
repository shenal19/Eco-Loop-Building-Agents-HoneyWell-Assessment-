"""
prepare_idf.py

Takes the stock 5ZoneAirCooled.idf (bundled with any EnergyPlus install,
under ExampleFiles/) and converts its heating/cooling setpoint schedules
from Schedule:Compact to Schedule:Constant.

Why: EnergyPlus's Python Data Transfer API can actuate any object of type
Schedule:Constant / Schedule:Compact as a "Schedule:Value" actuator, but
Schedule:Constant is simpler to seed with an initial value and is what
this project actuates every callback. This avoids having to hand-author
EMS:Actuator objects in the IDF.

Usage:
    1. Locate 5ZoneAirCooled.idf in your EnergyPlus install, e.g.:
       C:\\EnergyPlusV24-1-0\\ExampleFiles\\5ZoneAirCooled.idf
    2. Copy it into this `building/` folder.
    3. Copy a weather file (any .epw, e.g. USA_CO_Golden-NREL.724666_TMY3.epw
       from the WeatherData folder in your EnergyPlus install) into this
       folder and rename it weather.epw (or set ECOLOOP_EPW env var).
    4. Run: python prepare_idf.py
       -> produces 5ZoneAirCooled_modified.idf in this same folder.
"""

import os
import sys

try:
    from eppy.modeleditor import IDF
except ImportError:
    print("Missing dependency. Run: pip install eppy")
    sys.exit(1)

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "backend"))
import config  # noqa: E402

SOURCE_IDF = os.path.join(os.path.dirname(__file__), "5ZoneAirCooled.idf")
IDD_PATH = os.path.join(config.EPLUS_INSTALL_PATH, "Energy+.idd")


def main():
    if not os.path.exists(SOURCE_IDF):
        print(f"ERROR: {SOURCE_IDF} not found. Copy 5ZoneAirCooled.idf here first (see docstring).")
        sys.exit(1)
    if not os.path.exists(IDD_PATH):
        print(f"ERROR: IDD not found at {IDD_PATH}. Check EPLUS_INSTALL_PATH in backend/config.py.")
        sys.exit(1)

    IDF.setiddname(IDD_PATH)
    idf = IDF(SOURCE_IDF)

    converted = []
    for sched_name in [config.HEATING_SCHEDULE_NAME, config.COOLING_SCHEDULE_NAME]:
        compacts = [s for s in idf.idfobjects["SCHEDULE:COMPACT"] if s.Name == sched_name]
        if not compacts:
            print(f"WARNING: schedule '{sched_name}' not found as Schedule:Compact "
                  f"(may already be converted, or names differ in your file — check manually).")
            continue
        old = compacts[0]
        idf.removeidfobject(old)

        default_val = (config.HEATING_SETPOINT_DEFAULT_C
                        if sched_name == config.HEATING_SCHEDULE_NAME
                        else config.COOLING_SETPOINT_DEFAULT_C)

        new_obj = idf.newidfobject("SCHEDULE:CONSTANT")
        new_obj.Name = sched_name
        new_obj.Schedule_Type_Limits_Name = "Temperature"
        new_obj.Hourly_Value = default_val
        converted.append(sched_name)

    out_path = os.path.join(os.path.dirname(__file__), "5ZoneAirCooled_modified.idf")
    idf.saveas(out_path)
    print(f"Converted schedules: {converted}")
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    main()
