import logging

from django.contrib.auth.models import AnonymousUser
from django.contrib.gis.geoip2 import GeoIP2, GeoIP2Exception
from django.db import models
from django.http import HttpRequest

from geoip2.errors import GeoIP2Error
from ipware.ip import get_client_ip
from django_user_agents.utils import get_user_agent


logger = logging.getLogger('tracking_analyzer')


class TrackerManager(models.Manager):
    """
    Custom ``Tracker`` model manager that implements a method to create a new
    object instance from an HTTP request.
    """
    def create_from_request(self, request, content_object):
        """
        Given an ``HTTPRequest`` object and a generic content, it creates a
        ``Tracker`` object to store the data of that request.

        :param request: A Django ``HTTPRequest`` object.
        :param content_object: A Django model instance. Any object can be
        related.
        :return: A newly created ``Tracker`` instance.
        """
        # Sanity checks.
        assert isinstance(request, HttpRequest), \
            '`request` object is not an `HTTPRequest`'
        assert issubclass(content_object.__class__, models.Model), \
            '`content_object` is not a Django model'

        user = request.user

        user_agent = get_user_agent(request)

        if user_agent.is_mobile:
            device_type = self.model.MOBILE
        elif user_agent.is_tablet:
            device_type = self.model.TABLET
        elif user_agent.is_pc:
            device_type = self.model.PC
        elif user_agent.is_bot:
            device_type = self.model.BOT
        else:
            device_type = self.model.UNKNOWN

        city = {}

        # Get the IP address and so the geographical info, if available.
        ip_address, _ = get_client_ip(request) or ''
        if not ip_address:
            logger.debug(
                'Could not determine IP address for request %s', request)
        else:
            geo = GeoIP2()
            try:
                city = geo.city(ip_address)
            except (GeoIP2Error, GeoIP2Exception):
                logger.exception(
                    'Unable to determine geolocation for address %s',
                    ip_address
                )

        tracker = self.model.objects.create(
            content_object=content_object,
            ip_address=ip_address,
            ip_country=city.get('country_code', '') or '',
            ip_region=city.get('region', '') or '',
            ip_city=city.get('city', '') or '',
            referrer=request.META.get('HTTP_REFERER', ''),
            device_type=device_type,
            device=user_agent.device.family,
            browser=user_agent.browser.family[:30],
            browser_version=user_agent.browser.version_string,
            system=user_agent.os.family,
            system_version=user_agent.os.version_string,
            user=user if user.is_authenticated else None
        )
        logger.info(
            'Tracked click in %s %s.',
            content_object._meta.object_name, content_object.pk
        )

        return tracker
