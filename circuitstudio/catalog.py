"""Small, explicit symbol catalogue. Pins are never inferred for unknown symbols."""

SYMBOLS = {
    "Device:R": {"pins": {"1": "1", "2": "2"}, "shape": "resistor"},
    "Device:C": {"pins": {"1": "1", "2": "2"}, "shape": "capacitor"},
    "Device:LED": {"pins": {"1": "K", "2": "A"}, "shape": "led"},
    "Connector:Conn_01x02_Pin": {"pins": {"1": "1", "2": "2"}, "shape": "connector2"},
    "CircuitStudio:NMOS_3Pin": {"pins": {"1": "G", "2": "S", "3": "D"}, "shape": "three_pin"},
    "CircuitStudio:RP2040_Interface": {"pins": {"1": "GPIO_A", "2": "GPIO_B", "3": "3V3"}, "shape": "three_pin"},
    "CircuitStudio:Generic_4Pin": {"pins": {"1": "1", "2": "2", "3": "3", "4": "4"}, "shape": "four_pin"},
}


def symbol_info(symbol_id: str):
    return SYMBOLS.get(symbol_id)
