import os
from django.core.management.base import BaseCommand, CommandError
from nht_sacco.apps.integrations.crypto import CryptoService


class Command(BaseCommand):
    help = 'Rotates the configuration database encryption key and re-encrypts all stored secrets atomically.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--new-key',
            required=False,
            default=None,
            type=str,
            help='The new master encryption key (minimum 32 characters).'
        )
        parser.add_argument(
            '--key-file',
            required=False,
            default=None,
            type=str,
            help='Path to a file containing the new master encryption key.'
        )
        parser.add_argument(
            '--old-key',
            required=False,
            default=None,
            type=str,
            help='The prior master encryption key (if not in settings).'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            default=False,
            help='Simulate key rotation without updating database records or clearing cache.'
        )

    def handle(self, *args, **options):
        new_key = options.get('new_key')
        key_file = options.get('key_file')
        old_key = options.get('old_key')
        dry_run = options.get('dry_run', False)

        if key_file:
            if not os.path.isfile(key_file):
                raise CommandError(f"Security Error: The specified key file does not exist: {key_file}")
            try:
                with open(key_file, 'r', encoding='utf-8') as f:
                    new_key = f.read().strip()
            except Exception as e:
                raise CommandError(f"Security Error: Failed to read key file {key_file}: {str(e)}")

        if not new_key:
            raise CommandError("Security Error: Either --new-key or --key-file must be provided.")

        new_key = new_key.strip()
        if len(new_key) < 32:
            raise CommandError("Security Error: The new encryption key must be at least 32 characters in length.")

        mode_str = "Simulating key rotation (DRY-RUN)..." if dry_run else "Starting atomic cryptographic key rotation..."
        self.stdout.write(self.style.WARNING(mode_str))

        try:
            count = CryptoService.rotate_all_secrets(new_key=new_key, old_key=old_key, dry_run=dry_run)
            if dry_run:
                self.stdout.write(self.style.SUCCESS(
                    f"[DRY-RUN COMPLETE] Successfully validated {count} secrets for key rotation. No database changes were applied."
                ))
            else:
                self.stdout.write(self.style.SUCCESS(
                    f"Successfully rotated encryption keys: {count} secrets re-encrypted at rest."
                ))
                self.stdout.write(self.style.NOTICE(
                    "IMPORTANT: Update SETTINGS_ENCRYPTION_KEY in your production environment / .env file before restarting workers."
                ))
        except Exception as e:
            raise CommandError(f"Key rotation failed: {str(e)}")
