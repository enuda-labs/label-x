from rest_framework.response import Response
from rest_framework import serializers
from rest_framework import status


#utility classes and functions to facilitate having consistent api responses 
class SuccessResponse(Response):
    def __init__(self, data=None, message=None, status=200, **kwargs):
        resp = {"status": "success", "data":data, "message":message, "success":True}
        super().__init__(data=resp, status=status, **kwargs)


class ErrorResponse(Response):
    def __init__(self, data=None, message=None, status=400, **kwargs):
        resp = {"status": "error", "data":data, "error":message, "success":False}
        super().__init__(data=resp, status=status, **kwargs)
        


def get_first_error(errors):
    """
    Gets the first message in a serializer.errors
    
    Parameters:
    errors: The error messages of a serializer i.e serializer.errors
    """
    field, error_list = next(iter(errors.items()))
    return str(error_list[0]) 

def format_first_error(errors, with_key=True):
    field, error_list = next(iter(errors.items()))
    if isinstance(error_list, list):
        return f"({field}) {error_list[0]}" if with_key else error_list[0]
    else:
        return format_first_error(error_list)