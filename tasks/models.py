from django.db import models


class CreatedPlaylist(models.Model):
    """Stores recently created playlists to display on the main page."""
    name = models.CharField(max_length=255)
    spotify_url = models.URLField()
    image_url = models.URLField(blank=True, null=True)
    track_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} ({self.track_count} tracks)"
