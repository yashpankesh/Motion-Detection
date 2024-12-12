from django.db import models
import os

class MotionAlert(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)
    image = models.BinaryField(default=b'')
    distance = models.FloatField()

    def delete(self, *args, **kwargs):
        # If you store images in the filesystem, delete the file
        if hasattr(self, 'image') and os.path.isfile(self.image.path):
            os.remove(self.image.path)
        super(MotionAlert, self).delete(*args, **kwargs)

    def __str__(self):
        return f"Alert at {self.timestamp} - Distance: {self.distance:.2f}m"
