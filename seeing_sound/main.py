
import time
import os
import logging
from seeing_sound.config import load_config, get_audio_config, get_update_interval, get_log_level
from seeing_sound.audio import list_input_devices, get_sample_rate, compute_volume_and_freq, p, CHUNK, FORMAT, CHANNELS
from seeing_sound.color import audio_to_hsb
from seeing_sound.lifx import discover_bulbs, send_color_to_lifx_hsb

def listen_and_analyze(bulbs=[], device_index=None):
    logging.info(f"Got {len(bulbs)} bulbs: {[b.get_ip_addr() for b in bulbs]}")

    if device_index is None:
        device_index = p.get_default_input_device_info()["index"]

    config_mtime = os.path.getmtime("config.yaml") if os.path.exists("config.yaml") else None
    config = load_config()
    min_update_interval = get_update_interval(config)
    min_freq, max_freq, clip_threshold, max_brightness = get_audio_config(config)

    rate = get_sample_rate(device_index)
    stream = p.open(format=FORMAT, channels=CHANNELS, rate=rate, input=True, input_device_index=device_index, frames_per_buffer=CHUNK)

    logging.info(f"Listening on device {device_index}... (press Ctrl+C to stop)")
    last_update_time = 0

    try:
        while True:
            if os.path.exists("config.yaml"):
                new_mtime = os.path.getmtime("config.yaml")
                if new_mtime != config_mtime:
                    config = load_config()
                    min_update_interval = get_update_interval(config)
                    min_freq, max_freq, clip_threshold, max_brightness = get_audio_config(config)
                    config_mtime = new_mtime
                    logging.info("Reloaded config.")

            data = stream.read(CHUNK, exception_on_overflow=False)
            rms, freq = compute_volume_and_freq(data, rate)
            hue, saturation, brightness = audio_to_hsb(rms, freq, min_freq, max_freq, clip_threshold, max_brightness)
            logging.info(f"Volume (RMS): {rms:.2f} | Freq: {freq:.2f} Hz | HSB: ({hue}, {saturation}, {brightness})")

            if time.time() - last_update_time >= min_update_interval:
                send_color_to_lifx_hsb(bulbs, hue, saturation, brightness)
                last_update_time = time.time()

    except KeyboardInterrupt:
        logging.info("Stopped by user.")
    finally:
        stream.stop_stream()
        stream.close()
        send_color_to_lifx_hsb(bulbs, 0, 0, 0)
        p.terminate()
        logging.info("Stream closed.")

def main():
    list_input_devices()
    try:
        selected = int(input("\nEnter the device index to use: "))
    except ValueError:
        selected = None

    bulbs = discover_bulbs()
    listen_and_analyze(bulbs=bulbs, device_index=selected)
