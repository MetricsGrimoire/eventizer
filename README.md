# README

Eventizer is a python tool created by Bitergia to retrieve information from Meetup groups. It store the data in a MySQL database.

# License

The license is __GPLv3__

## Installation

```
python setup.py install

```

## Usage
```
luis@hogaza:~/repos/eventizer$ eventizer --help
usage: Usage: 'eventizer [options] <group>

positional arguments:
  group                 Group name on Meetup

optional arguments:
  -h, --help            show this help message and exit

Database options:
  -u DB_USER, --user DB_USER
                        Database user name
  -p DB_PASSWORD, --password DB_PASSWORD
                        Database user password
  -d DB_NAME            Name of the database where fetched events will be
                        stored
  --host DB_HOSTNAME    Name of the host where the database server is running
  --port DB_PORT        Port of the host where the database server is running

Meetup options:
  --key KEY             Meetup API key
```
