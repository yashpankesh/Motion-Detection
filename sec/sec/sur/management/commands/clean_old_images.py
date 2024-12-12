import datetime
from django.core.management.base import BaseCommand
from sur.models import MotionAlert

class Command(BaseCommand):
    help = 'Deletes motion alerts older than a specified number of days'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days', 
            type=int, 
            help='Number of days before which images will be deleted', 
            default=10
        )

    def handle(self, *args, **kwargs):
        days = kwargs['days']
        cutoff_date = datetime.datetime.now() - datetime.timedelta(days=days)
        old_alerts = MotionAlert.objects.filter(timestamp__lt=cutoff_date)
        
        count, _ = old_alerts.delete()
        self.stdout.write(self.style.SUCCESS(f'Successfully deleted {count} old motion alerts'))
