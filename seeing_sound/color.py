
def audio_to_hsb(rms, freq, min_freq, max_freq, clip_threshold, max_brightness):
    try:
        if rms >= clip_threshold:
            return 0, 0, max_brightness

        norm_freq = min(max((freq - min_freq) / (max_freq - min_freq), 0.0), 1.0)

        if norm_freq < 0.33:
            hue = int(norm_freq * 3 * 0.16 * 65535 + 0.5 * 65535)
            saturation = int(0.5 * 65535)
        elif norm_freq < 0.66:
            hue = int((0.16 + (norm_freq - 0.33) * 3 * 0.16) * 65535)
            saturation = int(0.75 * 65535)
        else:
            hue = int((0.0 + (norm_freq - 0.66) * 3 * 0.16) * 65535)
            saturation = 65535

        brightness = int(min(max(rms / 5000.0, 0.0), 1.0) * max_brightness)
        return hue, saturation, brightness
    except Exception as e:
        import warnings
        warnings.warn(f"Color mapping failed: {e}")
        return 0, 0, 0
