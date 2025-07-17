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