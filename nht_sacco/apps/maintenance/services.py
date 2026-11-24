from decimal import Decimal
from django.db import models
from django.utils import timezone
from django.db.models import Sum, Count, Avg
from .models import MaintenanceRecord, MaintenanceStatus


class MaintenanceService:
    @staticmethod
    def complete_service(record: MaintenanceRecord, verified_by, completed_date=None, downtime_hours=None, notes=None):
        """
        Completes and verifies a maintenance work order with downtime tracking.
        """
        record.status = MaintenanceStatus.COMPLETED
        record.verified_by = verified_by
        record.completed_date = completed_date or timezone.localdate()
        if downtime_hours is not None:
            record.downtime_hours = Decimal(str(downtime_hours))
        if notes:
            record.technician_notes = (record.technician_notes + f"\n{notes}").strip()
        record.save()
        return record

    @staticmethod
    def get_vehicle_maintenance_summary(vehicle):
        """
        Calculates operational maintenance metrics for a specific vehicle.
        """
        records = MaintenanceRecord.objects.filter(vehicle=vehicle)
        aggregates = records.aggregate(
            total_cost=Sum('total_cost'),
            total_downtime=Sum('downtime_hours'),
            total_services=Count('id')
        )
        last_record = records.filter(status=MaintenanceStatus.COMPLETED).order_by('-completed_date').first()
        return {
            'total_cost': aggregates['total_cost'] or Decimal('0.00'),
            'total_downtime_hours': aggregates['total_downtime'] or Decimal('0.00'),
            'total_services': aggregates['total_services'],
            'last_service_date': last_record.completed_date if last_record else None,
            'last_odometer': last_record.odometer_reading if last_record else None,
        }

    @staticmethod
    def get_fleet_maintenance_metrics():
        """
        Provides aggregated maintenance KPIs across the entire SACCO fleet.
        """
        qs = MaintenanceRecord.objects.all()
        aggregates = qs.aggregate(
            fleet_total_cost=Sum('total_cost'),
            fleet_total_downtime=Sum('downtime_hours'),
            completed_count=Count('id', filter=models.Q(status=MaintenanceStatus.COMPLETED)),
            pending_count=Count('id', filter=models.Q(status__in=[MaintenanceStatus.BOOKED, MaintenanceStatus.IN_PROGRESS]))
        )
        return {
            'fleet_total_cost': aggregates['fleet_total_cost'] or Decimal('0.00'),
            'fleet_total_downtime_hours': aggregates['fleet_total_downtime'] or Decimal('0.00'),
            'completed_count': aggregates['completed_count'],
            'pending_count': aggregates['pending_count'],
        }
