import re
from rest_framework import serializers
from django.contrib.auth import authenticate


from .models import CustomUser

class UserSerializer(serializers.ModelSerializer):
    """Serializer for the user model"""
    class Meta:
        model = CustomUser
        fields = ['id', 'username', 'email']

class LoginSerializer(serializers.Serializer):
    """Serializer for user login"""
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        user = authenticate(username=data['username'], password=data['password'])
        print(user)
        if not user:
            raise serializers.ValidationError("Invalid credentials")
        if not user.is_active:
            raise serializers.ValidationError("User is not active")
        return user


class RegisterSerializer(serializers.ModelSerializer):
    """Serializer for user registration"""

    password = serializers.CharField(
        write_only=True, 
        min_length=8,
    )

    class Meta:
        model = CustomUser
        fields = ['id', 'username', 'email', 'password']
        extra_kwargs = {
            'username': {
                'error_messages': {
                    'unique': 'Username already exists'
                }
            },
            'email': {
                'error_messages': {
                    'unique': 'Email already exists'
                }
            }
        }

    def create(self, validated_data):
        # Pop the password from validated_data
        password = validated_data.pop('password')
        
        # Create user instance
        user = CustomUser.objects.create(**validated_data)
        
        # Set the password (this will hash it)
        user.set_password(password)
        user.save()
        
        return user

    def validate_email(self, value):
        if CustomUser.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email already exists")
        return value

    def validate_username(self, value):
        if CustomUser.objects.filter(username=value).exists():
            raise serializers.ValidationError("Username already exists")
        return value
    
    def validate_password(self, value):
        """
        Validate password with detailed error messages for specific requirements
        """
        if len(value) < 8:
            raise serializers.ValidationError(
                "Password must be at least 8 characters long"
            )
        if not re.search(r'[A-Z]', value):
            raise serializers.ValidationError(
                "Password must contain at least one uppercase letter"
            )
        if not re.search(r'[a-z]', value):
            raise serializers.ValidationError(
                "Password must contain at least one lowercase letter"
            )
        if not re.search(r'\d', value):
            raise serializers.ValidationError(
                "Password must contain at least one number"
            )
        if not re.search(r'[@$!%*?&]', value):
            raise serializers.ValidationError(
                "Password must contain at least one special character (@$!%*?&)"
            )
        return value
    

class TokenRefreshSerializer(serializers.Serializer):
    refresh = serializers.CharField(help_text="The refresh token to obtain a new access token.")

class TokenRefreshResponseSerializer(serializers.Serializer):
    access = serializers.CharField(help_text="The new access token.")
    refresh = serializers.CharField(help_text="The new refresh token.", required=False)