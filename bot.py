#!/usr/bin/env python3

import json
import logging
import os
import re
import time
import urllib.error
import urllib.request


class Github:
    def __init__(self, settings):
        self._settings = settings
        self._sleep_sec = self._select_sleep_time({})
        self._etag = None

    def poll(self):
        url = f'https://api.github.com/repos/{self._settings["GITHUB_REPO"]}/events'
        req = urllib.request.Request(url)
        token = self._settings['GITHUB_TOKEN']
        if token:
            req.add_header('Authorization', f'token {token}')
        req.add_header('Accept', 'application/vnd.github.v3+json')
        if self._etag:
            req.add_header('If-None-Match', self._etag)
        try:
            with urllib.request.urlopen(req) as resp:
                self._sleep_sec = self._select_sleep_time(resp.headers)
                self._etag = resp.headers['ETag']
                return json.load(resp)
        except urllib.error.URLError as e:
            if e.code == 304:
                self._sleep_sec = self._select_sleep_time(e.headers)
            else:
                logging.error(f'polling events: {e}')
                self._etag = None
                self._sleep_sec = self._settings['POLLING_INTERVAL']
            return []

    def sleep(self):
        time.sleep(self._sleep_sec)

    def _select_sleep_time(self, headers):
        poll_interval = int(headers.get('X-Poll-Interval', 0))
        sleep_sec = max(poll_interval, self._settings['POLLING_INTERVAL'])
        return sleep_sec


class Redmine:
    def __init__(self, settings):
        self._settings = settings

    def close_issue(self, issue_id):
        desired_status_id = self._settings['REDMINE_STATUS_ID']
        try:
            issue = self._get_issue(issue_id)
            if issue['status']['id'] == desired_status_id:
                logging.info(f'issue {issue_id} is already closed')
                return
        except urllib.error.URLError as e:
            logging.warning(f'getting issue {issue_id}: {e}')
            return
        try:
            self._set_issue_status(issue_id, desired_status_id)
        except urllib.error.URLError as e:
            logging.error(f'closing issue {issue_id}: {e}')

    def _get_issue(self, issue_id):
        url = self._get_issue_url(issue_id)
        req = urllib.request.Request(url)
        req.add_header('X-Redmine-API-Key', self._settings['REDMINE_API_KEY'])
        resp = urllib.request.urlopen(req)
        return json.load(resp)['issue']

    def _set_issue_status(self, issue_id, status_id):
        url = self._get_issue_url(issue_id)
        data = json.dumps({'issue': {'status_id': status_id}})
        req = urllib.request.Request(url, method='PUT', data=data.encode('utf-8'))
        req.add_header('X-Redmine-API-Key', self._settings['REDMINE_API_KEY'])
        req.add_header('Content-Type', 'application/json')
        urllib.request.urlopen(req)

    def _get_issue_url(self, issue_id):
        return f'{self._settings["REDMINE_BASE_URL"]}/issues/{issue_id}.json'


def process_event(event, redmine, settings):
    if event['type'] != 'PullRequestEvent':
        return
    payload = event['payload']
    if payload['action'] != 'closed':
        return
    lines = (payload['pull_request']['body'] or '').splitlines()
    pattern = settings['REDMINE_ISSUE_PATTERN']
    for line in lines:
        match = re.search(pattern, line)
        if not match:
            continue
        issue_id = match.groups()[0]
        logging.info(f'closing issue {issue_id}, because PR {payload["number"]} is closed')
        redmine.close_issue(issue_id)


def load_settings():
    defaults = [
            ('GITHUB_REPO', '<owner>/<repo>'),
            ('GITHUB_TOKEN', '<secret>'), # if private
            ('REDMINE_BASE_URL', 'http://<redmine>'),
            ('REDMINE_API_KEY', '<secret>'),
            ('REDMINE_ISSUE_PATTERN', '^RM: #(\d+)$', re.compile),
            ('REDMINE_STATUS_ID', 5),
            ('POLLING_INTERVAL', 60),
            ('LOG_LEVEL', 'info')
            ]
    settings = {name: (cons[0] if cons else type(default))(os.getenv(name, default))
                for name, default, *cons in defaults}
    logging.basicConfig(level=getattr(logging, settings['LOG_LEVEL'].upper()))
    for name, default, *_ in defaults:
        value = settings[name] if default != '<secret>' else '<redacted>'
        logging.debug(f'config: {name} = {repr(value)}')
    return settings


def main():
    settings = load_settings()
    github = Github(settings)
    redmine = Redmine(settings)
    while True:
        events = github.poll()
        for event in events:
            process_event(event, redmine, settings)
        github.sleep()


if __name__ == '__main__':
    main()
