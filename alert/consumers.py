from channels.generic.websocket import AsyncWebsocketConsumer
from channels.exceptions import DenyConnection
import json

from task.models import TaskClassificationChoices
from task.tasks import submit_human_review_history
from asgiref.sync import sync_to_async



class AiChatWebsocket(AsyncWebsocketConsumer):
    async def connect(self):
        me = self.scope['user']
        if not me.is_anonymous:
            self.user_group_name = f"reviewer_group_{me.id}"
            await self.channel_layer.group_add(
                self.user_group_name,
                self.channel_name
            )
            await self.accept()
        else:
            raise DenyConnection("Authentication failed") 
    
    async def receive(self, text_data=None, bytes_data=None):
        """
        action
        confidence_score
        justification
        classification
        task_id
        """
        
        rd = json.loads(text_data)
        action = rd.get('action', None)
        user = self.scope['user']
        
        if action == 'submit_review':
            confidence_score = rd.get('confidence_score', None)
            justification = rd.get('justification', None)
            classification = rd.get('classification', None)
            task_id = rd.get('task_id', None)
            
            if not confidence_score or not justification or not classification or not task_id:
                return 
            
        
            if classification not in TaskClassificationChoices.values:
                return 
                        
            worker = submit_human_review_history.delay(user.id, task_id, confidence_score, justification, classification)
            
            await self.send_response_message(user.id, {'celery_worker_id': worker.id})
            
        
        # return await super().receive(text_data, bytes_data)
    
    
    async def send_response_message(self, receiver_id, body={}):
        await self.channel_layer.group_send(
            f"reviewer_group_{receiver_id}",
            {
                "type": "response.message",
                "text":body
            }
        )
        
        
    async def response_message(self, event):
        await self.send(text_data=json.dumps(event['text']))


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
    
    
    
    
