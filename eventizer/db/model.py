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

from sqlalchemy import Table, Column, Float, DateTime, Integer,\
    String, Text, ForeignKey, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship


Base = declarative_base()


class UniqueObject(object):

    @classmethod
    def unique_filter(cls, query, *arg, **kw):
        raise NotImplementedError

    @classmethod
    def as_unique(cls, session, *arg, **kw):
        return _unique(
                    session,
                    cls,
                    cls.unique_filter,
                    cls,
                    arg, kw
               )


class City(UniqueObject, Base):
    __tablename__ = 'cities'

    id = Column(Integer, primary_key=True)
    country = Column(String(32))
    city = Column(String(32))

    __table_args__ = (UniqueConstraint('country', 'city',
                                       name='_city_unique'),
                      {'mysql_charset': 'utf8'})

    @classmethod
    def unique_filter(cls, query, country, city):
        return query.filter(City.country == country,
                            City.city == city)


class Topic(UniqueObject, Base):
    __tablename__ = 'topics'

    id = Column(Integer, primary_key=True)
    urlkey = Column(String(64))
    name = Column(String(256))

    __table_args__ = (UniqueConstraint('urlkey',
                                       name='_topic_unique'),
                      {'mysql_charset': 'utf8'})

    @classmethod
    def unique_filter(cls, query, urlkey):
        return query.filter(Topic.urlkey == urlkey)


class Category(UniqueObject, Base):
    __tablename__ = 'categories'

    id = Column(Integer, primary_key=True)
    name = Column(String(256))
    shortname = Column(String(64))

    __table_args__ = (UniqueConstraint('shortname',
                                       name='_category_unique'),
                      {'mysql_charset': 'utf8'})

    @classmethod
    def unique_filter(cls, query, shortname):
        return query.filter(Category.shortname == shortname)


members_topics_table = Table('members_topics', Base.metadata,
    Column('member_id', Integer, ForeignKey('people.id')),
    Column('topic_id', Integer, ForeignKey('topics.id'))
)


class Member(UniqueObject, Base):
    __tablename__ = 'people'

    id = Column(Integer, primary_key=True)
    meetup_id = Column(Integer)
    name = Column(String(256))
    link = Column(String(256))
    joined = Column(DateTime(timezone=False))
    status = Column(String(32))

    city_id = Column(Integer,
                     ForeignKey('cities.id', ondelete='CASCADE'),)

    city = relationship('City', foreign_keys=[city_id])

    # many to many members-topics relationship
    topics = relationship('Topic', secondary=members_topics_table)

    __table_args__ = (UniqueConstraint('meetup_id',
                                       name='_member_unique'),
                      {'mysql_charset': 'utf8'})

    @classmethod
    def unique_filter(cls, query, meetup_id):
        return query.filter(Member.meetup_id == meetup_id)


groups_topics_table = Table('groups_topics', Base.metadata,
    Column('group_id', Integer, ForeignKey('groups.id')),
    Column('topic_id', Integer, ForeignKey('topics.id'))
)

members_groups_table = Table('members_groups', Base.metadata,
    Column('member_id', Integer, ForeignKey('people.id')),
    Column('group_id', Integer, ForeignKey('groups.id'))
)


class Group(UniqueObject, Base):
    __tablename__ = 'groups'

    id = Column(Integer, primary_key=True)
    meetup_id = Column(Integer)
    name = Column(String(256))
    link = Column(String(256))
    description = Column(Text())
    urlname = Column(String(256))
    rating = Column(Float())
    created_on = Column(DateTime(timezone=False))

    organizer_id = Column(Integer,
                          ForeignKey('people.id', ondelete='CASCADE'),)
    city_id = Column(Integer,
                     ForeignKey('cities.id', ondelete='CASCADE'),)
    category_id = Column(Integer,
                         ForeignKey('categories.id', ondelete='CASCADE'),)

    organizer = relationship('Member', foreign_keys=[organizer_id])
    city = relationship('City', foreign_keys=[city_id])
    category = relationship('Category', foreign_keys=[category_id])

    # many to many groups-topics relationship
    members = relationship('Member', secondary=members_groups_table)
    topics = relationship('Topic', secondary=groups_topics_table)
    events = relationship('Event',
                          cascade="save-update, merge, delete")

    __table_args__ = (UniqueConstraint('meetup_id',
                                       name='_group_unique'),
                      {'mysql_charset': 'utf8'})

    @classmethod
    def unique_filter(cls, query, meetup_id):
        return query.filter(Group.meetup_id == meetup_id)


class Event(UniqueObject, Base):
    __tablename__ = 'events'

    id = Column(Integer, primary_key=True)
    meetup_id = Column(String(64))
    name = Column(String(256))
    description = Column(Text())
    headcount = Column(Integer())
    status = Column(String(32))
    rating_count = Column(Float())
    rating_average = Column(Float())
    event_url = Column(String(256))
    created = Column(DateTime(timezone=False))
    updated = Column(DateTime(timezone=False))
    time = Column(DateTime(timezone=False))
    utc_offset = Column(Integer())
    local_time = Column(DateTime(timezone=False))

    group_id = Column(Integer,
                      ForeignKey('groups.id', ondelete='CASCADE'),)
    city_id = Column(Integer,
                     ForeignKey('cities.id', ondelete='CASCADE'),)

    group = relationship('Group')
    city = relationship('City', foreign_keys=[city_id])
    rsvps = relationship('RSVP',
                         cascade="save-update, merge, delete")

    __table_args__ = (UniqueConstraint('meetup_id',
                                       name='_event_unique'),
                      {'mysql_charset': 'utf8'})

    @classmethod
    def unique_filter(cls, query, meetup_id):
        return query.filter(Event.meetup_id == meetup_id)


class RSVP(UniqueObject, Base):
    __tablename__ = 'rsvps'

    id = Column(Integer, primary_key=True)
    meetup_id = Column(Integer)
    response = Column(String(32))

    event_id = Column(Integer,
                      ForeignKey('events.id', ondelete='CASCADE'),)
    member_id = Column(Integer,
                       ForeignKey('people.id', ondelete='CASCADE'),)

    event = relationship('Event')
    member = relationship('Member', foreign_keys=[member_id])

    __table_args__ = (UniqueConstraint('meetup_id',
                                       name='_rsvp_unique'),
                      {'mysql_charset': 'utf8'})

    @classmethod
    def unique_filter(cls, query, meetup_id):
        return query.filter(RSVP.meetup_id == meetup_id)


def _unique(session, cls, queryfunc, constructor, arg, kw):
    with session.no_autoflush:
        q = session.query(cls)
        q = queryfunc(q, *arg, **kw)

        obj = q.first()

        if not obj:
            obj = constructor(*arg, **kw)

        session.add(obj)
    return obj
