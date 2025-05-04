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
DEFAULT_MAX_UPDATES_PER_SECOND = 30
DEFAULT_CLIP_THRESHOLD = 32000
DEFAULT_MIN_FREQ = 20
DEFAULT_MAX_FREQ = 20000
SMOOTHING_FACTOR = 0.2

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
    return min_freq, max_freq, clip_threshold

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


def audio_to_hsb(rms, freq, min_freq, max_freq, clip_threshold):
    try:
        if rms >= clip_threshold:
            return 0, 0, 100

        norm_freq = min(max((freq - min_freq) / (max_freq - min_freq), 0.0), 1.0)

        if norm_freq < 0.33:
            hue = int((0.5 + norm_freq * 3 * 0.16) * 65535)
            saturation = 50
        elif norm_freq < 0.66:
            hue = int((0.16 + (norm_freq - 0.33) * 3 * 0.16) * 65535)
            saturation = 75
        else:
            hue = int((0.0 + (norm_freq - 0.66) * 3 * 0.16) * 65535)
            saturation = 100

        brightness = int(min(max(rms / 5000.0, 0.0), 1.0) * 100)

        return hue // 182, saturation, brightness
    except Exception as e:
        warnings.warn(f"Color mapping failed: {e}")
        return 0, 0, 0


def smooth_transition(current, target, factor):
    return int(current + (target - current) * factor)


def send_color_to_hue(lights, current_hsb, target_hsb):
    new_hue = smooth_transition(current_hsb[0], target_hsb[0], SMOOTHING_FACTOR)
    new_saturation = smooth_transition(current_hsb[1], target_hsb[1], SMOOTHING_FACTOR)
    new_brightness = smooth_transition(current_hsb[2], target_hsb[2], SMOOTHING_FACTOR)

    for light in lights:
        try:
            light.brightness = new_brightness
            light.hue = new_hue
            light.saturation = new_saturation
        except Exception as e:
            warnings.warn(f"Failed to send color to bulb {light.name}: {e}")

    return (new_hue, new_saturation, new_brightness)


def listen_and_analyze(duration=10, device_index=None):
    if device_index is None:
        device_index = p.get_default_input_device_info()["index"]

    config_mtime = os.path.getmtime(CONFIG_FILE) if os.path.exists(CONFIG_FILE) else None
    config = load_config()
    bridge = connect_hue_bridge(config)
    lights = bridge.lights
    min_update_interval = get_update_interval(config)
    min_freq, max_freq, clip_threshold = get_audio_config(config)

    rate = get_sample_rate(device_index)

    stream = p.open(format=FORMAT,
                    channels=CHANNELS,
                    rate=rate,
                    input=True,
                    input_device_index=device_index,
                    frames_per_buffer=CHUNK)

    logging.info(f"Listening on device {device_index}... (press Ctrl+C to stop)")
    start_time = time.time()
    last_update_time = 0

    current_hsb = (0, 0, 0)

    try:
        while time.time() - start_time < duration:
            if os.path.exists(CONFIG_FILE):
                new_mtime = os.path.getmtime(CONFIG_FILE)
                if new_mtime != config_mtime:
                    config = load_config()
                    bridge = connect_hue_bridge(config)
                    lights = bridge.lights
                    min_update_interval = get_update_interval(config)
                    min_freq, max_freq, clip_threshold = get_audio_config(config)
                    config_mtime = new_mtime
                    logging.info("Reloaded config.")

            data = stream.read(CHUNK, exception_on_overflow=False)
            rms, freq = compute_volume_and_freq(data, rate)
            target_hsb = audio_to_hsb(rms, freq, min_freq, max_freq, clip_threshold)
            logging.info(f"Volume (RMS): {rms:.2f} | Dominant Freq: {freq:.2f} Hz | HSB Target: {target_hsb}")

            current_time = time.time()
            if current_time - last_update_time >= min_update_interval:
                current_hsb = send_color_to_hue(lights, current_hsb, target_hsb)
                last_update_time = current_time

    except KeyboardInterrupt:
        logging.info("Stopped by user.")
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()
        logging.info("Stream closed.")

if __name__ == "__main__":
    list_input_devices()
    try:
        selected = int(input("\nEnter the device index to use: "))
    except ValueError:
        selected = None
    listen_and_analyze(duration=10, device_index=selected)
