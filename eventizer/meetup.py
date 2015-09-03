# -*- coding: utf-8 -*-
#
# Copyright (C) 2014-2015 Bitergia
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.
#
# Authors:
#     Santiago Dueñas <sduenas@bitergia.com>
#

import datetime
import time
import urlparse

import requests

from eventizer.db.model import City, Category, Topic, Group, Event,\
    Member, RSVP


MEETUP_API_URL = "https://api.meetup.com/2/"
HEADERS = {'User-Agent': 'eventizer/0.0.1'}
MIN_LIMIT_RATE = 5
WAIT_TIME = 2


class NotFoundError(Exception):
    """Entity not found"""

    def __init__(self, entity, type_):
        self.entity = entity
        self.type_ = type

    def __repr__(self):
        return "%s (%s) not found" % (self.entity, self.type_)

    def __srt__(self):
        return "%s (%s) not found" % (self.entity, self.type_)


class MeetupError(Exception):
    """Generic Meetup Error"""

    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return str(self.msg)


def epoch_to_datetime(epoch):
    ts = epoch / 1000.0
    return datetime.datetime.fromtimestamp(ts)


def check_rate_limit(response):
    headers = response.headers

    if 'X-RateLimit-Remaining' not in headers:
        return

    remaining = int(headers['X-RateLimit-Remaining'])
    reset = int(headers['X-RateLimit-Reset'])

    if remaining <= MIN_LIMIT_RATE:
        time.sleep(reset)


class MeetupIterator(object):

    def __init__(self, url, params, headers):
        self.url = url
        self.params = params
        self.headers = headers
        self.has_next = True
        self.results = []

    def __iter__(self):
        return self

    def _fetch(self):
        r = requests.get(self.url, params=self.params,
                         headers=self.headers)

        json = r.json()

        if 'code' in json:
            msg = '%s. %s. %s' % (json['code'], json['problem'], json['details'])
            raise MeetupError(msg)

        check_rate_limit(r)

        return json

    def next(self):
        if self.results:
            return self.results.pop(0)

        # Check if there are more releases to fetch
        if not self.has_next:
            raise StopIteration

        # Fetch new set of releases
        time.sleep(WAIT_TIME)
        json = self._fetch()

        self.results = json['results']

        if not self.results:
            raise StopIteration

        if not json['meta']['next']:
            self.has_next = False
        else:
            self.url = json['meta']['next']

        return self.results.pop(0)


