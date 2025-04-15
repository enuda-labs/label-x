from rest_framework.response import Response
from rest_framework import serializers
from rest_framework import status


#utility classes to facilitate having consistent api responses 


class SuccessResponse(Response):
    def __init__(self, data=None, message=None, status=200, **kwargs):
        resp = {"status": "success", "data":data, "message":message, "success":True}
        super().__init__(data=resp, status=status, **kwargs)


class ErrorResponse(Response):
    def __init__(self, data=None, message=None, status=400, **kwargs):
        resp = {"status": "error", "data":data, "error":message, "success":False}
        super().__init__(data=resp, status=status, **kwargs)