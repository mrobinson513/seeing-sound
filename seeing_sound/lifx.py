import logging
import warnings

from lifxlan import LifxLAN

def discover_bulbs():
    lifx = LifxLAN()
    return lifx.get_devices()

def send_color_to_lifx_hsb(bulbs, hue, saturation, brightness):
    for bulb in bulbs:
        logging.debug(f"✅ Sending to {bulb.get_label()} @ {bulb.get_ip_addr()} with color {[hue, saturation, brightness, 3500]}")
        try:
            bulb.set_color([hue, saturation, brightness, 3500], rapid=True)
        except Exception as e:
            logging.warning(f"⚠️ Error sending to {bulb.get_label()}: {e}")
