from dateutil.relativedelta import relativedelta
from django.utils import timezone


def get_duration(time_unit:str, time_period:int):
    now = timezone.now()
       
    if time_unit == 'month':
        duration= now - relativedelta(months= time_period)
    elif time_unit == 'year':
        duration = now - relativedelta(years=time_period)
    elif time_unit == 'week': 
        duration = now - relativedelta(weeks=time_period)
    elif time_unit == 'hour':
        duration = now - relativedelta(hours=time_period)
    elif time_unit == 'seconds':
        duration = now - relativedelta(seconds=time_period)
    else:
        duration = now - relativedelta(days=time_period)
    
    return duration

_settings_cache = None
def get_dp_cost_settings():
    """
    Retrieve all system settings related to data point costs and cache them in memory.

    This function uses a simple in-memory cache to avoid hitting the database
    every time the settings are needed.

    Returns:
        dict: A dictionary of system settings keyed by their `key` values with integer values.
    """
    global _settings_cache
    if _settings_cache is None:
        from django.apps import apps
        SystemSetting = apps.get_model("common", "SystemSetting")
        _settings_cache = {s.key: int(s.value) for s in SystemSetting.objects.all()}
    return _settings_cache
