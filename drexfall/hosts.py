from django_hosts import patterns, host

host_patterns = patterns('',
                         host(r'www', 'drexfall.urls', name='www'),
                         host(r'api', 'core.urls', name='api'),
                         host(r'scan', 'scan.urls', name='scan'),
                         host(r'profiles', 'profiles.urls', name='profiles'),
                         host(r'.*', 'drexfall.urls', name='root'),
                         )
