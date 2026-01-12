import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from channels.exceptions import DenyConnection
from django.utils import timezone
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from django.contrib.auth import get_user_model
from urllib.parse import parse_qs

from .models import User

# Set up logger
logger = logging.getLogger(__name__)

from channels.generic.websocket import AsyncWebsocketConsumer
from channels.exceptions import DenyConnection
import json


class UserActivityConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        logger.info("WebSocket connection attempt received")
        
        # Get query parameters
        user = self.scope['user']
        if not user.is_anonymous:
            self.user_group_name = f"user_tasks_{user.id}"
            await self.channel_layer.group_add(
                self.user_group_name,
                self.channel_name
            )
            await self.accept()
        else:
            raise DenyConnection("Authentication failed") 
    
       
        self.user_id = user.id
        await self.update_user_status(True)
        logger.info(f"User {user} is now online")
        
        # await self.accept()
        logger.info(f"WebSocket connection accepted for user {user}")


    async def disconnect(self, close_code):
        logger.info(f"WebSocket disconnection initiated with code {close_code}")
        
        # Check if user was authenticated
        if hasattr(self, 'user_id'):
            # Leave user group
            await self.channel_layer.group_discard(
                self.user_group_name,  # Changed from self.user_group to self.user_group_name
                self.channel_name
            )
            logger.debug(f"Removed user from group: {self.user_group_name}")
            
            # Update user's online status
            await self.update_user_status(False)
            logger.info(f"User {self.user_id} is now offline")
        else:
            logger.debug("Unauthenticated connection disconnected")

    async def receive(self, text_data):
        """
        Handle incoming WebSocket messages.
        Currently only handles activity updates.
        """
        try:
            data = json.loads(text_data)
            await self.send(text_data=json.dumps(data))  # Send it back to the client
            await self.send(text_data=json.dumps({'message': self.user_id}))

            message_type = data.get('type')
            
            logger.debug(f"Received message of type: {message_type}")
            
            if message_type == 'activity':
                await self.update_user_activity()
                logger.debug(f"Updated activity timestamp for user {self.user_id}")
            else:
                logger.warning(f"Received unhandled message type: {message_type}")
        except json.JSONDecodeError:
            logger.error("Received invalid JSON data")
        except Exception as e:
            logger.exception(f"Error processing message: {str(e)}")
            
            
    async def task_message(self, event):
        """
        Handle task.message events and send them to the client. 
        This comes in when a task has been assign to a user and they need to be notified.
        """
        # Extract the task data from the event
        task_data = event.get('text', {})
        
        # Send the task data to the WebSocket client
        await self.send(text_data=json.dumps({
            'type': 'task.update',
            'task': task_data
        }))

    @database_sync_to_async
    def update_user_status(self, is_online):
        """Update user's online status"""
        try:
            User.objects.filter(id=self.user_id).update(
                is_online=is_online,
                last_activity=timezone.now()
            )
            return True
        except Exception as e:
            logger.exception(f"Error updating user status: {str(e)}")
            return False

    @database_sync_to_async
    def update_user_activity(self):
        """Update user's last activity timestamp"""
        try:
            User.objects.filter(id=self.user_id).update(
                last_activity=timezone.now()
            )
            return True
        except Exception as e:
            logger.exception(f"Error updating user activity: {str(e)}")
            return False