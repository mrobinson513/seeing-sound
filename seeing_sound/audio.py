
import numpy as np
import pyaudio
import warnings

CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1

p = pyaudio.PyAudio()

def list_input_devices():
    print("Available input devices:")
    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        if info["maxInputChannels"] > 0:
            print(f"  [{i}] {info['name']}")

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
        rms = np.sqrt(np.mean(samples.astype(np.float64) ** 2))
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
