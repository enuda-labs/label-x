from rest_framework import generics
from common.responses import SuccessResponse
from common.utils import get_dp_cost_settings


class GetSystemSettingsView(generics.GenericAPIView):
    def get(self, request, *args, **kwargs):
        settings = get_dp_cost_settings()
        
        print(settings)
        return SuccessResponse(message="System settings", data=settings)