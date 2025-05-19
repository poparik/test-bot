from tortoise import fields
from tortoise.models import Model
from datetime import datetime


class BlacklistedUser(Model):
    id = fields.IntField(pk=True)
    user_id = fields.BigIntField()
    username = fields.CharField(max_length=255, null=True)
    first_name = fields.CharField(max_length=255, null=True)
    last_name = fields.CharField(max_length=255, null=True)
    chat_id = fields.BigIntField()
    reason = fields.TextField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "blacklisted_users"
        unique_together = (("user_id", "chat_id"),)

    def __str__(self):
        return f"BlacklistedUser(user_id={self.user_id}, chat_id={self.chat_id})"


class PendingVerification(Model):
    id = fields.IntField(pk=True)
    user_id = fields.BigIntField()
    chat_id = fields.BigIntField()
    message_id = fields.BigIntField()
    expires_at = fields.DatetimeField()
    
    class Meta:
        table = "pending_verifications"
        unique_together = (("user_id", "chat_id"),)
    
    def __str__(self):
        return f"PendingVerification(user_id={self.user_id}, chat_id={self.chat_id})"