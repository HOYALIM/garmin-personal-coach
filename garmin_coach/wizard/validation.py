from typing import Optional, Tuple


def validate_age(age: Optional[int]) -> Tuple[bool, str]:
    if age is None:
        return True, ""
    if not isinstance(age, int):
        return False, "Age must be a number"
    if age < 10 or age > 120:
        return False, "Age must be between 10 and 120"
    return True, ""


def validate_weight(weight: Optional[float]) -> Tuple[bool, str]:
    if weight is None:
        return True, ""
    if not isinstance(weight, (int, float)):
        return False, "Weight must be a number"
    if weight < 20 or weight > 300:
        return False, "Weight must be between 20 and 300 kg"
    return True, ""


def validate_height(height: Optional[int]) -> Tuple[bool, str]:
    if height is None:
        return True, ""
    if not isinstance(height, int):
        return False, "Height must be a number"
    if height < 100 or height > 250:
        return False, "Height must be between 100 and 250 cm"
    return True, ""


def validate_max_hr(max_hr: Optional[int]) -> Tuple[bool, str]:
    if max_hr is None:
        return True, ""
    if not isinstance(max_hr, int):
        return False, "Max heart rate must be a number"
    if max_hr < 100 or max_hr > 220:
        return False, "Max heart rate must be between 100 and 220 bpm"
    return True, ""


def validate_resting_hr(resting_hr: Optional[int]) -> Tuple[bool, str]:
    if resting_hr is None:
        return True, ""
    if not isinstance(resting_hr, int):
        return False, "Resting heart rate must be a number"
    if resting_hr < 30 or resting_hr > 120:
        return False, "Resting heart rate must be between 30 and 120 bpm"
    return True, ""


def validate_ftp(ftp: Optional[int]) -> Tuple[bool, str]:
    if ftp is None:
        return True, ""
    if not isinstance(ftp, int):
        return False, "FTP must be a number"
    if ftp < 50 or ftp > 500:
        return False, "FTP must be between 50 and 500 watts"
    return True, ""


def validate_training_days(days: Optional[int]) -> Tuple[bool, str]:
    if days is None:
        return True, ""
    if not isinstance(days, int):
        return False, "Training days must be a number"
    if days < 1 or days > 7:
        return False, "Training days must be between 1 and 7"
    return True, ""


def validate_name(name: Optional[str]) -> Tuple[bool, str]:
    if name is None:
        return True, ""
    if not isinstance(name, str):
        return False, "Name must be text"
    if len(name.strip()) < 1:
        return False, "Name cannot be empty"
    if len(name) > 100:
        return False, "Name is too long (max 100 characters)"
    return True, ""


def validate_sports(sports: list) -> Tuple[bool, str]:
    valid_sports = {"running", "cycling", "swimming", "triathlon"}
    if not sports:
        return False, "At least one sport must be selected"
    for sport in sports:
        if sport not in valid_sports:
            return False, f"Invalid sport: {sport}"
    return True, ""


def validate_profile(config: dict) -> Tuple[bool, list]:
    errors = []

    validators = {
        "name": validate_name,
        "age": validate_age,
        "weight_kg": validate_weight,
        "height_cm": validate_height,
        "max_heart_rate": validate_max_hr,
        "resting_heart_rate": validate_resting_hr,
        "ftp": validate_ftp,
        "training_days_per_week": validate_training_days,
    }

    for field, validator in validators.items():
        value = config.get(field)
        valid, msg = validator(value)
        if not valid:
            errors.append(f"{field}: {msg}")

    sports = config.get("sports", [])
    valid, msg = validate_sports(sports)
    if not valid:
        errors.append(msg)

    return len(errors) == 0, errors


def calculate_max_hr(age: int) -> int:
    return 220 - age


def calculate_target_hr(age: int, resting_hr: int) -> dict:
    max_hr = calculate_max_hr(age)
    hrr = max_hr - resting_hr

    zones = {
        "zone1": (int(resting_hr + hrr * 0.5), int(resting_hr + hrr * 0.6)),
        "zone2": (int(resting_hr + hrr * 0.6), int(resting_hr + hrr * 0.7)),
        "zone3": (int(resting_hr + hrr * 0.7), int(resting_hr + hrr * 0.8)),
        "zone4": (int(resting_hr + hrr * 0.8), int(resting_hr + hrr * 0.9)),
        "zone5": (int(resting_hr + hrr * 0.9), max_hr),
    }
    return zones
