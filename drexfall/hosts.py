from django.conf import settings
from django_hosts import patterns, host

host_patterns = patterns('',
                         host(r'www', 'core.urls', name='core'),
                         host(r'scan', 'scan.urls', name='scan'),
                         host(r'profiles', 'profiles.urls', name='profiles'),
                         host(r'api', 'api.urls', name='api'),
                         )
