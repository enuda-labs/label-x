from channels.generic.websocket import AsyncWebsocketConsumer
from channels.exceptions import DenyConnection
import json


class AlertConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        me = self.scope['user']
        if not me.is_anonymous:
            self.user_group_name = f"user_tasks_{me.id}"
            await self.channel_layer.group_add(
                self.user_group_name,
                self.channel_name
            )
            await self.accept()
        else:
            raise DenyConnection("Authentication failed") 
    
    async def receive(self, text_data=None, bytes_data=None):
        return await super().receive(text_data, bytes_data)
    
    async def task_message(self, event):
        await self.send(text_data=json.dumps(event['text']))
    
    
    
    
