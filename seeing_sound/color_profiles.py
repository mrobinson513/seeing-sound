# seeing_sound/color_profiles.py

class ColorProfile:
    def map_audio_to_hsb(self, rms, freq, min_freq, max_freq, clip_threshold, max_brightness):
        raise NotImplementedError


class DefaultProfile(ColorProfile):
    def map_audio_to_hsb(self, rms, freq, min_freq, max_freq, clip_threshold, max_brightness):
        from .color import audio_to_hsb
        return audio_to_hsb(rms, freq, min_freq, max_freq, clip_threshold, max_brightness)


class WarmProfile(ColorProfile):
    def map_audio_to_hsb(self, rms, freq, min_freq, max_freq, clip_threshold, max_brightness):
        if rms >= clip_threshold:
            return 0, 0, max_brightness

        norm_freq = min(max((freq - min_freq) / (max_freq - min_freq), 0.0), 1.0)
        hue = int((0.05 + 0.1 * norm_freq) * 65535)  # warm band from red-orange to yellow
        saturation = int(0.8 * 65535)
        brightness = int(min(max(rms / 5000.0, 0.0), 1.0) * max_brightness)
        return hue, saturation, brightness


class ColdProfile(ColorProfile):
    def map_audio_to_hsb(self, rms, freq, min_freq, max_freq, clip_threshold, max_brightness):
        if rms >= clip_threshold:
            return 0, 0, max_brightness

        norm_freq = min(max((freq - min_freq) / (max_freq - min_freq), 0.0), 1.0)
        hue = int((0.55 + 0.15 * norm_freq) * 65535)  # cold band from blue to purple
        saturation = int(0.9 * 65535)
        brightness = int(min(max(rms / 5000.0, 0.0), 1.0) * max_brightness)
        return hue, saturation, brightness


def get_profile(name: str) -> ColorProfile:
    return {
        "default": DefaultProfile(),
        "warm": WarmProfile(),
        "cold": ColdProfile(),
    }.get(name.lower(), DefaultProfile())
