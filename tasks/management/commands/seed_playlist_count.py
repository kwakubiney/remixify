"""
Management command to seed or reset the Redis playlist counter.
"""
from django.core.management.base import BaseCommand
from tasks.redis_utils import get_redis_client, PLAYLIST_COUNT_KEY, SEEDED_KEY
from tasks.models import CreatedPlaylist


class Command(BaseCommand):
    help = 'Seed or reset the Redis playlist counter from PostgreSQL'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force reseed even if already seeded',
        )
        parser.add_argument(
            '--set',
            type=int,
            help='Manually set the counter to a specific value',
        )

    def handle(self, *args, **options):
        client = get_redis_client()
        
        # Get current values
        current_redis_count = client.get(PLAYLIST_COUNT_KEY)
        current_redis_count = int(current_redis_count) if current_redis_count else 0
        db_count = CreatedPlaylist.objects.count()
        is_seeded = client.exists(SEEDED_KEY)
        
        self.stdout.write(f"Current Redis count: {current_redis_count}")
        self.stdout.write(f"Current PostgreSQL count: {db_count}")
        self.stdout.write(f"Already seeded: {bool(is_seeded)}")
        
        if options['set'] is not None:
            # Manually set the counter
            new_value = options['set']
            client.set(PLAYLIST_COUNT_KEY, new_value)
            client.set(SEEDED_KEY, "1")
            self.stdout.write(self.style.SUCCESS(f"Counter set to {new_value}"))
            return
        
        if is_seeded and not options['force']:
            self.stdout.write(self.style.WARNING(
                "Counter already seeded. Use --force to reseed from PostgreSQL."
            ))
            return
        
        # Seed from PostgreSQL
        client.set(PLAYLIST_COUNT_KEY, db_count)
        client.set(SEEDED_KEY, "1")
        
        self.stdout.write(self.style.SUCCESS(
            f"Redis counter seeded to {db_count} from PostgreSQL"
        ))
