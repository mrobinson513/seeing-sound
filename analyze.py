import numpy as np
import pyaudio
import time
import colorsys
import warnings
import yaml
import os
import logging
from phue import Bridge

CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1

CONFIG_FILE = "config.yaml"
DEFAULT_MAX_UPDATES_PER_SECOND = 5
DEFAULT_CLIP_THRESHOLD = 32000
DEFAULT_MIN_FREQ = 20
DEFAULT_MAX_FREQ = 20000
DEFAULT_MIN_AMPLITUDE = 1000  # minimum RMS for valid audio
DEFAULT_IDLE_TIMEOUT = 5  # seconds before setting idle color
DEFAULT_IDLE_COLOR = (0, 0, 0)  # Hue, Saturation, Brightness for idle (lights off)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("analyzer.log")
    ]
)

p = pyaudio.PyAudio()

def load_config():
    try:
        with open(CONFIG_FILE, "r") as f:
            config = yaml.safe_load(f)
            return config or {}
    except FileNotFoundError:
        return {}

def get_update_interval(config):
    max_updates = config.get("max_updates_per_second", DEFAULT_MAX_UPDATES_PER_SECOND)
    max_updates = min(max_updates, 30)
    return 1.0 / max_updates

def get_audio_config(config):
    min_freq = config.get("min_frequency", DEFAULT_MIN_FREQ)
    max_freq = config.get("max_frequency", DEFAULT_MAX_FREQ)
    clip_threshold = config.get("clip_threshold", DEFAULT_CLIP_THRESHOLD)
    min_amplitude = config.get("min_amplitude", DEFAULT_MIN_AMPLITUDE)
    idle_timeout = config.get("idle_timeout", DEFAULT_IDLE_TIMEOUT)
    idle_color = config.get("idle_color", DEFAULT_IDLE_COLOR)
    return min_freq, max_freq, clip_threshold, min_amplitude, idle_timeout, tuple(idle_color)

def connect_hue_bridge(config):
    bridge_ip = config.get("hue_bridge_ip")
    if not bridge_ip:
        raise ValueError("hue_bridge_ip is not specified in config.yaml")
    bridge = Bridge(bridge_ip)
    bridge.connect()
    return bridge

def list_input_devices():
    logging.info("Available input devices:")
    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        if info["maxInputChannels"] > 0:
            logging.info(f"  [{i}] {info['name']}")

def get_sample_rate(device_index):
    try:
        return int(p.get_device_info_by_index(device_index)["defaultSampleRate"])
    except Exception:
        return 44100

def compute_volume_and_freq(data, rate):
    samples = np.frombuffer(data, dtype=np.int16)
    if len(samples) == 0:
        return 0.0, 0.0

    try:
        rms = np.sqrt(np.mean(samples.astype(np.float64)**2))
    except Exception as e:
        warnings.warn(f"RMS calculation failed: {e}")
        rms = 0.0

    try:
        fft = np.fft.rfft(samples)
        freqs = np.fft.rfftfreq(len(samples), 1.0 / rate)
        peak_freq = freqs[np.argmax(np.abs(fft))]
    except Exception as e:
        warnings.warn(f"FFT calculation failed: {e}")
        peak_freq = 0.0

    return rms, peak_freq


def audio_to_hsb(rms, freq, min_freq, max_freq, clip_threshold, min_amplitude):
    if rms < min_amplitude or freq < min_freq or freq > max_freq:
        return None

    try:
        if rms >= clip_threshold:
            return 0, 0, 127

        norm_freq = min(max((freq - min_freq) / (max_freq - min_freq), 0.0), 1.0)

        if norm_freq < 0.33:
            hue = int((0.5 + norm_freq * 3 * 0.16) * 65535)
            saturation = 127
        elif norm_freq < 0.66:
            hue = int((0.16 + (norm_freq - 0.33) * 3 * 0.16) * 65535)
            saturation = 191
        else:
            hue = int((0.0 + (norm_freq - 0.66) * 3 * 0.16) * 65535)
            saturation = 254

        brightness = int(min(max(rms / 5000.0, 0.0), 1.0) * 127)

        return hue, saturation, brightness
    except Exception as e:
        warnings.warn(f"Color mapping failed: {e}")
        return None


def send_color_to_hue(lights, target_hsb):
    hue, saturation, brightness = target_hsb

    command = {
        'hue': hue,
        'sat': saturation,
        'bri': brightness,
        'transitiontime': 0
    }

    for light in lights:
        try:
            light.bridge.set_light(light.light_id, command)
        except Exception as e:
            warnings.warn(f"Failed to send color to bulb {light.name}: {e}")


def listen_and_analyze(lights, min_update_interval, min_freq, max_freq, clip_threshold, min_amplitude, idle_timeout, idle_color, device_index=None):
    if device_index is None:
        device_index = p.get_default_input_device_info()["index"]

    rate = get_sample_rate(device_index)

    stream = p.open(format=FORMAT,
                    channels=CHANNELS,
                    rate=rate,
                    input=True,
                    input_device_index=device_index,
                    frames_per_buffer=CHUNK)

    logging.info(f"Listening on device {device_index}... (press Ctrl+C to stop)")
    last_update_time = 0
    idle_start_time = None

    try:
        while True:
            data = stream.read(CHUNK, exception_on_overflow=False)
            rms, freq = compute_volume_and_freq(data, rate)
            target_hsb = audio_to_hsb(rms, freq, min_freq, max_freq, clip_threshold, min_amplitude)

            current_time = time.time()

            if target_hsb is not None:
                logging.info(f"Volume (RMS): {rms:.2f} | Dominant Freq: {freq:.2f} Hz | HSB: {target_hsb}")
                idle_start_time = None
                if current_time - last_update_time >= min_update_interval:
                    send_color_to_hue(lights, target_hsb)
                    last_update_time = current_time
            else:
                if idle_start_time is None:
                    idle_start_time = current_time
                elif current_time - idle_start_time >= idle_timeout and current_time - last_update_time >= min_update_interval:
                    send_color_to_hue(lights, idle_color)
                    last_update_time = current_time

    except KeyboardInterrupt:
        logging.info("Stopped by user.")
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()
        logging.info("Stream closed.")

if __name__ == "__main__":
    config = load_config()
    bridge = connect_hue_bridge(config)
    lights = bridge.lights
    min_update_interval = get_update_interval(config)
    min_freq, max_freq, clip_threshold, min_amplitude, idle_timeout, idle_color = get_audio_config(config)

    list_input_devices()
    try:
        selected = int(input("\nEnter the device index to use: "))
    except ValueError:
        selected = None
    listen_and_analyze(lights, min_update_interval, min_freq, max_freq, clip_threshold, min_amplitude, idle_timeout, idle_color, device_index=selected)
