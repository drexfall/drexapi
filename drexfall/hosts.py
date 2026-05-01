import os

from django_hosts import patterns, host

_core = os.getenv('CORE_SUBDOMAIN', 'core')
_profiles = os.getenv('PROFILES_SUBDOMAIN', 'profiles')
_accounts = os.getenv('ACCOUNTS_SUBDOMAIN', 'accounts')
_projects = os.getenv('PROJECTS_SUBDOMAIN', 'projects')

host_patterns = patterns('',
                         host(_core, 'core.urls', name='core'),
                         host(_profiles, 'profiles.urls', name='profiles'),
                         host(_accounts, 'accounts.urls', name='accounts'),
                         host(_projects, 'projects.urls', name='projects'),
                         host(r'.*', 'drexfall.urls', name='root'),
                         )
