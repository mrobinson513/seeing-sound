
import yaml
import os
import logging

CONFIG_FILE = "config.yaml"
DEFAULT_MAX_UPDATES_PER_SECOND = 30
DEFAULT_CLIP_THRESHOLD = 32000
DEFAULT_MIN_FREQ = 100
DEFAULT_MAX_FREQ = 4000
DEFAULT_MAX_BRIGHTNESS = 60000
DEFAULT_LOG_LEVEL = "INFO"

def load_config():
    try:
        with open(CONFIG_FILE, "r") as f:
            config = yaml.safe_load(f)
            return config or {}
    except FileNotFoundError:
        return {}

def get_log_level(config):
    level_name = config.get("log_level", DEFAULT_LOG_LEVEL).upper()
    return getattr(logging, level_name, logging.INFO)

def get_audio_config(config):
    return (
        config.get("min_frequency", DEFAULT_MIN_FREQ),
        config.get("max_frequency", DEFAULT_MAX_FREQ),
        config.get("clip_threshold", DEFAULT_CLIP_THRESHOLD),
        config.get("max_brightness", DEFAULT_MAX_BRIGHTNESS),
    )

def get_update_interval(config):
    max_updates = config.get("max_updates_per_second", DEFAULT_MAX_UPDATES_PER_SECOND)
    return 1.0 / min(max_updates, 30)