class Meetup(object):

    MEMBERS_CACHE = {}
    CITIES_CACHE = {}
    TOPICS_CACHE = {}
    CATEGORIES_CACHE = {}

    def __init__(self, key, session):
        self.key = key
        self.session = session

    def fetch(self, group_name):
        return self._fetch_group(group_name)

    def _fetch_group(self, name):
        url = urlparse.urljoin(MEETUP_API_URL, 'groups')
        params = {'key' : self.key,
                  'sign' : 'true',
                  'group_urlname' : name,
                  'page' : 2}
        r = requests.get(url, params=params,
                         headers=HEADERS)

        json = r.json()

        if 'code' in json:
            msg = '%s. %s. %s' % (json['code'], json['problem'], json['details'])
            raise MeetupError(msg)

        if json['meta']['total_count'] != 1:
            raise NotFoundError(name, 'group')

        check_rate_limit(r)

        results = json['results']

        raw_group = results[0]

        group = self.__parse_group(raw_group)

        for member in self._fetch_members(group.urlname):
            group.members.append(member)

        for event in self._fetch_events(group.urlname):
            group.events.append(event)

        return group

    def _fetch_members(self, name, member_id=None):
        url = urlparse.urljoin(MEETUP_API_URL, 'members')
        params = {'key' : self.key,
                  'sign' : 'true',
                  'group_urlname' : name}

        for m in MeetupIterator(url, params, HEADERS):
            member = self.__parse_member(m)
            yield member

    def _fetch_member(self, member_id):
        if member_id in self.MEMBERS_CACHE:
            return self.MEMBERS_CACHE[member_id]

        url = urlparse.urljoin(MEETUP_API_URL, 'member/%s' % str(member_id))
        params = {'key' : self.key,
                  'sign' : 'true'}
        r = requests.get(url, params=params,
                         headers=HEADERS)

        if r.text == 'not found':
            raise NotFoundError(str(member_id), 'member')

        json = r.json()

        if 'code' in json:
            msg = '%s. %s. %s' % (json['code'], json['problem'], json['details'])
            raise MeetupError(msg)

        check_rate_limit(r)

        member = self.__parse_member(json)

        return member

    def _fetch_events(self, name):
        url = urlparse.urljoin(MEETUP_API_URL, 'events')

        # This is required due urrlib encodes comma characters
        # when values are given using params dict
        url = urlparse.urljoin(url, '?status=upcoming,past')

        params = {'key' : self.key,
                  'sign' : 'true',
                  'group_urlname' : name,
                  'order' : 'time'}

        for raw_event in MeetupIterator(url, params, HEADERS):
            event = self.__parse_event(raw_event)

            time.sleep(WAIT_TIME)

            for rvps in self._fetch_rsvps(event.meetup_id):
                event.rsvps.append(rvps)
            yield event

    def _fetch_rsvps(self, event_id):
        url = urlparse.urljoin(MEETUP_API_URL, 'rsvps')
        params = {'key' : self.key,
                  'sign' : 'true',
                  'event_id' : event_id}

        for raw_rsvp in MeetupIterator(url, params, HEADERS):
            # According to the documentation, ff the RSVP is for a host
            # of a repeating event that hasn't been RSVP'd to by others,
            # the id in the response will be -1. So, we ignore it.
            if raw_rsvp['rsvp_id'] == -1:
                continue

            rsvp = self.__parse_rsvp(raw_rsvp)
            rsvp.member = self._fetch_member(raw_rsvp['member']['member_id'])
            yield rsvp

    def __parse_group(self, raw_group):
        group = Group.as_unique(self.session, meetup_id=raw_group['id'])

        if not group.id:
            group.name = raw_group['name']
            group.link = raw_group['link']
            group.urlname = raw_group['urlname']
            group.created_on = epoch_to_datetime(raw_group['created'])
            group.organizer = self._fetch_member(raw_group['organizer']['member_id'])

        group.rating = raw_group['rating']
        group.description = raw_group.get('description', None)
        group.city = self.__parse_city(raw_group)
        group.category = self.__parse_category(raw_group['category'])

        for raw_topic in raw_group['topics']:
            topic = self.__parse_topic(raw_topic)
            group.topics.append(topic)

        return group

    def __parse_event(self, raw_event):
        event = Event.as_unique(self.session,
                                meetup_id=raw_event['id'])

        updated = epoch_to_datetime(raw_event['updated'])

        if updated != event.updated:
            utc_time = raw_event['time']
            utc_offset = raw_event['utc_offset']

            event.name = raw_event['name']
            event.description = raw_event.get('description', None)
            event.time = epoch_to_datetime(utc_time)
            event.utc_offset =  utc_offset / 3600000
            event.local_time = epoch_to_datetime(utc_time + utc_offset)
            event.created = epoch_to_datetime(raw_event['created'])
            event.updated = updated
            event.status = raw_event['status']
            event.event_url = raw_event['event_url']

            if 'venue' in raw_event:
                event.city = self.__parse_city(raw_event['venue'])

        event.headcount = raw_event['headcount']

        if 'rating' in raw_event:
            event.rating_count = raw_event['rating']['count']
            event.rating_average = raw_event['rating']['average']
        else:
            event.rating_count = None
            event.rating_average = None

        return event

    def __parse_rsvp(self, raw_rsvp):
        rsvp = RSVP.as_unique(self.session, meetup_id=raw_rsvp['rsvp_id'])
        rsvp.response = raw_rsvp['response']
        return rsvp

    def __parse_city(self, raw_city):
        country = raw_city['country'].upper()
        city = raw_city['city']
        key = country + ':' + city

        if key in self.CITIES_CACHE:
            return self.CITIES_CACHE[key]

        c = City.as_unique(self.session,
                           country=country,
                           city=city)

        self.CITIES_CACHE[key] = c

        return c

    def __parse_category(self, raw_category):
        name = raw_category['name']
        shortname = raw_category['shortname']
        key = shortname

        if key in self.CATEGORIES_CACHE:
            return self.CATEGORIES_CACHE[key]

        c = Category.as_unique(self.session,
                               shortname=shortname)
        c.name = name

        self.CATEGORIES_CACHE[key] = c

        return c

    def __parse_topic(self, raw_topic):
        key = raw_topic['urlkey']

        if key in self.TOPICS_CACHE:
            return self.TOPICS_CACHE[key]

        t = Topic.as_unique(self.session,
                            urlkey=key)
        t.name = raw_topic['name']

        self.TOPICS_CACHE[key] = t

        return t

    def __parse_member(self, raw_member):
        member_id = raw_member['id']

        if member_id in self.MEMBERS_CACHE:
            return self.MEMBERS_CACHE[member_id]

        member = Member.as_unique(self.session,
                                  meetup_id=member_id)

        if not member.id:
            member.link = raw_member['link']
            member.joined = epoch_to_datetime(raw_member['joined'])

        member.name = raw_member['name']
        member.status = raw_member['status']
        member.city = self.__parse_city(raw_member)

        for raw_topic in raw_member['topics']:
            topic = self.__parse_topic(raw_topic)
            member.topics.append(topic)

        self.MEMBERS_CACHE[member_id] = member

        return member
