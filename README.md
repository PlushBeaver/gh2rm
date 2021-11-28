# GitHub+Redmine integration script

This script closes issues in Redmine
when a GitHub PR with the description mentioning the issue is closed.

PR events are monitored using polling,
so that external access to the Redmine is not required.

The script is configured from environment, it should be run like this:

```shell
#!/usr/bin/env sh
export GITHUB_REPO='owner/repo'
export GITHUB_TOKEN='...'
export REDMINE_BASE_URL='http://host:port'
export REDMINE_API_KEY='...'
export REDMINE_ISSUE_PATTERN='^RM: (?:#|https://redmine.example.org/issues/)(\d+)$'
exec python3 bot.py
```
